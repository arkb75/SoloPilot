#!/usr/bin/env python3
"""
Performance Benchmark Suite for SoloPilot
Tests timeout behavior, performance guardrails, and complex project handling.
"""

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from agents.dev.dev_agent import DevAgent


class PerformanceBenchmark:
    """Performance benchmark test suite."""

    def __init__(self):
        """Initialize benchmark suite."""
        self.results: List[Dict[str, Any]] = []
        self.temp_dirs: List[Path] = []

    def cleanup(self):
        """Clean up temporary directories."""
        for temp_dir in self.temp_dirs:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)

    def create_complex_planning_data(self, milestone_count: int = 10) -> Dict[str, Any]:
        """Create complex planning data for stress testing."""
        milestones = []

        for i in range(milestone_count):
            milestone = {
                "name": f"Complex Milestone {i+1}",
                "description": "Implement a complex feature with multiple components, integrations, and dependencies. This milestone requires careful planning, multiple API integrations, complex business logic, error handling, logging, monitoring, testing, and documentation. The implementation should follow enterprise patterns and be production-ready with proper security, performance optimizations, and scalability considerations.",
                "estimated_duration": "2-3 weeks",
                "tasks": [],
            }

            # Add many tasks to make prompts complex
            for j in range(5):
                task = {
                    "name": f"Complex Task {j+1}",
                    "description": "Implement complex functionality including API design, database schema creation, business logic implementation, validation rules, error handling strategies, logging frameworks, monitoring dashboards, comprehensive test suites, performance optimization, security measures, and detailed documentation with examples and best practices.",
                    "estimated_hours": 16 + j * 4,
                }
                milestone["tasks"].append(task)

            milestones.append(milestone)

        return {
            "project_title": "Complex Enterprise Application",
            "tech_stack": [
                "React",
                "Node.js",
                "TypeScript",
                "PostgreSQL",
                "Redis",
                "Docker",
                "AWS",
                "Jest",
                "ESLint",
            ],
            "milestones": milestones,
        }

    def test_timeout_behavior(self) -> Dict[str, Any]:
        """Test timeout behavior with different provider configurations."""
        print("🕐 Testing timeout behavior...")

        results = {"test_name": "timeout_behavior", "start_time": time.time(), "scenarios": []}

        # Test different timeout scenarios
        timeout_scenarios = [
            {"name": "fast_timeout", "timeout": 5, "expected": "timeout"},
            {"name": "standard_timeout", "timeout": 15, "expected": "success"},
            {"name": "extended_timeout", "timeout": 30, "expected": "success"},
        ]

        agent = DevAgent()

        for scenario in timeout_scenarios:
            scenario_start = time.time()

            try:
                # Use fake provider for predictable testing
                if os.getenv("AI_PROVIDER") != "fake":
                    os.environ["AI_PROVIDER"] = "fake"
                    agent = DevAgent()  # Reinitialize with fake provider

                prompt = "Generate a simple JavaScript function with comprehensive documentation and tests."
                result = agent._call_llm(prompt, timeout=scenario["timeout"])

                scenario_result = {
                    "scenario": scenario["name"],
                    "timeout": scenario["timeout"],
                    "duration": time.time() - scenario_start,
                    "success": True,
                    "result_length": len(result) if result else 0,
                }

            except Exception as e:
                scenario_result = {
                    "scenario": scenario["name"],
                    "timeout": scenario["timeout"],
                    "duration": time.time() - scenario_start,
                    "success": False,
                    "error": str(e),
                }

            results["scenarios"].append(scenario_result)
            print(f"  ✓ {scenario['name']}: {scenario_result['duration']:.2f}s")

        results["total_duration"] = time.time() - results["start_time"]
        return results

    def test_complex_project_performance(self) -> Dict[str, Any]:
        """Test performance with complex project structures."""
        print("🏗️ Testing complex project performance...")

        results = {
            "test_name": "complex_project_performance",
            "start_time": time.time(),
            "project_sizes": [],
        }

        # Test different project complexities
        complexities = [
            {"name": "small", "milestones": 3, "target_time": 30},
            {"name": "medium", "milestones": 7, "target_time": 60},
            {"name": "large", "milestones": 15, "target_time": 120},
        ]

        for complexity in complexities:
            complexity_start = time.time()

            try:
                # Create complex planning data
                planning_data = self.create_complex_planning_data(complexity["milestones"])

                # Create temporary planning file
                temp_dir = Path(tempfile.mkdtemp(prefix="benchmark_"))
                self.temp_dirs.append(temp_dir)
                planning_file = temp_dir / "planning_output.json"

                with open(planning_file, "w") as f:
                    json.dump(planning_data, f, indent=2)

                # Test dev agent processing
                agent = DevAgent()
                manifest = agent.process_planning_output(
                    str(planning_file), str(temp_dir / "output")
                )

                complexity_result = {
                    "complexity": complexity["name"],
                    "milestone_count": complexity["milestones"],
                    "duration": time.time() - complexity_start,
                    "target_time": complexity["target_time"],
                    "success": True,
                    "generated_files": len(manifest["milestones"])
                    * 3,  # implementation, test, readme
                    "within_target": (time.time() - complexity_start) <= complexity["target_time"],
                }

            except Exception as e:
                complexity_result = {
                    "complexity": complexity["name"],
                    "milestone_count": complexity["milestones"],
                    "duration": time.time() - complexity_start,
                    "target_time": complexity["target_time"],
                    "success": False,
                    "error": str(e),
                    "within_target": False,
                }

            results["project_sizes"].append(complexity_result)
            print(
                f"  ✓ {complexity['name']} ({complexity['milestones']} milestones): "
                f"{complexity_result['duration']:.2f}s {'✓' if complexity_result['within_target'] else '⚠️'}"
            )

        results["total_duration"] = time.time() - results["start_time"]
        return results

    def test_performance_logging(self) -> Dict[str, Any]:
        """Test that performance logging is working correctly."""
        print("📊 Testing performance logging...")

        results = {"test_name": "performance_logging", "start_time": time.time()}

        # Clear existing logs
        logs_dir = Path("logs")
        if logs_dir.exists():
            for log_file in ["dev_agent_performance.log", "slow_operations.log", "llm_calls.log"]:
                log_path = logs_dir / log_file
                if log_path.exists():
                    log_path.unlink()

        try:
            agent = DevAgent()

            # Generate some operations to trigger logging
            for i in range(3):
                prompt = f"Generate test code for iteration {i+1} with comprehensive documentation."
                result = agent._call_llm(prompt)

            # Check if logs were created
            performance_log = logs_dir / "dev_agent_performance.log"
            llm_calls_log = logs_dir / "llm_calls.log"

            results.update(
                {
                    "success": True,
                    "performance_log_exists": performance_log.exists(),
                    "llm_calls_log_exists": llm_calls_log.exists(),
                    "performance_log_entries": 0,
                    "llm_calls_entries": 0,
                }
            )

            # Count log entries
            if performance_log.exists():
                with open(performance_log, "r") as f:
                    results["performance_log_entries"] = len(f.readlines())

            if llm_calls_log.exists():
                with open(llm_calls_log, "r") as f:
                    results["llm_calls_entries"] = len(f.readlines())

            print(f"  ✓ Performance log entries: {results['performance_log_entries']}")
            print(f"  ✓ LLM calls log entries: {results['llm_calls_entries']}")

        except Exception as e:
            results.update({"success": False, "error": str(e)})

        results["total_duration"] = time.time() - results["start_time"]
        return results

    def test_memory_usage(self) -> Dict[str, Any]:
        """Test memory usage patterns during complex operations."""
        print("💾 Testing memory usage patterns...")

        try:
            import psutil
        except ImportError:
            return {"test_name": "memory_usage", "skipped": True, "reason": "psutil not available"}

        results = {"test_name": "memory_usage", "start_time": time.time(), "memory_snapshots": []}

        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        results["memory_snapshots"].append(
            {"phase": "initial", "memory_mb": initial_memory, "timestamp": time.time()}
        )

        try:
            # Create large planning data
            planning_data = self.create_complex_planning_data(20)

            # Snapshot after data creation
            memory_after_data = process.memory_info().rss / 1024 / 1024
            results["memory_snapshots"].append(
                {
                    "phase": "after_data_creation",
                    "memory_mb": memory_after_data,
                    "timestamp": time.time(),
                }
            )

            # Process with dev agent
            temp_dir = Path(tempfile.mkdtemp(prefix="memory_test_"))
            self.temp_dirs.append(temp_dir)
            planning_file = temp_dir / "planning_output.json"

            with open(planning_file, "w") as f:
                json.dump(planning_data, f, indent=2)

            agent = DevAgent()
            manifest = agent.process_planning_output(str(planning_file), str(temp_dir / "output"))

            # Final memory snapshot
            final_memory = process.memory_info().rss / 1024 / 1024
            results["memory_snapshots"].append(
                {"phase": "after_processing", "memory_mb": final_memory, "timestamp": time.time()}
            )

            results.update(
                {
                    "success": True,
                    "memory_increase_mb": final_memory - initial_memory,
                    "peak_memory_mb": max(
                        snapshot["memory_mb"] for snapshot in results["memory_snapshots"]
                    ),
                }
            )

            print(
                f"  ✓ Memory usage: {initial_memory:.1f} MB → {final_memory:.1f} MB "
                f"(+{final_memory - initial_memory:.1f} MB)"
            )

        except Exception as e:
            results.update({"success": False, "error": str(e)})

        results["total_duration"] = time.time() - results["start_time"]
        return results

    def run_all_benchmarks(self) -> Dict[str, Any]:
        """Run all performance benchmarks."""
        print("🚀 Starting Performance Benchmark Suite")
        print("=" * 50)

        benchmark_start = time.time()

        try:
            # Run all benchmark tests
            all_results = {
                "benchmark_suite": "solopilot_performance",
                "start_time": benchmark_start,
                "tests": [],
            }

            tests = [
                self.test_timeout_behavior,
                self.test_complex_project_performance,
                self.test_performance_logging,
                self.test_memory_usage,
            ]

            for test_func in tests:
                try:
                    result = test_func()
                    all_results["tests"].append(result)
                except Exception as e:
                    error_result = {
                        "test_name": test_func.__name__,
                        "success": False,
                        "error": str(e),
                        "duration": 0,
                    }
                    all_results["tests"].append(error_result)
                    print(f"  ❌ {test_func.__name__} failed: {e}")

            all_results["total_duration"] = time.time() - benchmark_start
            all_results["success_count"] = sum(
                1 for test in all_results["tests"] if test.get("success", False)
            )
            all_results["total_count"] = len(all_results["tests"])

            # Save results
            os.makedirs("logs", exist_ok=True)
            results_file = Path("logs") / "performance_benchmark_results.json"
            with open(results_file, "w") as f:
                json.dump(all_results, f, indent=2)

            print("\n" + "=" * 50)
            print(
                f"🎯 Benchmark Complete: {all_results['success_count']}/{all_results['total_count']} tests passed"
            )
            print(f"⏱️ Total Duration: {all_results['total_duration']:.2f}s")
            print(f"📄 Results saved: {results_file}")

            return all_results

        finally:
            self.cleanup()


def main():
    """Run performance benchmarks."""
    benchmark = PerformanceBenchmark()
    try:
        results = benchmark.run_all_benchmarks()

        # Exit with appropriate code
        if results["success_count"] == results["total_count"]:
            print("✅ All benchmarks passed!")
            sys.exit(0)
        else:
            print(f"⚠️ {results['total_count'] - results['success_count']} benchmarks failed!")
            sys.exit(1)

    except Exception as e:
        print(f"❌ Benchmark suite failed: {e}")
        sys.exit(1)
    finally:
        benchmark.cleanup()


if __name__ == "__main__":
    main()
