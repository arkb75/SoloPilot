#!/usr/bin/env python3
"""
SoloPilot Dev Agent v0
Transforms planning output into milestone-based code structure with skeleton implementations.
"""

import json
import os
import re
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from src.agents.dev.context_engine import get_context_engine
from src.providers import ProviderError, get_provider
from src.utils.linter_integration import LinterManager


class DevAgent:
    def __init__(self, config_path: str = "config/model_config.yaml"):
        """Initialize the dev agent with configuration."""
        self.config = self._load_config(config_path)

        # Initialize AI provider with error handling
        try:
            provider_name = os.getenv("AI_PROVIDER", "bedrock")
            self.provider = get_provider(provider_name, **self.config)
            print(f"✅ AI Provider ({provider_name}) initialized successfully")
        except ProviderError as e:
            print(f"⚠️ Provider initialization failed: {e}")
            if "NO_NETWORK" in str(e) or os.getenv("NO_NETWORK") == "1":
                # Fall back to fake provider for offline mode
                self.provider = get_provider("fake")
                print("✅ Fell back to fake provider for offline mode")
            else:
                raise

        # Initialize context engine
        try:
            self.context_engine = get_context_engine()
            engine_info = self.context_engine.get_engine_info()
            print(f"✅ Context Engine ({engine_info['engine']}) initialized successfully")
        except Exception as e:
            print(f"⚠️ Context engine initialization failed: {e}")
            # Fallback to legacy engine
            self.context_engine = get_context_engine("legacy")
            print("✅ Fell back to legacy context engine")

        # Initialize linter manager
        try:
            linter_config = self.config.get("linting", {})
            self.linter_manager = LinterManager(linter_config)
            print(
                f"✅ Linter Manager initialized for languages: {self.linter_manager.get_available_languages()}"
            )
        except Exception as e:
            print(f"⚠️ Linter Manager initialization failed: {e}")
            self.linter_manager = None

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file with environment variable substitution."""
        with open(config_path, "r") as f:
            content = f.read()

        # Substitute environment variables in format ${VAR:-default}
        def env_substitute(match):
            var_spec = match.group(1)
            if ":-" in var_spec:
                var_name, default = var_spec.split(":-", 1)
                return os.getenv(var_name, default)
            else:
                return os.getenv(var_spec, "")

        content = re.sub(r"\$\{([^}]+)\}", env_substitute, content)
        return yaml.safe_load(content)

    def _log_performance_metrics(self, metrics: Dict[str, Any]) -> None:
        """Log performance metrics for dev agent operations."""
        os.makedirs("logs", exist_ok=True)

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "component": "dev_agent",
            "operation": "llm_generation",
            **metrics,
        }

        # Log to performance file
        with open("logs/dev_agent_performance.log", "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        # Log slow operations
        if metrics.get("generation_time", 0) > 30:
            print(
                f"⚠️ Slow LLM generation: {metrics['generation_time']:.2f}s "
                f"(prompt: {metrics['prompt_size']} chars)"
            )

            # Capture stack trace for slow operations
            if metrics.get("success", True):
                slow_trace = {
                    "timestamp": datetime.now().isoformat(),
                    "component": "dev_agent",
                    "operation": "slow_generation_trace",
                    "stack_trace": "".join(traceback.format_stack()),
                    **metrics,
                }
                with open("logs/slow_operations.log", "a") as f:
                    f.write(json.dumps(slow_trace) + "\n")

    def _call_llm(
        self, prompt: str, milestone_path: Optional[Path] = None, timeout: Optional[int] = None
    ) -> str:
        """Call AI provider with context packing and performance monitoring."""
        if not self.provider:
            raise ProviderError("❌ AI provider not available.")

        # Build context if milestone_path is provided
        files = [milestone_path] if milestone_path else None
        context_start_time = time.time()

        if milestone_path:
            context, metadata = self.context_engine.build_context(milestone_path, prompt)
            if context.strip():
                prompt = context  # context already includes the original prompt
                context_time = time.time() - context_start_time
                print(
                    f"📦 Context built: {metadata['token_count']} tokens, {len(context)} chars "
                    f"via {metadata['engine']} from {milestone_path} ({context_time:.2f}s)"
                )

        # Performance monitoring
        prompt_size = len(prompt)
        generation_start_time = time.time()

        # Set default timeout based on prompt complexity
        if not timeout:
            if prompt_size < 10000:
                timeout = 15  # Fast timeout for simple prompts
            elif prompt_size < 50000:
                timeout = 30  # Standard timeout
            else:
                timeout = 60  # Extended timeout for complex prompts

        try:
            # Use provider's generate_code method with timeout
            result = self.provider.generate_code(prompt, files, timeout=timeout)

            # Log performance metrics
            generation_time = time.time() - generation_start_time
            self._log_performance_metrics(
                {
                    "prompt_size": prompt_size,
                    "generation_time": generation_time,
                    "timeout_used": timeout,
                    "milestone_path": str(milestone_path) if milestone_path else None,
                    "context_time": time.time() - context_start_time,
                    "success": True,
                }
            )

            return result

        except ProviderError as e:
            # Log failed performance metrics
            generation_time = time.time() - generation_start_time
            self._log_performance_metrics(
                {
                    "prompt_size": prompt_size,
                    "generation_time": generation_time,
                    "timeout_used": timeout,
                    "milestone_path": str(milestone_path) if milestone_path else None,
                    "context_time": time.time() - context_start_time,
                    "success": False,
                    "error": str(e),
                }
            )
            print(f"⚠️ Provider error: {e}")
            raise

    def _generate_with_linting(
        self,
        prompt: str,
        language: str,
        milestone_path: Optional[Path] = None,
        max_iterations: int = 3,
    ) -> str:
        """Generate code with real-time linting feedback and self-correction."""
        if not self.linter_manager or language not in self.linter_manager.get_available_languages():
            # No linting available, fall back to standard generation
            return self._call_llm(prompt, milestone_path)

        print(f"🔍 Generating {language} code with real-time linting feedback...")

        for iteration in range(max_iterations):
            print(f"  Iteration {iteration + 1}/{max_iterations}")

            # Use shorter timeout for linting iterations (fail fast)
            timeout = 15 if iteration > 0 else None  # First iteration uses default

            # Generate code
            try:
                code = self._call_llm(prompt, milestone_path, timeout=timeout)
            except Exception as e:
                print(f"  ❌ Code generation failed: {e}")
                return self._generate_stub_code()

            # Lint the generated code
            lint_results = self.linter_manager.lint_code(code, language)

            if not lint_results:
                print(f"  ✅ No linters available for {language}, using generated code")
                return code

            # Check if there are critical errors
            if not self.linter_manager.has_critical_errors(lint_results):
                summary = self.linter_manager.get_summary(lint_results)
                if summary["total_warnings"] > 0:
                    print(
                        f"  ✅ Code generated with {summary['total_warnings']} warnings (acceptable)"
                    )
                else:
                    print("  ✅ Code generated with no issues")
                return code

            # Generate correction prompt and retry
            summary = self.linter_manager.get_summary(lint_results)
            print(
                f"  ⚠️ Found {summary['total_errors']} errors, {summary['total_warnings']} warnings - attempting correction..."
            )

            if iteration < max_iterations - 1:  # Don't correct on the last iteration
                correction_prompt = self.linter_manager.generate_correction_prompt(
                    lint_results, code
                )
                prompt = correction_prompt  # Update prompt for next iteration
            else:
                print(
                    f"  ❌ Max iterations reached, using code with {summary['total_errors']} errors"
                )
                return code

        return code

    def _generate_stub_code(self) -> str:
        """Generate basic stub code when LLM calls fail."""
        return """// Generated stub code (LLM unavailable)
export class StubImplementation {
    constructor() {
        // TODO: Implement constructor
    }
    
    async execute() {
        // TODO: Implement main functionality
        throw new Error('Not implemented');
    }
}

// Example unit test
describe('StubImplementation', () => {
    test('should exist', () => {
        expect(StubImplementation).toBeDefined();
    });
});"""

    def _infer_language(self, tech_stack: List[str], milestone_name: str) -> str:
        """Infer programming language from tech stack and milestone context."""
        tech_lower = [tech.lower() for tech in tech_stack]
        milestone_lower = milestone_name.lower()

        if any(
            tech in tech_lower
            for tech in ["react", "node.js", "express", "javascript", "typescript"]
        ):
            return "javascript"
        elif any(tech in tech_lower for tech in ["python", "django", "flask", "fastapi"]):
            return "python"
        elif any(tech in tech_lower for tech in ["java", "spring"]):
            return "java"
        elif any(tech in tech_lower for tech in ["c#", "dotnet", ".net"]):
            return "csharp"
        elif "database" in milestone_lower or "schema" in milestone_lower:
            return "sql"
        else:
            return "javascript"  # Default to JavaScript

    def _get_file_extension(self, language: str) -> str:
        """Get appropriate file extension for language."""
        extensions = {
            "javascript": ".js",
            "typescript": ".ts",
            "python": ".py",
            "java": ".java",
            "csharp": ".cs",
            "sql": ".sql",
        }
        return extensions.get(language, ".js")

    def _create_milestone_prompt(
        self, milestone: Dict[str, Any], tech_stack: List[str], language: str
    ) -> str:
        """Create LLM prompt for milestone code generation."""
        return f"""Generate skeleton code and a unit test for this development milestone:

**Milestone:** {milestone['name']}
**Description:** {milestone['description']}
**Language:** {language}
**Tech Stack:** {', '.join(tech_stack)}

**Tasks in this milestone:**
{chr(10).join([f"- {task['name']}: {task['description']}" for task in milestone['tasks']])}

Please provide:
1. Skeleton code with proper structure, imports, and TODO comments
2. A comprehensive unit test using jest-style syntax
3. Brief documentation comments explaining key components

Format your response as:
```{language}
// === SKELETON CODE ===
[skeleton code here]

// === UNIT TEST ===
[unit test code here]
```

Focus on creating a solid foundation that a developer can build upon."""

    def _parse_llm_response(self, response: str, language: str) -> tuple[str, str]:
        """Parse LLM response to extract skeleton code and unit test."""
        try:
            # Look for code blocks
            if "```" in response:
                # Extract code from markdown blocks
                lines = response.split("\n")
                in_code_block = False
                current_section = None
                skeleton_code = []
                unit_test = []

                for line in lines:
                    if line.startswith("```"):
                        in_code_block = not in_code_block
                        continue

                    if in_code_block:
                        if "=== SKELETON CODE ===" in line:
                            current_section = "skeleton"
                        elif "=== UNIT TEST ===" in line:
                            current_section = "test"
                        elif current_section == "skeleton":
                            skeleton_code.append(line)
                        elif current_section == "test":
                            unit_test.append(line)

                skeleton = "\n".join(skeleton_code).strip()
                test = "\n".join(unit_test).strip()

                if skeleton and test:
                    return skeleton, test

            # Fallback: split response roughly in half
            lines = response.split("\n")
            mid = len(lines) // 2
            skeleton = "\n".join(lines[:mid]).strip()
            test = "\n".join(lines[mid:]).strip()

            return skeleton, test

        except Exception:
            # Final fallback
            return self._generate_stub_code(), "// Test code generation failed"

    def process_planning_output(
        self, planning_file: str, output_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process planning output and generate milestone-based code structure."""
        # Load planning data
        with open(planning_file, "r") as f:
            planning_data = json.load(f)

        # Create output directory
        if not output_dir:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = f"output/dev/{timestamp}"

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        manifest = {
            "project_title": planning_data.get("project_title", "Unknown Project"),
            "generated_at": datetime.now().isoformat(),
            "milestones": [],
            "tech_stack": planning_data.get("tech_stack", []),
            "output_directory": str(output_path),
        }

        print(f"Generating code for {len(planning_data['milestones'])} milestones...")

        # Process each milestone
        for i, milestone in enumerate(planning_data["milestones"], 1):
            print(
                f"Processing milestone {i}/{len(planning_data['milestones'])}: {milestone['name']}"
            )

            # Create milestone directory
            milestone_dir = output_path / f"milestone-{i}"
            milestone_dir.mkdir(exist_ok=True)

            # Infer language
            language = self._infer_language(planning_data.get("tech_stack", []), milestone["name"])
            file_ext = self._get_file_extension(language)

            # Generate code using LLM with real-time linting
            prompt = self._create_milestone_prompt(
                milestone, planning_data.get("tech_stack", []), language
            )
            llm_response = self._generate_with_linting(prompt, language, milestone_dir)

            # Parse response
            skeleton_code, unit_test = self._parse_llm_response(llm_response, language)

            # Write skeleton code
            code_file = milestone_dir / f"implementation{file_ext}"
            with open(code_file, "w") as f:
                f.write(skeleton_code)

            # Write unit test
            test_file = milestone_dir / f"test{file_ext}"
            with open(test_file, "w") as f:
                f.write(unit_test)

            # Create README for milestone
            readme_content = f"""# {milestone['name']}

{milestone['description']}

## Duration
{milestone.get('estimated_duration', 'Not specified')}

## Tasks
{chr(10).join([f"- **{task['name']}** ({task.get('estimated_hours', '?')}h): {task['description']}" for task in milestone['tasks']])}

## Generated Files
- `implementation{file_ext}` - Skeleton code implementation
- `test{file_ext}` - Unit test suite
- `README.md` - This documentation

## Next Steps
1. Review and refine the skeleton code
2. Implement TODO items marked in the code
3. Expand unit tests as needed
4. Ensure integration with previous milestones

Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

            readme_file = milestone_dir / "README.md"
            with open(readme_file, "w") as f:
                f.write(readme_content)

            # Add to manifest
            manifest["milestones"].append(
                {
                    "name": milestone["name"],
                    "directory": f"milestone-{i}",
                    "language": language,
                    "files": {
                        "implementation": f"implementation{file_ext}",
                        "test": f"test{file_ext}",
                        "readme": "README.md",
                    },
                    "tasks_count": len(milestone["tasks"]),
                }
            )

        # Create unit_tests directory with sample test
        unit_tests_dir = output_path / "unit_tests"
        unit_tests_dir.mkdir(exist_ok=True)

        sample_test = f"""// Sample integration test for all milestones
describe('Project Integration Tests', () => {{
    test('All milestone implementations should be defined', () => {{
        // TODO: Import and test each milestone implementation
        expect(true).toBe(true); // Placeholder
    }});
    
    test('Project structure should be valid', () => {{
        // TODO: Validate project structure and dependencies
        expect(true).toBe(true); // Placeholder  
    }});
}});

// Generated for project: {manifest['project_title']}
// Total milestones: {len(manifest['milestones'])}
"""

        sample_test_file = unit_tests_dir / "integration.test.js"
        with open(sample_test_file, "w") as f:
            f.write(sample_test)

        # Save manifest
        manifest_file = output_path / "manifest.json"
        with open(manifest_file, "w") as f:
            json.dump(manifest, f, indent=2)

        print(f"✅ Generated code structure in {output_path}")
        print(f"📁 Created {len(manifest['milestones'])} milestone directories")
        print("🧪 Generated unit tests and integration test framework")

        return manifest

    def find_latest_planning_output(self) -> Optional[str]:
        """Find the most recent planning output file."""
        planning_dir = Path("analysis/planning")
        if not planning_dir.exists():
            return None

        # Find all planning output files
        planning_files = list(planning_dir.glob("*/planning_output.json"))
        if not planning_files:
            return None

        # Return the most recent one (by directory name timestamp)
        latest = max(planning_files, key=lambda p: p.parent.name)
        return str(latest)
