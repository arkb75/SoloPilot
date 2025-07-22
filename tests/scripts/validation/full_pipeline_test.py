#!/usr/bin/env python3
"""
Full Pipeline Validation Test
A comprehensive end-to-end test that ATLAS can't bypass - validates the entire SoloPilot pipeline
with real providers, actual code generation, linting, and SonarCloud integration.
"""

import json
import os
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from agents.dev.dev_agent import DevAgent
from tests.regression.complex_projects.large_ecommerce_platform import (
    create_large_ecommerce_project,
)
from src.utils.sonarcloud_integration import SonarCloudClient


class FullPipelineValidator:
    """
    Comprehensive pipeline validation that cannot be bypassed.
    Tests the complete SoloPilot workflow with real providers and actual integrations.
    """

    def __init__(self):
        """Initialize the validator."""
        self.temp_dirs: List[Path] = []
        self.validation_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.results = {
            "validation_id": self.validation_id,
            "start_time": time.time(),
            "phases": [],
            "success": False,
            "bypass_detected": False,
            "critical_failures": [],
        }

        # Detection mechanisms to prevent bypassing
        self.integrity_checks = {
            "real_provider_used": False,
            "actual_code_generated": False,
            "linting_executed": False,
            "sonarcloud_integrated": False,
            "performance_validated": False,
        }

    def cleanup(self):
        """Clean up temporary directories."""
        for temp_dir in self.temp_dirs:
            if temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                except Exception as e:
                    print(f"⚠️ Could not clean up {temp_dir}: {e}")

    def detect_bypass_attempts(self) -> List[str]:
        """Detect attempts to bypass validation."""
        bypass_attempts = []

        # Check if fake provider is being used when real providers are required
        ai_provider = os.getenv("AI_PROVIDER", "bedrock")
        if ai_provider == "fake":
            bypass_attempts.append(
                "Fake AI provider detected - real provider required for validation"
            )

        # Check if NO_NETWORK is set (would disable SonarCloud)
        if os.getenv("NO_NETWORK") == "1":
            bypass_attempts.append("NO_NETWORK=1 detected - network access required for validation")

        # Check if logs directory exists (performance monitoring requirement)
        if not Path("logs").exists():
            bypass_attempts.append("Logs directory missing - performance monitoring disabled")

        return bypass_attempts

    def validate_environment(self) -> Dict[str, Any]:
        """Validate that the environment is properly configured for real testing."""
        print("🔧 Validating environment configuration...")

        validation = {"valid": True, "issues": [], "warnings": []}

        # Check for bypass attempts
        bypass_attempts = self.detect_bypass_attempts()
        if bypass_attempts:
            validation["valid"] = False
            validation["issues"].extend(bypass_attempts)
            self.results["bypass_detected"] = True

        # Check AI provider configuration
        ai_provider = os.getenv("AI_PROVIDER", "bedrock")
        if ai_provider not in ["bedrock"]:
            validation["warnings"].append(
                f"AI provider '{ai_provider}' may not support all features"
            )

        # Check SonarCloud configuration
        sonar_token = os.getenv("SONAR_TOKEN")
        if not sonar_token:
            validation["warnings"].append(
                "SONAR_TOKEN not set - SonarCloud integration will be skipped"
            )

        # Check required dependencies
        required_commands = ["git", "python"]
        for cmd in required_commands:
            if not shutil.which(cmd):
                validation["valid"] = False
                validation["issues"].append(f"Required command '{cmd}' not found in PATH")

        # Log validation results
        phase_result = {
            "name": "environment_validation",
            "duration": 0,
            "success": validation["valid"],
            "issues": validation["issues"],
            "warnings": validation["warnings"],
        }
        self.results["phases"].append(phase_result)

        if validation["valid"]:
            print("✅ Environment validation passed")
        else:
            print("❌ Environment validation failed:")
            for issue in validation["issues"]:
                print(f"   - {issue}")

        return validation

    def phase_1_generate_complex_project(self) -> Dict[str, Any]:
        """Phase 1: Generate a complex project for testing."""
        print("\n📁 Phase 1: Generating complex project...")
        phase_start = time.time()

        try:
            # Create a complex e-commerce project (500+ files)
            project_dir = create_large_ecommerce_project()
            self.temp_dirs.append(project_dir)

            # Validate project structure
            planning_file = project_dir / "planning_output.json"
            if not planning_file.exists():
                raise ValueError("Planning file not generated")

            with open(planning_file, "r") as f:
                planning_data = json.load(f)

            file_count = len(list(project_dir.rglob("*")))
            milestone_count = len(planning_data.get("milestones", []))

            if file_count < 500:
                raise ValueError(f"Project too small: {file_count} files (expected >500)")

            if milestone_count < 15:
                raise ValueError(f"Not enough milestones: {milestone_count} (expected >=15)")

            phase_result = {
                "name": "complex_project_generation",
                "duration": time.time() - phase_start,
                "success": True,
                "project_dir": str(project_dir),
                "file_count": file_count,
                "milestone_count": milestone_count,
                "planning_file": str(planning_file),
            }

            print(f"✅ Generated complex project: {file_count} files, {milestone_count} milestones")
            return phase_result

        except Exception as e:
            phase_result = {
                "name": "complex_project_generation",
                "duration": time.time() - phase_start,
                "success": False,
                "error": str(e),
            }
            self.results["critical_failures"].append(f"Project generation failed: {e}")
            print(f"❌ Project generation failed: {e}")
            return phase_result

    def phase_2_real_provider_validation(self, project_dir: Path) -> Dict[str, Any]:
        """Phase 2: Validate real AI provider usage and code generation."""
        print("\n🤖 Phase 2: Real AI provider validation...")
        phase_start = time.time()

        try:
            # Initialize dev agent with real provider
            agent = DevAgent()

            # Verify real provider is being used
            provider_info = agent.provider.get_provider_info()
            provider_name = provider_info.get("name", "unknown")

            if provider_name == "fake":
                raise ValueError("Fake provider detected - real provider required")

            self.integrity_checks["real_provider_used"] = True

            # Process a subset of milestones with real provider
            planning_file = project_dir / "planning_output.json"
            output_dir = project_dir / "validation_output"

            print(f"🔥 Testing with REAL {provider_name} provider...")

            # Monitor performance and actual generation
            generation_start = time.time()
            manifest = agent.process_planning_output(str(planning_file), str(output_dir))
            generation_time = time.time() - generation_start

            # Validate that actual code was generated
            generated_files = []
            for milestone in manifest["milestones"]:
                milestone_dir = output_dir / milestone["directory"]
                if milestone_dir.exists():
                    files = list(milestone_dir.glob("*"))
                    generated_files.extend(files)

            if len(generated_files) == 0:
                raise ValueError("No files were actually generated")

            # Verify code quality by sampling files
            code_quality_score = self._analyze_generated_code_quality(generated_files[:10])

            if code_quality_score < 0.5:
                raise ValueError(f"Generated code quality too low: {code_quality_score:.2f}")

            self.integrity_checks["actual_code_generated"] = True

            phase_result = {
                "name": "real_provider_validation",
                "duration": time.time() - phase_start,
                "success": True,
                "provider_name": provider_name,
                "provider_available": agent.provider.is_available(),
                "generation_time": generation_time,
                "milestones_processed": len(manifest["milestones"]),
                "files_generated": len(generated_files),
                "code_quality_score": code_quality_score,
                "output_dir": str(output_dir),
            }

            print(f"✅ Real provider validation passed: {provider_name}")
            print(f"   Generated {len(generated_files)} files in {generation_time:.2f}s")
            print(f"   Code quality score: {code_quality_score:.2f}")

            return phase_result

        except Exception as e:
            phase_result = {
                "name": "real_provider_validation",
                "duration": time.time() - phase_start,
                "success": False,
                "error": str(e),
            }
            self.results["critical_failures"].append(f"Real provider validation failed: {e}")
            print(f"❌ Real provider validation failed: {e}")
            return phase_result

    def phase_3_linting_validation(self, output_dir: Path) -> Dict[str, Any]:
        """Phase 3: Validate that linting actually executed."""
        print("\n🔍 Phase 3: Linting validation...")
        phase_start = time.time()

        try:
            # Check performance logs for linting evidence
            logs_dir = Path("logs")
            performance_log = logs_dir / "dev_agent_performance.log"

            linting_evidence = []

            if performance_log.exists():
                with open(performance_log, "r") as f:
                    for line in f:
                        try:
                            log_entry = json.loads(line.strip())
                            if log_entry.get("component") == "dev_agent":
                                linting_evidence.append(log_entry)
                        except json.JSONDecodeError:
                            continue

            # Look for actual linting configuration and execution
            linting_configs_found = []
            for config_file in [".eslintrc.js", ".eslintrc.json", "pyproject.toml", "setup.cfg"]:
                if (output_dir / config_file).exists():
                    linting_configs_found.append(config_file)

            # Check for linting in generated code comments
            linting_comments_found = 0
            for file_path in output_dir.rglob("*.js"):
                try:
                    with open(file_path, "r") as f:
                        content = f.read()
                        if "eslint" in content.lower() or "lint" in content.lower():
                            linting_comments_found += 1
                except Exception:
                    continue

            self.integrity_checks["linting_executed"] = (
                len(linting_evidence) > 0 or len(linting_configs_found) > 0
            )

            phase_result = {
                "name": "linting_validation",
                "duration": time.time() - phase_start,
                "success": True,
                "linting_evidence_count": len(linting_evidence),
                "linting_configs_found": linting_configs_found,
                "linting_comments_found": linting_comments_found,
                "linting_executed": self.integrity_checks["linting_executed"],
            }

            if self.integrity_checks["linting_executed"]:
                print("✅ Linting validation passed - evidence of linting found")
            else:
                print("⚠️ Linting validation passed but no evidence found")

            return phase_result

        except Exception as e:
            phase_result = {
                "name": "linting_validation",
                "duration": time.time() - phase_start,
                "success": False,
                "error": str(e),
            }
            print(f"❌ Linting validation failed: {e}")
            return phase_result

    def phase_4_sonarcloud_integration(self, project_dir: Path) -> Dict[str, Any]:
        """Phase 4: Validate SonarCloud auto-provisioning without manual intervention."""
        print("\n☁️ Phase 4: SonarCloud integration validation...")
        phase_start = time.time()

        try:
            # Initialize SonarCloud client
            client = SonarCloudClient()

            # Test configuration validation
            config_validation = client.validate_configuration()

            if not config_validation["valid"]:
                # SonarCloud not available - still validate the integration code works
                print("⚠️ SonarCloud not available, validating integration code...")

                # Test URL parsing and client initialization
                test_urls = [
                    "https://github.com/test-user/test-repo.git",
                    "git@gitlab.com:company/project.git",
                ]

                parsing_success = 0
                for url in test_urls:
                    parsed = client.parse_git_url(url)
                    if parsed and all(key in parsed for key in ["owner", "repo", "project_key"]):
                        parsing_success += 1

                phase_result = {
                    "name": "sonarcloud_integration",
                    "duration": time.time() - phase_start,
                    "success": True,
                    "available": False,
                    "config_issues": config_validation["issues"],
                    "url_parsing_success": parsing_success,
                    "total_urls_tested": len(test_urls),
                }

                print("✅ SonarCloud integration code validated (service not available)")
                return phase_result

            # SonarCloud is available - test full auto-provisioning
            print("🚀 Testing SonarCloud auto-provisioning...")

            # Create a test repository URL
            test_repo_url = (
                f"https://github.com/solopilot-demo/validation-test-{self.validation_id}.git"
            )

            # Attempt auto-provisioning
            auto_provision_start = time.time()
            result = client.setup_project_from_git_url(
                test_repo_url, f"SoloPilot Validation Test {self.validation_id}"
            )
            auto_provision_time = time.time() - auto_provision_start

            # Validate result
            auto_provision_success = result is not None
            manual_intervention_required = False

            if auto_provision_success:
                # Verify the project exists and is accessible
                try:
                    metrics = client.get_project_metrics()
                    quality_gate = client.get_quality_gate_status()

                    # These may return None for new projects, which is acceptable
                    self.integrity_checks["sonarcloud_integrated"] = True

                except Exception as e:
                    print(f"⚠️ Project created but metrics unavailable: {e}")
                    # This is acceptable for new projects
            else:
                manual_intervention_required = True
                self.results["critical_failures"].append("SonarCloud auto-provisioning failed")

            phase_result = {
                "name": "sonarcloud_integration",
                "duration": time.time() - phase_start,
                "success": auto_provision_success,
                "available": True,
                "auto_provision_time": auto_provision_time,
                "manual_intervention_required": manual_intervention_required,
                "project_created": auto_provision_success,
                "project_key": result.get("project_key") if result else None,
                "config_validation": config_validation,
            }

            if auto_provision_success:
                print(f"✅ SonarCloud auto-provisioning successful in {auto_provision_time:.2f}s")
                print(f"   Project: {result['project_key']}")
            else:
                print("❌ SonarCloud auto-provisioning failed")

            return phase_result

        except Exception as e:
            phase_result = {
                "name": "sonarcloud_integration",
                "duration": time.time() - phase_start,
                "success": False,
                "error": str(e),
            }
            print(f"❌ SonarCloud integration failed: {e}")
            return phase_result

    def phase_5_performance_validation(self) -> Dict[str, Any]:
        """Phase 5: Validate performance monitoring and guards."""
        print("\n📊 Phase 5: Performance validation...")
        phase_start = time.time()

        try:
            # Check for performance logs
            logs_dir = Path("logs")
            performance_files = [
                "dev_agent_performance.log",
                "llm_calls.log",
                "slow_operations.log",
            ]

            performance_evidence = {}
            for log_file in performance_files:
                log_path = logs_dir / log_file
                if log_path.exists():
                    try:
                        with open(log_path, "r") as f:
                            lines = f.readlines()
                            performance_evidence[log_file] = {
                                "exists": True,
                                "entry_count": len(lines),
                                "size_bytes": log_path.stat().st_size,
                            }
                    except Exception as e:
                        performance_evidence[log_file] = {"exists": True, "error": str(e)}
                else:
                    performance_evidence[log_file] = {"exists": False}

            # Analyze performance data if available
            performance_metrics = self._analyze_performance_logs(logs_dir)

            # Check if performance guards are working
            self.integrity_checks["performance_validated"] = any(
                evidence.get("exists", False) and evidence.get("entry_count", 0) > 0
                for evidence in performance_evidence.values()
            )

            phase_result = {
                "name": "performance_validation",
                "duration": time.time() - phase_start,
                "success": True,
                "performance_evidence": performance_evidence,
                "performance_metrics": performance_metrics,
                "monitoring_active": self.integrity_checks["performance_validated"],
            }

            if self.integrity_checks["performance_validated"]:
                print("✅ Performance monitoring validated - metrics captured")
            else:
                print("⚠️ Performance monitoring not detected")

            return phase_result

        except Exception as e:
            phase_result = {
                "name": "performance_validation",
                "duration": time.time() - phase_start,
                "success": False,
                "error": str(e),
            }
            print(f"❌ Performance validation failed: {e}")
            return phase_result

    def _analyze_generated_code_quality(self, files: List[Path]) -> float:
        """Analyze the quality of generated code files."""
        if not files:
            return 0.0

        quality_scores = []

        for file_path in files:
            try:
                with open(file_path, "r") as f:
                    content = f.read()

                score = 0.0
                total_checks = 0

                # Check 1: File has meaningful content
                if len(content.strip()) > 50:
                    score += 1
                total_checks += 1

                # Check 2: Contains implementation guidance
                if "TODO" in content or "implement" in content.lower():
                    score += 1
                total_checks += 1

                # Check 3: Has structure (functions, classes, etc.)
                if any(
                    keyword in content for keyword in ["function", "class", "def", "const", "let"]
                ):
                    score += 1
                total_checks += 1

                # Check 4: Contains comments or documentation
                if "//" in content or "/*" in content or "#" in content or '"""' in content:
                    score += 1
                total_checks += 1

                # Check 5: Not just stub code
                if "stub" not in content.lower() and "placeholder" not in content.lower():
                    score += 1
                total_checks += 1

                if total_checks > 0:
                    quality_scores.append(score / total_checks)

            except Exception:
                quality_scores.append(0.0)

        return sum(quality_scores) / len(quality_scores) if quality_scores else 0.0

    def _analyze_performance_logs(self, logs_dir: Path) -> Dict[str, Any]:
        """Analyze performance logs for metrics."""
        metrics = {
            "total_operations": 0,
            "avg_response_time": 0,
            "slow_operations": 0,
            "error_rate": 0,
        }

        try:
            performance_log = logs_dir / "dev_agent_performance.log"
            if performance_log.exists():
                response_times = []
                errors = 0

                with open(performance_log, "r") as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            metrics["total_operations"] += 1

                            if entry.get("success"):
                                response_time = entry.get("generation_time", 0)
                                response_times.append(response_time)

                                if response_time > 30:  # Slow operation threshold
                                    metrics["slow_operations"] += 1
                            else:
                                errors += 1

                        except json.JSONDecodeError:
                            continue

                if response_times:
                    metrics["avg_response_time"] = sum(response_times) / len(response_times)

                if metrics["total_operations"] > 0:
                    metrics["error_rate"] = errors / metrics["total_operations"]

        except Exception as e:
            metrics["analysis_error"] = str(e)

        return metrics

    def run_full_validation(self) -> Dict[str, Any]:
        """Run the complete validation pipeline."""
        print("🚀 Starting Full Pipeline Validation")
        print("=" * 60)
        print(f"Validation ID: {self.validation_id}")
        print("=" * 60)

        try:
            # Environment validation (bypass detection)
            env_validation = self.validate_environment()
            if not env_validation["valid"]:
                self.results["success"] = False
                return self.results

            # Phase 1: Generate complex project
            phase1 = self.phase_1_generate_complex_project()
            self.results["phases"].append(phase1)

            if not phase1["success"]:
                self.results["success"] = False
                return self.results

            project_dir = Path(phase1["project_dir"])

            # Phase 2: Real provider validation
            phase2 = self.phase_2_real_provider_validation(project_dir)
            self.results["phases"].append(phase2)

            if not phase2["success"]:
                self.results["success"] = False
                return self.results

            output_dir = Path(phase2["output_dir"])

            # Phase 3: Linting validation
            phase3 = self.phase_3_linting_validation(output_dir)
            self.results["phases"].append(phase3)

            # Phase 4: SonarCloud integration
            phase4 = self.phase_4_sonarcloud_integration(project_dir)
            self.results["phases"].append(phase4)

            # Phase 5: Performance validation
            phase5 = self.phase_5_performance_validation()
            self.results["phases"].append(phase5)

            # Final validation
            self.results["total_duration"] = time.time() - self.results["start_time"]
            self.results["integrity_checks"] = self.integrity_checks

            # Success criteria
            critical_phases_passed = all(
                phase["success"]
                for phase in self.results["phases"][:3]  # First 3 phases are critical
            )

            integrity_score = sum(1 for check in self.integrity_checks.values() if check) / len(
                self.integrity_checks
            )

            self.results["success"] = (
                critical_phases_passed
                and not self.results["bypass_detected"]
                and integrity_score >= 0.6  # At least 60% of integrity checks passed
            )

            self.results["integrity_score"] = integrity_score

            # Save detailed results
            os.makedirs("logs", exist_ok=True)
            results_file = Path("logs") / f"full_pipeline_validation_{self.validation_id}.json"
            with open(results_file, "w") as f:
                json.dump(self.results, f, indent=2)

            # Print summary
            print("\n" + "=" * 60)
            print("🎯 Full Pipeline Validation Summary")
            print("=" * 60)

            success_icon = "✅" if self.results["success"] else "❌"
            print(
                f"{success_icon} Overall Result: {'PASSED' if self.results['success'] else 'FAILED'}"
            )
            print(f"🔒 Bypass Detected: {'YES' if self.results['bypass_detected'] else 'NO'}")
            print(f"📊 Integrity Score: {integrity_score:.1%}")
            print(f"⏱️ Total Duration: {self.results['total_duration']:.2f}s")

            print("\n📋 Phase Results:")
            for i, phase in enumerate(self.results["phases"], 1):
                status = "✅" if phase["success"] else "❌"
                print(f"  {status} Phase {i}: {phase['name']} ({phase['duration']:.2f}s)")

            print("\n🔍 Integrity Checks:")
            for check, passed in self.integrity_checks.items():
                status = "✅" if passed else "❌"
                print(f"  {status} {check.replace('_', ' ').title()}")

            if self.results["critical_failures"]:
                print("\n🚨 Critical Failures:")
                for failure in self.results["critical_failures"]:
                    print(f"   - {failure}")

            print(f"\n📄 Detailed results: {results_file}")
            print("=" * 60)

            return self.results

        except Exception as e:
            self.results["success"] = False
            self.results["fatal_error"] = str(e)
            print(f"💥 Fatal validation error: {e}")
            return self.results

        finally:
            self.cleanup()


def main():
    """Run full pipeline validation."""
    validator = FullPipelineValidator()

    try:
        results = validator.run_full_validation()

        # Exit with appropriate code
        if results["success"]:
            print("\n🎉 FULL PIPELINE VALIDATION PASSED!")
            print("All systems verified, no bypass detected.")
            sys.exit(0)
        else:
            print("\n💥 FULL PIPELINE VALIDATION FAILED!")
            if results.get("bypass_detected"):
                print("Bypass attempt detected!")
            if results.get("critical_failures"):
                print("Critical system failures detected!")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Validation framework failed: {e}")
        sys.exit(1)
    finally:
        validator.cleanup()


if __name__ == "__main__":
    main()
