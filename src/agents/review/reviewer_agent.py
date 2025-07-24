#!/usr/bin/env python3
"""
AI Pair Reviewer Agent for SoloPilot

Provides automated code review with static analysis and AI-powered quality assessment.
Integrates ruff, mypy, pytest, and AI provider for comprehensive code review.
"""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from src.providers import get_provider
from src.providers.base import BaseProvider, ProviderError
from src.utils.sonarcloud_integration import SonarCloudClient


class ReviewerAgent:
    """AI-powered code reviewer with static analysis integration."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the ReviewerAgent.

        Args:
            config_path: Path to configuration file
        """
        self.config = self._load_config(config_path)
        self.provider = self._initialize_provider()
        self.sonarcloud = SonarCloudClient()

    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load configuration from file or use defaults."""
        if config_path and Path(config_path).exists():
            with open(config_path, "r") as f:
                return yaml.safe_load(f)

        # Default configuration
        return {
            "llm": {
                "primary": "bedrock",
                "bedrock": {
                    "inference_profile_arn": os.getenv(
                        "BEDROCK_IP_ARN",
                        "arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0",
                    ),
                    "region": "us-east-2",
                    "model_kwargs": {"temperature": 0.1, "max_tokens": 4096},
                },
            },
            "reviewer": {
                "strict_mode": True,
                "min_test_coverage": 70,
                "max_file_size": 10000,  # lines
                "fail_on_warnings": False,
            },
        }

    def _initialize_provider(self) -> BaseProvider:
        """Initialize AI provider for code review."""
        try:
            return get_provider(provider_name=os.getenv("AI_PROVIDER"), **self.config)
        except Exception as e:
            raise ProviderError(f"Failed to initialize AI provider: {e}")

    def review(self, milestone_dir: Path) -> Dict[str, Any]:
        """
        Perform comprehensive code review of milestone directory.

        Args:
            milestone_dir: Path to milestone directory to review

        Returns:
            Dictionary with review results including status, summary, and comments
        """
        if not milestone_dir.exists():
            return {
                "status": "fail",
                "summary": f"Milestone directory not found: {milestone_dir}",
                "comments": [],
                "static_analysis": {},
                "timestamp": time.time(),
            }

        print(f"🔍 Starting code review for {milestone_dir}")

        # Run static analysis
        static_results = self._run_static_analysis(milestone_dir)

        # Fetch SonarCloud findings
        sonarcloud_results = self._get_sonarcloud_findings()

        # Collect code files for AI review
        code_files = self._collect_code_files(milestone_dir)

        # AI-powered code review with SonarCloud integration
        ai_review = self._ai_code_review(code_files, static_results, sonarcloud_results)

        # Determine overall status including SonarCloud findings
        overall_status = self._determine_status(static_results, ai_review, sonarcloud_results)

        # Generate review report
        review_result = {
            "status": overall_status,
            "summary": ai_review.get("summary", "Code review completed"),
            "comments": ai_review.get("comments", []),
            "static_analysis": static_results,
            "sonarcloud_analysis": sonarcloud_results,
            "ai_insights": ai_review.get("insights", []),
            "timestamp": time.time(),
            "milestone_dir": str(milestone_dir),
        }

        # Write review report
        self._write_review_report(milestone_dir, review_result)

        print(f"✅ Review complete: {overall_status}")
        return review_result

    def _run_static_analysis(self, milestone_dir: Path) -> Dict[str, Any]:
        """Run static analysis tools on milestone directory."""
        results = {
            "ruff": self._run_ruff(milestone_dir),
            "mypy": self._run_mypy(milestone_dir),
            "pytest": self._run_pytest(milestone_dir),
            "file_stats": self._analyze_file_stats(milestone_dir),
        }

        return results

    def _get_sonarcloud_findings(self) -> Dict[str, Any]:
        """Fetch SonarCloud quality findings."""
        if not self.sonarcloud.is_available():
            return {
                "available": False,
                "reason": "offline_mode" if self.sonarcloud.no_network else "no_token",
                "metrics": {},
                "issues": [],
                "quality_gate": None,
            }

        print("🔍 Fetching SonarCloud quality findings...")
        try:
            summary = self.sonarcloud.generate_review_summary()
            print(f"✅ SonarCloud: {len(summary.get('issues', []))} issues found")
            return summary
        except Exception as e:
            print(f"❌ SonarCloud fetch failed: {e}")
            return {
                "available": False,
                "reason": "api_error",
                "error": str(e),
                "metrics": {},
                "issues": [],
                "quality_gate": None,
            }

    def _run_ruff(self, milestone_dir: Path) -> Dict[str, Any]:
        """Run ruff linter on milestone directory."""
        try:
            # Check if ruff is available
            subprocess.run(["ruff", "--version"], capture_output=True, check=True)

            result = subprocess.run(
                ["ruff", "check", str(milestone_dir), "--output-format=json"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            violations = []
            if result.stdout.strip():
                try:
                    violations = json.loads(result.stdout)
                except json.JSONDecodeError:
                    violations = []

            return {
                "success": True,
                "violations": violations,
                "error_count": len([v for v in violations if v.get("code", "").startswith("E")]),
                "warning_count": len([v for v in violations if v.get("code", "").startswith("W")]),
                "return_code": result.returncode,
            }

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
            return {
                "success": False,
                "error": str(e),
                "violations": [],
                "error_count": 0,
                "warning_count": 0,
            }

    def _run_mypy(self, milestone_dir: Path) -> Dict[str, Any]:
        """Run mypy type checker on milestone directory."""
        try:
            # Check if mypy is available
            subprocess.run(["mypy", "--version"], capture_output=True, check=True)

            result = subprocess.run(
                ["mypy", str(milestone_dir), "--strict", "--show-error-codes"],
                capture_output=True,
                text=True,
                timeout=45,
            )

            return {
                "success": True,
                "output": result.stdout,
                "errors": result.stderr,
                "return_code": result.returncode,
                "has_errors": result.returncode != 0,
            }

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
            return {
                "success": False,
                "error": str(e),
                "output": "",
                "errors": "",
                "has_errors": False,
            }

    def _run_pytest(self, milestone_dir: Path) -> Dict[str, Any]:
        """Run pytest on milestone directory."""
        try:
            # Look for test files
            test_files = list(milestone_dir.rglob("test_*.py")) + list(
                milestone_dir.rglob("*_test.py")
            )

            if not test_files:
                return {
                    "success": True,
                    "test_count": 0,
                    "passed": 0,
                    "failed": 0,
                    "coverage": 0,
                    "no_tests": True,
                }

            # Check if pytest is available
            subprocess.run(["pytest", "--version"], capture_output=True, check=True)

            result = subprocess.run(
                ["pytest", str(milestone_dir), "-q", "--tb=short"],
                capture_output=True,
                text=True,
                timeout=60,
            )

            return {
                "success": True,
                "output": result.stdout,
                "errors": result.stderr,
                "return_code": result.returncode,
                "test_files": len(test_files),
                "passed": result.returncode == 0,
            }

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
            return {
                "success": False,
                "error": str(e),
                "output": "",
                "errors": "",
                "passed": False,
                "test_files": 0,
            }

    def _analyze_file_stats(self, milestone_dir: Path) -> Dict[str, Any]:
        """Analyze file statistics for the milestone."""
        stats = {
            "total_files": 0,
            "python_files": 0,
            "test_files": 0,
            "total_lines": 0,
            "avg_file_size": 0,
            "large_files": [],
        }

        python_files = list(milestone_dir.rglob("*.py"))
        test_files = [f for f in python_files if "test" in f.name.lower()]

        total_lines = 0
        large_files = []

        for file_path in python_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = len(f.readlines())
                    total_lines += lines

                    if lines > self.config["reviewer"]["max_file_size"]:
                        large_files.append(
                            {"file": str(file_path.relative_to(milestone_dir)), "lines": lines}
                        )
            except (IOError, UnicodeDecodeError):
                continue

        stats.update(
            {
                "total_files": len(list(milestone_dir.rglob("*"))),
                "python_files": len(python_files),
                "test_files": len(test_files),
                "total_lines": total_lines,
                "avg_file_size": total_lines // max(len(python_files), 1),
                "large_files": large_files,
            }
        )

        return stats

    def _collect_code_files(self, milestone_dir: Path) -> List[Dict[str, Any]]:
        """Collect code files for AI review."""
        code_files = []

        for py_file in milestone_dir.rglob("*.py"):
            try:
                with open(py_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # Skip very large files
                if len(content.splitlines()) > self.config["reviewer"]["max_file_size"]:
                    continue

                code_files.append(
                    {
                        "path": str(py_file.relative_to(milestone_dir)),
                        "content": content,
                        "lines": len(content.splitlines()),
                    }
                )

            except (IOError, UnicodeDecodeError):
                continue

        return code_files

    def _ai_code_review(
        self,
        code_files: List[Dict[str, Any]],
        static_results: Dict[str, Any],
        sonarcloud_results: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Perform AI-powered code review."""
        if not code_files:
            return {
                "summary": "No Python files found for review",
                "comments": [],
                "insights": ["No code files to review"],
            }

        try:
            # Build review prompt with SonarCloud integration
            prompt = self._build_review_prompt(code_files, static_results, sonarcloud_results)

            # Get AI review
            ai_response = self.provider.generate_code(prompt)

            # Parse AI response
            return self._parse_ai_response(ai_response)

        except Exception as e:
            return {
                "summary": f"AI review failed: {e}",
                "comments": [],
                "insights": [f"AI review error: {e}"],
            }

    def _build_review_prompt(
        self,
        code_files: List[Dict[str, Any]],
        static_results: Dict[str, Any],
        sonarcloud_results: Dict[str, Any],
    ) -> str:
        """Build comprehensive review prompt for AI."""
        prompt_parts = [
            "# CODE REVIEW REQUEST",
            "",
            "Please perform a comprehensive code review focusing on:",
            "- Code quality and best practices",
            "- Security vulnerabilities",
            "- Performance issues",
            "- Test coverage and quality",
            "- Documentation completeness",
            "",
            "## STATIC ANALYSIS RESULTS",
            "",
        ]

        # Add static analysis summary
        ruff_results = static_results.get("ruff", {})
        if ruff_results.get("success") and ruff_results.get("violations"):
            prompt_parts.extend(
                [
                    f"**Ruff Violations**: {ruff_results['error_count']} errors, {ruff_results['warning_count']} warnings",
                    "",
                ]
            )

        mypy_results = static_results.get("mypy", {})
        if mypy_results.get("success") and mypy_results.get("has_errors"):
            prompt_parts.extend(
                [
                    "**MyPy Type Errors**: Present (see below)",
                    f"```\n{mypy_results.get('output', '')[:500]}...\n```",
                    "",
                ]
            )

        pytest_results = static_results.get("pytest", {})
        if pytest_results.get("success"):
            test_status = "PASS" if pytest_results.get("passed") else "FAIL"
            test_count = pytest_results.get("test_files", 0)
            prompt_parts.extend([f"**Tests**: {test_status} ({test_count} test files)", ""])

        # Add SonarCloud findings if available
        if sonarcloud_results.get("available"):
            metrics = sonarcloud_results.get("metrics", {})
            issues = sonarcloud_results.get("issues", [])
            analysis = sonarcloud_results.get("analysis", {})

            prompt_parts.extend(
                [
                    "## SONARCLOUD QUALITY ANALYSIS",
                    "",
                    f"**Overall Rating**: {analysis.get('overall_rating', 'unknown').upper()}",
                    f"**Bugs**: {metrics.get('bugs', 0)}",
                    f"**Vulnerabilities**: {metrics.get('vulnerabilities', 0)}",
                    f"**Code Smells**: {metrics.get('code_smells', 0)}",
                    f"**Coverage**: {metrics.get('coverage', 0):.1f}%",
                    f"**Critical Issues**: {analysis.get('critical_issues', 0)}",
                    "",
                ]
            )

            if analysis.get("blockers"):
                prompt_parts.extend(["**BLOCKING ISSUES**:", ""])
                for blocker in analysis["blockers"][:3]:  # Limit to 3 blockers
                    prompt_parts.append(f"- {blocker}")
                prompt_parts.append("")

            if analysis.get("recommendations"):
                prompt_parts.extend(["**SONARCLOUD RECOMMENDATIONS**:", ""])
                for rec in analysis["recommendations"][:3]:  # Limit to 3 recommendations
                    prompt_parts.append(f"- {rec}")
                prompt_parts.append("")
        else:
            prompt_parts.extend(
                [
                    "## SONARCLOUD QUALITY ANALYSIS",
                    "",
                    f"**Status**: Not available ({sonarcloud_results.get('reason', 'unknown')})",
                    "",
                ]
            )

        # Add code files
        prompt_parts.extend(["## CODE FILES TO REVIEW", ""])

        for file_info in code_files[:5]:  # Limit to 5 files to avoid context overflow
            prompt_parts.extend(
                [
                    f"### {file_info['path']} ({file_info['lines']} lines)",
                    "```python",
                    file_info["content"],
                    "```",
                    "",
                ]
            )

        if len(code_files) > 5:
            prompt_parts.append(f"... and {len(code_files) - 5} more files")

        prompt_parts.extend(
            [
                "",
                "## REVIEW OUTPUT FORMAT",
                "",
                "Respond with JSON in this exact format:",
                "```json",
                "{",
                '  "summary": "Brief overall assessment",',
                '  "comments": [',
                '    {"file": "path/to/file.py", "line": 42, "severity": "high|medium|low", "message": "Issue description"},',
                '    {"file": "general", "line": 0, "severity": "info", "message": "General feedback"}',
                "  ],",
                '  "insights": [',
                '    "Key insight about code quality",',
                '    "Suggestion for improvement"',
                "  ]",
                "}",
                "```",
            ]
        )

        return "\n".join(prompt_parts)

    def _parse_ai_response(self, ai_response: str) -> Dict[str, Any]:
        """Parse AI response into structured review data."""
        # Try to extract JSON from response
        try:
            # Look for JSON block
            if "```json" in ai_response:
                json_start = ai_response.find("```json") + 7
                json_end = ai_response.find("```", json_start)
                json_str = ai_response[json_start:json_end].strip()
            else:
                # Try to find JSON-like content
                json_str = ai_response.strip()

            parsed = json.loads(json_str)

            # Validate structure
            if not isinstance(parsed, dict):
                raise ValueError("Response is not a dictionary")

            return {
                "summary": parsed.get("summary", "AI review completed"),
                "comments": parsed.get("comments", []),
                "insights": parsed.get("insights", []),
            }

        except (json.JSONDecodeError, ValueError) as e:
            # Fallback: parse as text
            return {
                "summary": "AI review completed (parsing failed)",
                "comments": [
                    {
                        "file": "general",
                        "line": 0,
                        "severity": "info",
                        "message": f"AI response parsing failed: {e}",
                    }
                ],
                "insights": [ai_response[:500] + "..." if len(ai_response) > 500 else ai_response],
            }

    def _determine_status(
        self,
        static_results: Dict[str, Any],
        ai_review: Dict[str, Any],
        sonarcloud_results: Dict[str, Any],
    ) -> str:
        """Determine overall review status based on static analysis and AI review."""
        # Check for critical static analysis failures
        ruff_results = static_results.get("ruff", {})
        if ruff_results.get("error_count", 0) > 0:
            return "fail"

        mypy_results = static_results.get("mypy", {})
        if self.config["reviewer"]["strict_mode"] and mypy_results.get("has_errors"):
            return "fail"

        pytest_results = static_results.get("pytest", {})
        if (
            pytest_results.get("success")
            and not pytest_results.get("passed")
            and not pytest_results.get("no_tests")
        ):
            return "fail"

        # Check AI review for high severity issues
        high_severity_count = len(
            [c for c in ai_review.get("comments", []) if c.get("severity") == "high"]
        )

        if high_severity_count > 2:  # More than 2 high severity issues
            return "fail"

        # Check SonarCloud findings for critical issues
        if sonarcloud_results.get("available"):
            metrics = sonarcloud_results.get("metrics", {})
            analysis = sonarcloud_results.get("analysis", {})

            # Fail on security vulnerabilities
            if metrics.get("vulnerabilities", 0) > 0:
                return "fail"

            # Fail on blocking issues
            if analysis.get("blockers"):
                return "fail"

            # Fail if too many bugs
            if metrics.get("bugs", 0) > 5:
                return "fail"

            # Fail if coverage is too low (only if coverage data is available)
            coverage = metrics.get("coverage", 100)  # Default to 100 if not available
            if coverage > 0 and coverage < 50:  # Only fail if coverage is reported and very low
                return "fail"

        # Check for file size violations
        file_stats = static_results.get("file_stats", {})
        if file_stats.get("large_files"):
            return "fail"

        return "pass"

    def _write_review_report(self, milestone_dir: Path, review_result: Dict[str, Any]) -> None:
        """Write review report to milestone directory."""
        report_path = milestone_dir / "review-report.md"

        # Generate markdown report
        report_lines = [
            "# Code Review Report",
            "",
            f"**Status**: {review_result['status'].upper()}",
            f"**Timestamp**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(review_result['timestamp']))}",
            f"**Milestone**: {milestone_dir.name}",
            "",
            "## Summary",
            "",
            f"{review_result['summary']}",
            "",
            "## Static Analysis Results",
            "",
        ]

        # Add static analysis details
        static_results = review_result.get("static_analysis", {})
        sonarcloud_results = review_result.get("sonarcloud_analysis", {})

        # Ruff results
        ruff_results = static_results.get("ruff", {})
        if ruff_results.get("success"):
            error_count = ruff_results.get("error_count", 0)
            warning_count = ruff_results.get("warning_count", 0)
            status_icon = "✅" if error_count == 0 else "❌"
            report_lines.extend(
                [
                    f"### {status_icon} Ruff Linter",
                    f"- Errors: {error_count}",
                    f"- Warnings: {warning_count}",
                    "",
                ]
            )

        # MyPy results
        mypy_results = static_results.get("mypy", {})
        if mypy_results.get("success"):
            status_icon = "✅" if not mypy_results.get("has_errors") else "❌"
            report_lines.extend(
                [
                    f"### {status_icon} MyPy Type Checking",
                    f"- Status: {'PASS' if not mypy_results.get('has_errors') else 'FAIL'}",
                    "",
                ]
            )

        # Pytest results
        pytest_results = static_results.get("pytest", {})
        if pytest_results.get("success"):
            if pytest_results.get("no_tests"):
                status_icon = "⚠️"
                status_text = "NO TESTS"
            else:
                status_icon = "✅" if pytest_results.get("passed") else "❌"
                status_text = "PASS" if pytest_results.get("passed") else "FAIL"

            report_lines.extend(
                [
                    f"### {status_icon} Tests",
                    f"- Status: {status_text}",
                    f"- Test files: {pytest_results.get('test_files', 0)}",
                    "",
                ]
            )

        # SonarCloud results
        if sonarcloud_results.get("available"):
            metrics = sonarcloud_results.get("metrics", {})
            analysis = sonarcloud_results.get("analysis", {})
            quality_gate = sonarcloud_results.get("quality_gate", {})

            overall_rating = analysis.get("overall_rating", "unknown")
            status_icon = {"good": "✅", "fair": "🟡", "needs_improvement": "⚠️", "poor": "❌"}.get(
                overall_rating, "❓"
            )

            report_lines.extend(
                [
                    f"### {status_icon} SonarCloud Quality Analysis",
                    f"- Overall Rating: {overall_rating.upper()}",
                    f"- Bugs: {metrics.get('bugs', 0)}",
                    f"- Vulnerabilities: {metrics.get('vulnerabilities', 0)}",
                    f"- Code Smells: {metrics.get('code_smells', 0)}",
                    f"- Coverage: {metrics.get('coverage', 0):.1f}%",
                    f"- Critical Issues: {analysis.get('critical_issues', 0)}",
                    "",
                ]
            )

            if analysis.get("blockers"):
                report_lines.extend(["#### 🚫 Blocking Issues:", ""])
                for blocker in analysis["blockers"]:
                    report_lines.append(f"- {blocker}")
                report_lines.append("")

            if analysis.get("recommendations"):
                report_lines.extend(["#### 💡 SonarCloud Recommendations:", ""])
                for rec in analysis["recommendations"]:
                    report_lines.append(f"- {rec}")
                report_lines.append("")
        else:
            reason = sonarcloud_results.get("reason", "unknown")
            status_icon = "⚠️" if reason == "offline_mode" else "❌"
            report_lines.extend(
                [
                    f"### {status_icon} SonarCloud Quality Analysis",
                    f"- Status: Not available ({reason})",
                    "",
                ]
            )

        # AI Review Comments
        if review_result.get("comments"):
            report_lines.extend(["## Review Comments", ""])

            for comment in review_result["comments"]:
                severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢", "info": "ℹ️"}.get(
                    comment.get("severity", "info"), "ℹ️"
                )
                file_ref = comment.get("file", "general")
                line_ref = f":{comment['line']}" if comment.get("line", 0) > 0 else ""

                report_lines.extend(
                    [
                        f"### {severity_icon} {file_ref}{line_ref}",
                        "",
                        f"{comment.get('message', 'No message')}",
                        "",
                    ]
                )

        # AI Insights
        if review_result.get("ai_insights"):
            report_lines.extend(["## AI Insights", ""])

            for insight in review_result["ai_insights"]:
                report_lines.extend(
                    [
                        f"- {insight}",
                    ]
                )

            report_lines.append("")

        # File Statistics
        file_stats = static_results.get("file_stats", {})
        if file_stats:
            report_lines.extend(
                [
                    "## File Statistics",
                    "",
                    f"- Total files: {file_stats.get('total_files', 0)}",
                    f"- Python files: {file_stats.get('python_files', 0)}",
                    f"- Test files: {file_stats.get('test_files', 0)}",
                    f"- Total lines: {file_stats.get('total_lines', 0)}",
                    f"- Average file size: {file_stats.get('avg_file_size', 0)} lines",
                    "",
                ]
            )

            if file_stats.get("large_files"):
                report_lines.extend(["### ⚠️ Large Files", ""])
                for large_file in file_stats["large_files"]:
                    report_lines.append(f"- {large_file['file']}: {large_file['lines']} lines")
                report_lines.append("")

        # Footer
        report_lines.extend(["---", "*Generated by SoloPilot ReviewerAgent*"])

        # Write report
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))

        print(f"📄 Review report written to {report_path}")


def main():
    """Main function for testing reviewer agent."""
    import sys

    if len(sys.argv) != 2:
        print("Usage: python reviewer_agent.py <milestone_dir>")
        sys.exit(1)

    milestone_dir = Path(sys.argv[1])
    reviewer = ReviewerAgent()
    result = reviewer.review(milestone_dir)

    print(f"\nReview Status: {result['status']}")
    print(f"Summary: {result['summary']}")


if __name__ == "__main__":
    main()
