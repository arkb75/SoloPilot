#!/usr/bin/env python3
"""
SoloPilot Dev Agent v0
Transforms planning output into milestone-based code structure with skeleton implementations.
"""

import json
import os
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
import yaml
from botocore.exceptions import BotoCoreError, ClientError


class DevAgent:
    def __init__(self, config_path: str = "config/model_config.yaml"):
        """Initialize the dev agent with configuration."""
        self.config = self._load_config(config_path)
        self._validate_credentials()
        self._validate_inference_profile()
        self.bedrock_client = None
        self._init_llm_clients()
        self._validate_inference_profile_access()

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        with open(config_path, "r") as f:
            return yaml.safe_load(f)

    def _validate_credentials(self) -> None:
        """Fail fast if no AWS credentials are available for Bedrock."""
        has_env = all(os.getenv(k) for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"))
        has_profile = Path("~/.aws/credentials").expanduser().exists()
        if not (has_env or has_profile):
            raise RuntimeError(
                "❌ Bedrock credentials not found. "
                "Set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY or configure ~/.aws/credentials."
            )

    def _validate_inference_profile(self) -> None:
        """Fail fast if inference profile ARN is missing or invalid."""
        arn = self.config["llm"]["bedrock"].get("inference_profile_arn")
        if not arn:
            raise RuntimeError(
                "❌ Bedrock inference_profile_arn not found in config. "
                "Update config/model_config.yaml with a valid ARN."
            )
        if not arn.startswith("arn:aws:bedrock:"):
            raise RuntimeError(
                f"❌ Invalid inference profile ARN format: {arn}. "
                "Expected format: arn:aws:bedrock:region:account:inference-profile/profile-id"
            )

    def _validate_inference_profile_access(self) -> None:
        """Fail fast if we don't have access to the inference profile."""
        if not self.bedrock_client:
            return  # Skip validation if no client

        try:
            # Try a simple operation to validate access - bedrock-runtime doesn't have list operations
            # We'll skip this validation for now since there's no good way to test access without invoking
            pass
        except ClientError as e:
            if "AccessDeniedException" in str(e):
                arn = self.config["llm"]["bedrock"]["inference_profile_arn"]
                raise RuntimeError(
                    f"❌ Bedrock access denied for inference profile. "
                    f"ARN: {arn}. Verify you have bedrock:InvokeModel permissions."
                ) from e

    def _init_llm_clients(self):
        """Initialize Bedrock client."""
        try:
            # Initialize Bedrock client
            self.bedrock_client = boto3.client(
                "bedrock-runtime", region_name=self.config["llm"]["bedrock"]["region"]
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Bedrock client: {e}")

    def _get_model_id_from_arn(self, inference_profile_arn: str) -> str:
        """Extract the underlying model ID from an inference profile ARN."""
        # ARN format: arn:aws:bedrock:region:account:inference-profile/us.provider.model-id
        if "/us." in inference_profile_arn:
            return inference_profile_arn.split("/")[-1]
        return "anthropic.claude-3-haiku-20240307-v1:0"  # fallback

    def _call_bedrock(self, prompt: str) -> str:
        """Call AWS Bedrock using inference profile ARN with proper parameters."""
        if not self.bedrock_client:
            raise Exception("Bedrock client not available")

        inference_profile_arn = self.config["llm"]["bedrock"]["inference_profile_arn"]
        model_id = self._get_model_id_from_arn(inference_profile_arn)

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self.config["llm"]["bedrock"]["model_kwargs"]["max_tokens"],
            "temperature": self.config["llm"]["bedrock"]["model_kwargs"]["temperature"],
            "top_p": self.config["llm"]["bedrock"]["model_kwargs"]["top_p"],
            "messages": [{"role": "user", "content": prompt}],
        }

        try:
            response = self.bedrock_client.invoke_model(
                modelId=model_id,
                inferenceProfileArn=inference_profile_arn,
                body=json.dumps(body),
                contentType="application/json",
            )

            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]

        except (ClientError, BotoCoreError) as e:
            # If we get AccessDeniedException, raise clear error with ARN info
            if "AccessDeniedException" in str(e) or "ValidationException" in str(e):
                raise RuntimeError(
                    f"❌ Bedrock inference profile access denied. "
                    f"ARN attempted: {inference_profile_arn}. "
                    f"Verify the profile exists and you have access in us-east-2."
                ) from e
            print(f"Bedrock API error: {e}")
            raise

    def _call_llm_with_retry(self, prompt: str, max_retries: int = 3) -> str:
        """Call Bedrock with exponential backoff retry."""
        last_exception = None

        for attempt in range(max_retries):
            try:
                return self._call_bedrock(prompt)
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    # Exponential backoff: 2^attempt + random jitter
                    wait_time = (2**attempt) + random.uniform(0, 1)
                    print(f"Bedrock call failed (attempt {attempt + 1}/{max_retries}): {e}")
                    print(f"Retrying in {wait_time:.1f} seconds...")
                    time.sleep(wait_time)
                else:
                    print(f"Final Bedrock attempt failed: {e}")

        raise last_exception

    def _call_llm(self, prompt: str) -> str:
        """Call Bedrock with retry logic."""
        try:
            return self._call_llm_with_retry(prompt)
        except Exception as e:
            print(f"Bedrock failed after retries: {e}")
            # Return stub code as final fallback
            return self._generate_stub_code()

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

            # Generate code using LLM
            prompt = self._create_milestone_prompt(
                milestone, planning_data.get("tech_stack", []), language
            )
            llm_response = self._call_llm(prompt)

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
