#!/usr/bin/env python3
"""
Real-Time Linter Integration for SoloPilot Dev Agent

Provides language-agnostic linting capabilities with immediate feedback
for code generation self-correction.
"""

import json
import os
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class LintResult:
    """Represents the result of a linting operation."""

    def __init__(self, success: bool, issues: List[Dict[str, Any]], tool: str):
        self.success = success
        self.issues = issues
        self.tool = tool
        self.error_count = len([i for i in issues if i.get("severity") in ["error", "critical"]])
        self.warning_count = len([i for i in issues if i.get("severity") == "warning"])

    def has_errors(self) -> bool:
        """Check if there are any error-level issues."""
        return self.error_count > 0

    def get_issues_summary(self) -> str:
        """Get a human-readable summary of issues."""
        if not self.issues:
            return f"{self.tool}: No issues found"

        return f"{self.tool}: {self.error_count} errors, {self.warning_count} warnings"

    def get_correction_prompt(self) -> str:
        """Generate a prompt for AI to correct the issues."""
        if not self.issues:
            return ""

        issue_lines = []
        for issue in self.issues[:10]:  # Limit to 10 issues to avoid prompt overflow
            location = f"Line {issue.get('line', '?')}" if issue.get("line") else "Unknown location"
            severity = issue.get("severity", "info").upper()
            message = issue.get("message", "No description")
            issue_lines.append(f"- {location}: [{severity}] {message}")

        truncated = " (showing first 10)" if len(self.issues) > 10 else ""

        return f"""
The {self.tool} linter found {len(self.issues)} issues{truncated}:

{chr(10).join(issue_lines)}

Please fix these issues and regenerate the corrected code.
"""


class BaseLinter(ABC):
    """Abstract base class for language-specific linters."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.timeout = self.config.get("timeout", 30)

    @abstractmethod
    def get_language(self) -> str:
        """Return the programming language this linter supports."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the linter tool is available on the system."""
        pass

    @abstractmethod
    def lint_code(self, code: str, filename: str = "temp_file") -> LintResult:
        """Lint the provided code and return results."""
        pass

    def _run_command(
        self, cmd: List[str], cwd: Optional[Path] = None, input_text: str = ""
    ) -> Tuple[int, str, str]:
        """Run a command and return (returncode, stdout, stderr)."""
        try:
            result = subprocess.run(
                cmd, cwd=cwd, input=input_text, text=True, capture_output=True, timeout=self.timeout
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 1, "", f"Command timed out after {self.timeout}s"
        except FileNotFoundError:
            return 1, "", f"Command not found: {cmd[0]}"


class RuffLinter(BaseLinter):
    """Python linter using ruff for style and error checking."""

    def get_language(self) -> str:
        return "python"

    def is_available(self) -> bool:
        returncode, _, _ = self._run_command(["ruff", "--version"])
        return returncode == 0

    def lint_code(self, code: str, filename: str = "temp.py") -> LintResult:
        """Lint Python code using ruff."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            # Run ruff check with JSON output
            cmd = ["ruff", "check", temp_path, "--output-format=json"]
            returncode, stdout, stderr = self._run_command(cmd)

            issues = []
            if stdout.strip():
                try:
                    ruff_issues = json.loads(stdout)
                    for issue in ruff_issues:
                        issues.append(
                            {
                                "line": issue.get("location", {}).get("row", 0),
                                "column": issue.get("location", {}).get("column", 0),
                                "severity": (
                                    "error" if issue.get("code", "").startswith("E") else "warning"
                                ),
                                "message": issue.get("message", ""),
                                "rule": issue.get("code", ""),
                                "tool": "ruff",
                            }
                        )
                except json.JSONDecodeError:
                    # Fallback: parse as text
                    if stderr.strip():
                        issues.append(
                            {
                                "line": 0,
                                "severity": "error",
                                "message": f"Ruff error: {stderr.strip()}",
                                "tool": "ruff",
                            }
                        )

            return LintResult(success=True, issues=issues, tool="ruff")

        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except OSError:
                pass


class MyPyLinter(BaseLinter):
    """Python type checker using mypy."""

    def get_language(self) -> str:
        return "python"

    def is_available(self) -> bool:
        returncode, _, _ = self._run_command(["mypy", "--version"])
        return returncode == 0

    def lint_code(self, code: str, filename: str = "temp.py") -> LintResult:
        """Type-check Python code using mypy."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            # Run mypy with specific options
            cmd = ["mypy", temp_path, "--show-error-codes", "--no-error-summary"]
            returncode, stdout, stderr = self._run_command(cmd)

            issues = []

            # Parse mypy output (format: filename:line:column: error: message [error-code])
            for line in (stdout + stderr).split("\n"):
                if ":" in line and ("error:" in line or "warning:" in line):
                    parts = line.split(":", 4)
                    if len(parts) >= 4:
                        try:
                            line_num = int(parts[1])
                            col_num = int(parts[2]) if parts[2].isdigit() else 0
                            message_part = parts[3] if len(parts) > 3 else ""

                            # Extract severity and message
                            if "error:" in message_part:
                                severity = "error"
                                message = message_part.split("error:", 1)[1].strip()
                            elif "warning:" in message_part:
                                severity = "warning"
                                message = message_part.split("warning:", 1)[1].strip()
                            else:
                                severity = "error"
                                message = message_part.strip()

                            issues.append(
                                {
                                    "line": line_num,
                                    "column": col_num,
                                    "severity": severity,
                                    "message": message,
                                    "tool": "mypy",
                                }
                            )
                        except (ValueError, IndexError):
                            continue

            return LintResult(success=True, issues=issues, tool="mypy")

        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


class BanditLinter(BaseLinter):
    """Python security linter using bandit."""

    def get_language(self) -> str:
        return "python"

    def is_available(self) -> bool:
        returncode, _, _ = self._run_command(["bandit", "--version"])
        return returncode == 0

    def lint_code(self, code: str, filename: str = "temp.py") -> LintResult:
        """Security scan Python code using bandit."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            # Run bandit with JSON output
            cmd = ["bandit", "-f", "json", temp_path]
            returncode, stdout, stderr = self._run_command(cmd)

            issues = []
            if stdout.strip():
                try:
                    bandit_data = json.loads(stdout)
                    for result in bandit_data.get("results", []):
                        severity_map = {"HIGH": "error", "MEDIUM": "warning", "LOW": "info"}

                        issues.append(
                            {
                                "line": result.get("line_number", 0),
                                "severity": severity_map.get(
                                    result.get("issue_severity", "LOW"), "info"
                                ),
                                "message": result.get("issue_text", "Security issue"),
                                "rule": result.get("test_id", ""),
                                "tool": "bandit",
                            }
                        )
                except json.JSONDecodeError:
                    if returncode != 0 and stderr:
                        issues.append(
                            {
                                "line": 0,
                                "severity": "error",
                                "message": f"Bandit error: {stderr.strip()}",
                                "tool": "bandit",
                            }
                        )

            return LintResult(success=True, issues=issues, tool="bandit")

        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


class ESLintLinter(BaseLinter):
    """JavaScript/TypeScript linter using ESLint."""

    def get_language(self) -> str:
        return "javascript"

    def is_available(self) -> bool:
        returncode, _, _ = self._run_command(["eslint", "--version"])
        return returncode == 0

    def lint_code(self, code: str, filename: str = "temp.js") -> LintResult:
        """Lint JavaScript/TypeScript code using ESLint."""
        # Determine file extension based on filename
        suffix = ".ts" if filename.endswith(".ts") else ".js"

        with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            # Run ESLint with JSON output
            cmd = [
                "eslint",
                temp_path,
                "--format",
                "json",
                "--no-eslintrc",
                "--config",
                '{"extends": ["eslint:recommended"]}',
            ]
            returncode, stdout, stderr = self._run_command(cmd)

            issues = []
            if stdout.strip():
                try:
                    eslint_data = json.loads(stdout)
                    for file_result in eslint_data:
                        for message in file_result.get("messages", []):
                            severity_map = {1: "warning", 2: "error"}

                            issues.append(
                                {
                                    "line": message.get("line", 0),
                                    "column": message.get("column", 0),
                                    "severity": severity_map.get(
                                        message.get("severity", 1), "warning"
                                    ),
                                    "message": message.get("message", ""),
                                    "rule": message.get("ruleId", ""),
                                    "tool": "eslint",
                                }
                            )
                except json.JSONDecodeError:
                    if stderr.strip():
                        issues.append(
                            {
                                "line": 0,
                                "severity": "error",
                                "message": f"ESLint error: {stderr.strip()}",
                                "tool": "eslint",
                            }
                        )

            return LintResult(success=True, issues=issues, tool="eslint")

        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


class LinterManager:
    """Manages multiple linters for real-time code feedback."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.linters = self._initialize_linters()
        self.max_correction_iterations = self.config.get("max_correction_iterations", 3)
        self.enabled_languages = self.config.get("enabled_languages", ["python", "javascript"])

    def _initialize_linters(self) -> Dict[str, List[BaseLinter]]:
        """Initialize all available linters by language."""
        linters = {
            "python": [RuffLinter(self.config), MyPyLinter(self.config), BanditLinter(self.config)],
            "javascript": [ESLintLinter(self.config)],
        }

        # Filter to only available linters
        available_linters = {}
        for lang, lang_linters in linters.items():
            available = [linter for linter in lang_linters if linter.is_available()]
            if available:
                available_linters[lang] = available
                print(f"✅ {lang}: {', '.join([l.__class__.__name__ for l in available])}")
            else:
                print(f"⚠️ {lang}: No linters available")

        return available_linters

    def get_available_languages(self) -> List[str]:
        """Get list of languages with available linters."""
        return list(self.linters.keys())

    def lint_code(self, code: str, language: str, filename: str = None) -> List[LintResult]:
        """Lint code using all available linters for the specified language."""
        if language not in self.linters:
            return []

        if language not in self.enabled_languages:
            return []

        # Generate appropriate filename if not provided
        if not filename:
            extensions = {"python": ".py", "javascript": ".js", "typescript": ".ts"}
            filename = f"temp{extensions.get(language, '.txt')}"

        results = []
        for linter in self.linters[language]:
            try:
                result = linter.lint_code(code, filename)
                results.append(result)
            except Exception as e:
                # Create error result for failed linter
                error_result = LintResult(
                    success=False,
                    issues=[
                        {
                            "line": 0,
                            "severity": "error",
                            "message": f"Linter {linter.__class__.__name__} failed: {e}",
                            "tool": linter.__class__.__name__,
                        }
                    ],
                    tool=linter.__class__.__name__,
                )
                results.append(error_result)

        return results

    def has_critical_errors(self, results: List[LintResult]) -> bool:
        """Check if any linting results have critical errors that require correction."""
        return any(result.has_errors() for result in results)

    def generate_correction_prompt(self, results: List[LintResult], original_code: str) -> str:
        """Generate a comprehensive correction prompt for the AI."""
        if not results:
            return ""

        error_results = [r for r in results if r.has_errors()]
        if not error_results:
            return ""

        prompt_parts = [
            "The following code has linting errors that need to be fixed:",
            "",
            "```python" if any("python" in r.tool.lower() for r in results) else "```",
            original_code,
            "```",
            "",
            "LINTING ERRORS:",
        ]

        for result in error_results:
            prompt_parts.append(result.get_correction_prompt())

        prompt_parts.extend(
            [
                "",
                "Please fix these issues and provide ONLY the corrected code without any explanation or markdown formatting.",
            ]
        )

        return "\n".join(prompt_parts)

    def get_summary(self, results: List[LintResult]) -> Dict[str, Any]:
        """Get a summary of all linting results."""
        total_errors = sum(r.error_count for r in results)
        total_warnings = sum(r.warning_count for r in results)

        return {
            "total_linters": len(results),
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "has_errors": total_errors > 0,
            "summaries": [r.get_issues_summary() for r in results],
            "successful_linters": len([r for r in results if r.success]),
        }


def main():
    """Main function for testing linter integration."""
    # Test Python code with intentional issues
    test_python_code = """
import os
import sys

def badfunction(x):
    if x == 1:
        print("hello world")
    return x

# Security issue: hardcoded password
password = "secret123"

# Type issue: missing type hints
def add_numbers(a, b):
    return a + b

# Style issue: unused import
import json
"""

    print("🔍 Testing Linter Integration")
    print("=" * 50)

    manager = LinterManager()
    print(f"\nAvailable languages: {manager.get_available_languages()}")

    if "python" in manager.get_available_languages():
        print("\n📋 Linting Python code...")
        results = manager.lint_code(test_python_code, "python", "test.py")

        summary = manager.get_summary(results)
        print(f"\nSummary: {summary['total_errors']} errors, {summary['total_warnings']} warnings")

        for result in results:
            print(f"  {result.get_issues_summary()}")

        if manager.has_critical_errors(results):
            print("\n🔧 Generated correction prompt:")
            correction_prompt = manager.generate_correction_prompt(results, test_python_code)
            print(
                correction_prompt[:500] + "..."
                if len(correction_prompt) > 500
                else correction_prompt
            )


if __name__ == "__main__":
    main()
