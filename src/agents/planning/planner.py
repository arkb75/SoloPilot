"""
SoloPilot Project Planning Agent

Converts requirement specifications into structured project plans with milestones,
tech stack recommendations, and open questions.
"""

import json
import os
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

# Load environment variables from .env file
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # dotenv is optional

# Try to import LangChain components with fallbacks
try:
    from langchain_aws import ChatBedrock
    from langchain_openai import ChatOpenAI

    LANGCHAIN_AVAILABLE = True
    BEDROCK_AVAILABLE = True
except ImportError:
    try:
        from langchain_openai import ChatOpenAI

        LANGCHAIN_AVAILABLE = True
        BEDROCK_AVAILABLE = False
        print("⚠️  AWS Bedrock not available, using OpenAI only")
    except ImportError:
        LANGCHAIN_AVAILABLE = False
        BEDROCK_AVAILABLE = False
        print("⚠️  LangChain not fully available. LLM features will be disabled.")

from .models import PlanningOutput


class ProjectPlanner:
    """Converts requirement specifications into structured project plans."""

    def __init__(self, config_path: Optional[str] = None, output_dir: str = "analysis/planning"):
        self.config = self._load_config(config_path)
        self.output_dir = Path(output_dir)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / self.timestamp
        self._setup_llm()

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        """Load model configuration."""
        if config_path and os.path.exists(config_path):
            with open(config_path) as f:
                return yaml.safe_load(f)
        return {
            "llm": {
                "primary": "bedrock",
                "fallback": "openai",
                "bedrock": {
                    "model_id": "us.anthropic.claude-sonnet-4-20250514-v1:0",
                    "region": "us-east-2",
                },
                "openai": {"model": "gpt-4o-mini"},
            }
        }

    def _setup_llm(self):
        """Initialize LLM instances."""
        if not LANGCHAIN_AVAILABLE:
            self.primary_llm = None
            self.fallback_llm = None
            return

        # Setup primary LLM (Bedrock)
        self.primary_llm = None
        if BEDROCK_AVAILABLE and self.config["llm"]["primary"] == "bedrock":
            try:
                bedrock_config = self.config["llm"].get("bedrock", {})
                self.primary_llm = ChatBedrock(
                    model_id=bedrock_config.get(
                        "model_id", "us.anthropic.claude-sonnet-4-20250514-v1:0"
                    ),
                    region_name=bedrock_config.get("region", "us-east-2"),
                    model_kwargs={"temperature": 0.1, "max_tokens": 4096},
                )
                print("✅ AWS Bedrock initialized successfully")
            except Exception as e:
                print(f"⚠️  Bedrock initialization failed: {e}")
                self.primary_llm = None

        # Setup fallback LLM (OpenAI)
        try:
            openai_config = self.config["llm"].get("openai", {})
            self.fallback_llm = ChatOpenAI(
                model=openai_config.get("model", "gpt-4o-mini"), temperature=0.1
            )
            print("✅ OpenAI fallback initialized")
        except Exception as e:
            print(f"⚠️  OpenAI initialization failed: {e}")
            self.fallback_llm = None

    def load_specification(self, spec_path: str) -> Dict[str, Any]:
        """Load specification JSON from file."""
        with open(spec_path) as f:
            return json.load(f)

    def _call_llm_with_retry(self, llm, prompt: str, max_retries: int = 3):
        """Call LLM with exponential backoff retry."""
        last_exception = None

        for attempt in range(max_retries):
            try:
                return llm.invoke(prompt)
            except Exception as e:
                last_exception = e
                if attempt < max_retries - 1:
                    # Exponential backoff: 2^attempt + random jitter
                    wait_time = (2**attempt) + random.uniform(0, 1)
                    print(f"LLM call failed (attempt {attempt + 1}/{max_retries}): {e}")
                    print(f"Retrying in {wait_time:.1f} seconds...")
                    time.sleep(wait_time)
                else:
                    print(f"Final LLM attempt failed: {e}")

        raise last_exception

    def generate_plan(self, specification: Dict[str, Any]) -> PlanningOutput:
        """Generate project plan from specification using LLM with retry logic."""

        if not LANGCHAIN_AVAILABLE or (not self.primary_llm and not self.fallback_llm):
            # Fallback to simple plan generation
            return self._generate_plan_fallback(specification)

        prompt = self._build_planning_prompt(specification)
        llm = self.primary_llm or self.fallback_llm

        try:
            print(f"🧠 Using LLM: {llm.__class__.__name__}")
            response = self._call_llm_with_retry(llm, prompt)

            print("✅ LLM planning successful")
            return self._parse_llm_response(response, specification)
        except Exception as e:
            print(f"⚠️  Primary LLM failed after retries ({e})")
            if self.fallback_llm and llm != self.fallback_llm:
                try:
                    print(f"🔄 Trying fallback LLM: {self.fallback_llm.__class__.__name__}")
                    response = self._call_llm_with_retry(self.fallback_llm, prompt)
                    print("✅ Fallback LLM planning successful")
                    return self._parse_llm_response(response, specification)
                except Exception as fallback_e:
                    print(f"⚠️  Fallback LLM also failed after retries ({fallback_e})")
                    pass
            # If all LLMs fail, use fallback
            print("🔄 Using simple plan generation fallback")
            return self._generate_plan_fallback(specification)

    def _build_planning_prompt(self, specification: Dict[str, Any]) -> str:
        """Build prompt for project planning."""
        spec_json = json.dumps(specification, indent=2)

        return f"""
You are a senior software architect and project manager. Given the following project specification,
create a detailed project plan that breaks the work into ≤5 logical milestones.

Project Specification:
{spec_json}

Requirements:
1. Break the project into ≤5 milestones that follow a logical development sequence
2. Each milestone should have 3-8 specific, actionable tasks
3. Recommend a modern, appropriate tech stack
4. Identify open questions that need clarification
5. Provide realistic time estimates

Return ONLY a JSON object with this exact structure:
{{
  "project_title": "Clear project title",
  "project_summary": "Brief 1-2 sentence summary",
  "milestones": [
    {{
      "name": "Milestone name",
      "description": "What this milestone accomplishes",
      "estimated_duration": "X weeks",
      "tasks": [
        {{
          "name": "Task name",
          "description": "Detailed task description",
          "estimated_hours": 8,
          "dependencies": []
        }}
      ]
    }}
  ],
  "tech_stack": ["Technology1", "Technology2", "..."],
  "open_questions": ["Question 1?", "Question 2?"],
  "estimated_total_duration": "X-Y weeks"
}}

Focus on:
- Modern, industry-standard technologies
- Realistic time estimates
- Clear task descriptions
- Logical milestone progression
- MVP-first approach

Respond with ONLY the JSON object, no additional text:
"""

    def _parse_llm_response(self, response, specification: Dict[str, Any]) -> PlanningOutput:
        """Parse LLM response into PlanningOutput model."""
        content = response.content if hasattr(response, "content") else str(response)

        # Extract JSON from response
        try:
            # Find JSON block in response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start != -1 and end > start:
                json_str = content[start:end]
                plan_data = json.loads(json_str)

                # Validate and create PlanningOutput
                return PlanningOutput(**plan_data)

        except json.JSONDecodeError as e:
            print(f"⚠️  JSON parsing failed: {e}")
        except Exception as e:
            print(f"⚠️  Plan validation failed: {e}")

        # If parsing fails, use fallback
        print("🔄 Using fallback plan generation")
        return self._generate_plan_fallback(specification)

    def _generate_plan_fallback(self, specification: Dict[str, Any]) -> PlanningOutput:
        """Generate a simple plan without LLM."""
        title = specification.get("title", "Software Project")
        summary = specification.get("summary", "Software development project")
        features = specification.get("features", [])
        constraints = specification.get("constraints", [])
        tech_stack = specification.get("metadata", {}).get("tech_stack", [])

        # Generate basic milestones
        milestones = []

        # Milestone 1: Setup
        milestones.append(
            {
                "name": "Project Setup & Foundation",
                "description": "Initialize project structure and development environment",
                "estimated_duration": "1 week",
                "tasks": [
                    {
                        "name": "Repository setup",
                        "description": "Initialize git repository and project structure",
                        "estimated_hours": 4,
                        "dependencies": [],
                    },
                    {
                        "name": "Development environment",
                        "description": "Setup development tools and dependencies",
                        "estimated_hours": 8,
                        "dependencies": ["Repository setup"],
                    },
                ],
            }
        )

        # Milestone 2-4: Features (group features)
        if features:
            feature_groups = [features[i : i + 3] for i in range(0, len(features), 3)]
            for i, group in enumerate(feature_groups[:3]):
                milestone_tasks = []
                for feature in group:
                    feature_name = feature.get("name", f"Feature {i+1}")
                    feature_desc = feature.get("desc", feature_name)

                    # Create detailed task description for better dev agent code generation
                    detailed_desc = f"Implement {feature_name} functionality. {feature_desc}. "

                    # Add technology-specific implementation details
                    if any(tech.lower() in ["react", "vue", "angular"] for tech in tech_stack):
                        detailed_desc += "Create React components with proper state management, event handlers, and user interface elements. "
                    elif any(
                        tech.lower() in ["node.js", "express", "fastapi", "django"]
                        for tech in tech_stack
                    ):
                        detailed_desc += "Implement backend API endpoints with proper routing, validation, and database integration. "

                    detailed_desc += (
                        "Include error handling, input validation, and comprehensive unit tests."
                    )

                    milestone_tasks.append(
                        {
                            "name": f"Implement {feature_name}",
                            "description": detailed_desc,
                            "estimated_hours": 16,
                            "dependencies": [],
                        }
                    )

                milestones.append(
                    {
                        "name": f"Development Phase {i+1}",
                        "description": f"Implement core features: {', '.join([f.get('name', f'Feature {j+1}') for j, f in enumerate(group)])}",
                        "estimated_duration": "2-3 weeks",
                        "tasks": milestone_tasks,
                    }
                )

        # Milestone: Testing & Deployment
        milestones.append(
            {
                "name": "Testing & Deployment",
                "description": "Quality assurance, testing, and production deployment",
                "estimated_duration": "1-2 weeks",
                "tasks": [
                    {
                        "name": "Testing suite",
                        "description": "Implement comprehensive testing",
                        "estimated_hours": 16,
                        "dependencies": [],
                    },
                    {
                        "name": "Production deployment",
                        "description": "Deploy to production environment",
                        "estimated_hours": 8,
                        "dependencies": ["Testing suite"],
                    },
                ],
            }
        )

        # Basic tech stack inference
        if not tech_stack:
            if "web" in summary.lower() or "website" in summary.lower():
                tech_stack = ["React", "Node.js", "PostgreSQL"]
            elif "mobile" in summary.lower():
                tech_stack = ["React Native", "Node.js", "MongoDB"]
            else:
                tech_stack = ["Python", "FastAPI", "PostgreSQL"]

        # Generate open questions
        open_questions = []
        if not tech_stack:
            open_questions.append("What technology stack would you prefer?")
        if not constraints:
            open_questions.append("Are there any specific technical constraints or requirements?")
        open_questions.append("What is the expected launch timeline?")

        return PlanningOutput(
            project_title=title,
            project_summary=summary,
            milestones=milestones[:5],  # Ensure ≤5 milestones
            tech_stack=tech_stack,
            open_questions=open_questions,
            estimated_total_duration=f"{len(milestones) * 2}-{len(milestones) * 3} weeks",
        )

    def save_planning_output(self, planning_output: PlanningOutput) -> str:
        """Save planning output to disk."""
        # Create session directory
        self.session_dir.mkdir(parents=True, exist_ok=True)

        # Save main planning output
        output_path = self.session_dir / "planning_output.json"
        with open(output_path, "w") as f:
            json.dump(planning_output.model_dump(), f, indent=2)

        # Create summary file
        summary_path = self.session_dir / "README.md"
        with open(summary_path, "w") as f:
            f.write(self._generate_planning_summary(planning_output))

        return str(self.session_dir)

    def _generate_planning_summary(self, planning_output: PlanningOutput) -> str:
        """Generate planning summary README."""
        summary = f"""# Project Plan: {planning_output.project_title}

**Generated:** {datetime.now().isoformat()}
**Session ID:** {self.timestamp}

## Summary
{planning_output.project_summary}

**Estimated Duration:** {planning_output.estimated_total_duration}

## Technology Stack
{chr(10).join(f"- {tech}" for tech in planning_output.tech_stack)}

## Milestones

"""

        for i, milestone in enumerate(planning_output.milestones, 1):
            summary += f"### {i}. {milestone.name}\n"
            summary += f"**Duration:** {milestone.estimated_duration}\n\n"
            summary += f"{milestone.description}\n\n"
            summary += "**Tasks:**\n"
            for task in milestone.tasks:
                hours = f" ({task.estimated_hours}h)" if task.estimated_hours else ""
                summary += f"- {task.name}{hours}: {task.description}\n"
            summary += "\n"

        if planning_output.open_questions:
            summary += "## Open Questions\n\n"
            for question in planning_output.open_questions:
                summary += f"- {question}\n"

        return summary

    def plan_project(self, spec_path: str) -> str:
        """Complete planning workflow: load spec → generate plan → save output."""
        print("🔧 SoloPilot Project Planner")
        print("=" * 50)

        # Load specification
        print(f"📖 Loading specification: {spec_path}")
        specification = self.load_specification(spec_path)
        print(f"✅ Loaded: {specification.get('title', 'Untitled Project')}")

        # Generate plan
        print("🧠 Generating project plan...")
        planning_output = self.generate_plan(specification)
        print(f"✅ Generated plan with {len(planning_output.milestones)} milestones")

        # Save output
        print("💾 Saving planning output...")
        session_dir = self.save_planning_output(planning_output)

        print("=" * 50)
        print("📊 Planning complete!")
        print(f"📂 Output saved to: {session_dir}")
        print(f"🎯 Project: {planning_output.project_title}")
        print(f"📅 Duration: {planning_output.estimated_total_duration}")
        print(f"🏗️  Milestones: {len(planning_output.milestones)}")
        print(f"⚙️  Tech Stack: {', '.join(planning_output.tech_stack)}")

        return session_dir
