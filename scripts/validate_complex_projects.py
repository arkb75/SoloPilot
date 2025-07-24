#!/usr/bin/env python3
"""
Complex Project Validation Script
Runs full pipeline validation with realistic complex projects.
"""

import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.dev.dev_agent import DevAgent
from tests.regression.complex_projects.enterprise_saas_platform import (
    create_enterprise_saas_project,
)
from tests.regression.complex_projects.large_ecommerce_platform import (
    create_large_ecommerce_project,
)


class ComplexProjectValidator:
    """Validates SoloPilot with complex, realistic projects."""

    def __init__(self):
        """Initialize the validator."""
        self.temp_dirs: List[Path] = []
        self.results: List[Dict[str, Any]] = []

    def cleanup(self):
        """Clean up temporary directories."""
        for temp_dir in self.temp_dirs:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def validate_complex_project(
        self, project_name: str, project_creator, target_time: int
    ) -> Dict[str, Any]:
        """Validate a complex project through the full pipeline."""
        print(f"\n🏗️ Validating {project_name}...")
        print("-" * 50)

        validation_start = time.time()
        result = {
            "project_name": project_name,
            "start_time": validation_start,
            "target_time": target_time,
            "phases": [],
        }

        try:
            # Phase 1: Generate complex project
            phase_start = time.time()
            print("📁 Phase 1: Generating complex project structure...")
            project_dir = project_creator()
            self.temp_dirs.append(project_dir)

            phase1_duration = time.time() - phase_start
            result["phases"].append(
                {
                    "name": "project_generation",
                    "duration": phase1_duration,
                    "success": True,
                    "files_created": len(list(project_dir.rglob("*"))),
                    "project_dir": str(project_dir),
                }
            )
            print(
                f"  ✅ Generated {result['phases'][-1]['files_created']} files in {phase1_duration:.2f}s"
            )

            # Phase 2: Run dev agent on complex project
            phase_start = time.time()
            print("🤖 Phase 2: Running dev agent on complex planning data...")

            planning_file = project_dir / "planning_output.json"
            output_dir = project_dir / "dev_output"

            agent = DevAgent()
            manifest = agent.process_planning_output(str(planning_file), str(output_dir))

            phase2_duration = time.time() - phase_start
            result["phases"].append(
                {
                    "name": "dev_agent_processing",
                    "duration": phase2_duration,
                    "success": True,
                    "milestones_processed": len(manifest["milestones"]),
                    "files_generated": len(manifest["milestones"])
                    * 3,  # implementation, test, readme
                }
            )
            print(
                f"  ✅ Processed {result['phases'][-1]['milestones_processed']} milestones in {phase2_duration:.2f}s"
            )

            # Phase 3: Validate generated output
            phase_start = time.time()
            print("🔍 Phase 3: Validating generated output quality...")

            validation_results = self._validate_generated_output(output_dir, manifest)

            phase3_duration = time.time() - phase_start
            result["phases"].append(
                {
                    "name": "output_validation",
                    "duration": phase3_duration,
                    "success": validation_results["success"],
                    **validation_results,
                }
            )
            print(f"  ✅ Validation completed in {phase3_duration:.2f}s")

            # Calculate overall results
            total_duration = time.time() - validation_start
            result.update(
                {
                    "total_duration": total_duration,
                    "within_target": total_duration <= target_time,
                    "success": all(phase["success"] for phase in result["phases"]),
                    "performance_score": self._calculate_performance_score(result, target_time),
                }
            )

            print(
                f"📊 Total Duration: {total_duration:.2f}s (Target: {target_time}s) "
                f"{'✅' if result['within_target'] else '⚠️'}"
            )
            print(f"🎯 Performance Score: {result['performance_score']:.1f}/100")

        except Exception as e:
            result.update(
                {
                    "success": False,
                    "error": str(e),
                    "total_duration": time.time() - validation_start,
                    "within_target": False,
                    "performance_score": 0,
                }
            )
            print(f"❌ Validation failed: {e}")

        return result

    def _validate_generated_output(
        self, output_dir: Path, manifest: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate the quality of generated output."""
        results = {"success": True, "checks": []}

        # Check 1: All milestone directories exist
        milestone_check = {"name": "milestone_directories", "success": True, "missing_dirs": []}

        for i, milestone in enumerate(manifest["milestones"], 1):
            milestone_dir = output_dir / f"milestone-{i}"
            if not milestone_dir.exists():
                milestone_check["success"] = False
                milestone_check["missing_dirs"].append(f"milestone-{i}")

        results["checks"].append(milestone_check)

        # Check 2: Required files exist in each milestone
        files_check = {"name": "required_files", "success": True, "missing_files": []}

        for i, milestone in enumerate(manifest["milestones"], 1):
            milestone_dir = output_dir / f"milestone-{i}"
            if milestone_dir.exists():
                required_files = ["implementation.js", "test.js", "README.md"]  # Default to JS
                for required_file in required_files:
                    file_path = milestone_dir / required_file
                    if not file_path.exists():
                        # Check for other extensions
                        found = False
                        for ext in [".ts", ".py", ".java"]:
                            alt_file = milestone_dir / (required_file.replace(".js", ext))
                            if alt_file.exists():
                                found = True
                                break

                        if not found:
                            files_check["success"] = False
                            files_check["missing_files"].append(f"milestone-{i}/{required_file}")

        results["checks"].append(files_check)

        # Check 3: File content quality
        content_check = {"name": "content_quality", "success": True, "issues": []}

        # Sample a few files for content validation
        sample_count = 0
        for i, milestone in enumerate(manifest["milestones"][:5], 1):  # Check first 5 milestones
            milestone_dir = output_dir / f"milestone-{i}"
            if milestone_dir.exists():
                for file_path in milestone_dir.glob("implementation.*"):
                    try:
                        with open(file_path, "r") as f:
                            content = f.read()

                        # Basic content validation
                        if len(content) < 100:
                            content_check["success"] = False
                            content_check["issues"].append(f"{file_path.name} too short")
                        elif "TODO" not in content and "implement" not in content.lower():
                            content_check["issues"].append(
                                f"{file_path.name} lacks implementation guidance"
                            )

                        sample_count += 1
                        if sample_count >= 10:  # Limit sampling
                            break
                    except Exception as e:
                        content_check["success"] = False
                        content_check["issues"].append(f"{file_path.name} read error: {e}")

            if sample_count >= 10:
                break

        results["checks"].append(content_check)

        # Check 4: Manifest integrity
        manifest_check = {"name": "manifest_integrity", "success": True, "issues": []}

        if not manifest.get("project_title"):
            manifest_check["success"] = False
            manifest_check["issues"].append("Missing project title")

        if not manifest.get("milestones"):
            manifest_check["success"] = False
            manifest_check["issues"].append("No milestones in manifest")

        if len(manifest.get("tech_stack", [])) == 0:
            manifest_check["issues"].append("No tech stack specified")

        results["checks"].append(manifest_check)

        # Overall success
        results["success"] = all(check["success"] for check in results["checks"])
        results["total_checks"] = len(results["checks"])
        results["passed_checks"] = sum(1 for check in results["checks"] if check["success"])

        return results

    def _calculate_performance_score(self, result: Dict[str, Any], target_time: int) -> float:
        """Calculate performance score based on various factors."""
        score = 100.0

        # Time penalty
        if result.get("total_duration", 0) > target_time:
            time_penalty = min(50, (result["total_duration"] - target_time) / target_time * 50)
            score -= time_penalty

        # Success bonus/penalty
        if not result.get("success", False):
            score -= 30

        # Phase success penalties
        for phase in result.get("phases", []):
            if not phase.get("success", False):
                score -= 15

        # Output quality penalties
        validation_phase = next(
            (p for p in result.get("phases", []) if p["name"] == "output_validation"), None
        )
        if validation_phase:
            failed_checks = validation_phase.get("total_checks", 0) - validation_phase.get(
                "passed_checks", 0
            )
            score -= failed_checks * 5

        return max(0, score)

    def run_all_validations(self) -> Dict[str, Any]:
        """Run validation on all complex projects."""
        print("🚀 Starting Complex Project Validation Suite")
        print("=" * 60)

        validation_start = time.time()

        # Define test projects
        test_projects = [
            {
                "name": "Large E-commerce Platform",
                "creator": create_large_ecommerce_project,
                "target_time": 300,  # 5 minutes
            },
            {
                "name": "Enterprise SaaS Platform",
                "creator": create_enterprise_saas_project,
                "target_time": 420,  # 7 minutes
            },
        ]

        try:
            all_results = {
                "validation_suite": "complex_projects",
                "start_time": validation_start,
                "projects": [],
            }

            # Run validation for each project
            for project_config in test_projects:
                try:
                    result = self.validate_complex_project(
                        project_config["name"],
                        project_config["creator"],
                        project_config["target_time"],
                    )
                    all_results["projects"].append(result)
                except Exception as e:
                    error_result = {
                        "project_name": project_config["name"],
                        "success": False,
                        "error": str(e),
                        "total_duration": 0,
                        "within_target": False,
                        "performance_score": 0,
                    }
                    all_results["projects"].append(error_result)
                    print(f"❌ {project_config['name']} validation failed: {e}")

            # Calculate overall results
            all_results["total_duration"] = time.time() - validation_start
            all_results["success_count"] = sum(
                1 for p in all_results["projects"] if p.get("success", False)
            )
            all_results["total_count"] = len(all_results["projects"])
            all_results["avg_performance_score"] = sum(
                p.get("performance_score", 0) for p in all_results["projects"]
            ) / len(all_results["projects"])
            all_results["within_target_count"] = sum(
                1 for p in all_results["projects"] if p.get("within_target", False)
            )

            # Save results
            os.makedirs("logs", exist_ok=True)
            results_file = Path("logs") / "complex_project_validation_results.json"
            with open(results_file, "w") as f:
                json.dump(all_results, f, indent=2)

            print("\n" + "=" * 60)
            print("🎯 Validation Complete:")
            print(
                f"  ✅ Successful Projects: {all_results['success_count']}/{all_results['total_count']}"
            )
            print(
                f"  ⏱️ Within Target Time: {all_results['within_target_count']}/{all_results['total_count']}"
            )
            print(f"  📊 Average Performance Score: {all_results['avg_performance_score']:.1f}/100")
            print(f"  ⏱️ Total Duration: {all_results['total_duration']:.2f}s")
            print(f"  📄 Results saved: {results_file}")

            return all_results

        finally:
            self.cleanup()


def main():
    """Run complex project validation."""
    # Set environment for testing
    os.environ["AI_PROVIDER"] = os.getenv("AI_PROVIDER", "fake")  # Use fake by default for testing

    validator = ComplexProjectValidator()
    try:
        results = validator.run_all_validations()

        # Exit with appropriate code
        if (
            results["success_count"] == results["total_count"]
            and results["within_target_count"] >= results["total_count"] * 0.8
        ):
            print("✅ All complex project validations passed!")
            sys.exit(0)
        else:
            print("⚠️ Some validations failed or exceeded target times!")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Validation suite failed: {e}")
        sys.exit(1)
    finally:
        validator.cleanup()


if __name__ == "__main__":
    main()
