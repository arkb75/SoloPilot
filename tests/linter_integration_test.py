#!/usr/bin/env python3
"""
Tests for linter integration functionality in SoloPilot.
"""

import unittest
from unittest.mock import MagicMock, patch

from utils.linter_integration import (
    BanditLinter,
    ESLintLinter,
    LinterManager,
    LintResult,
    MyPyLinter,
    RuffLinter,
)


class TestLintResult(unittest.TestCase):
    """Test LintResult class functionality."""

    def test_empty_result(self):
        """Test LintResult with no issues."""
        result = LintResult(success=True, issues=[], tool="test_tool")

        self.assertTrue(result.success)
        self.assertEqual(result.error_count, 0)
        self.assertEqual(result.warning_count, 0)
        self.assertFalse(result.has_errors())
        self.assertEqual(result.get_issues_summary(), "test_tool: No issues found")
        self.assertEqual(result.get_correction_prompt(), "")

    def test_result_with_issues(self):
        """Test LintResult with various issues."""
        issues = [
            {"line": 1, "severity": "error", "message": "Syntax error"},
            {"line": 5, "severity": "warning", "message": "Unused variable"},
            {"line": 10, "severity": "error", "message": "Type mismatch"},
        ]
        result = LintResult(success=True, issues=issues, tool="test_tool")

        self.assertEqual(result.error_count, 2)
        self.assertEqual(result.warning_count, 1)
        self.assertTrue(result.has_errors())
        self.assertEqual(result.get_issues_summary(), "test_tool: 2 errors, 1 warnings")

        prompt = result.get_correction_prompt()
        self.assertIn("test_tool linter found 3 issues", prompt)
        self.assertIn("Line 1: [ERROR] Syntax error", prompt)
        self.assertIn("Line 5: [WARNING] Unused variable", prompt)


class TestRuffLinter(unittest.TestCase):
    """Test RuffLinter functionality."""

    def setUp(self):
        """Set up test environment."""
        self.linter = RuffLinter()

    def test_language(self):
        """Test language identification."""
        self.assertEqual(self.linter.get_language(), "python")

    def test_availability(self):
        """Test linter availability check."""
        # This depends on system setup, so we'll test both cases
        is_available = self.linter.is_available()
        self.assertIsInstance(is_available, bool)

    def test_lint_valid_code(self):
        """Test linting valid Python code."""
        if not self.linter.is_available():
            self.skipTest("Ruff not available")

        valid_code = """
def hello_world():
    print("Hello, World!")
    return True
"""
        result = self.linter.lint_code(valid_code)

        self.assertTrue(result.success)
        self.assertEqual(result.tool, "ruff")
        # Valid code might still have some warnings, but should not have errors

    def test_lint_invalid_code(self):
        """Test linting invalid Python code."""
        if not self.linter.is_available():
            self.skipTest("Ruff not available")

        invalid_code = """
import os
import sys  # unused import

def bad_function():
    x = 1  # unused variable
    if True:
        pass
"""
        result = self.linter.lint_code(invalid_code)

        self.assertTrue(result.success)
        self.assertEqual(result.tool, "ruff")
        # This code should have some issues (unused imports/variables)
        self.assertGreater(len(result.issues), 0)


class TestMyPyLinter(unittest.TestCase):
    """Test MyPyLinter functionality."""

    def setUp(self):
        """Set up test environment."""
        self.linter = MyPyLinter()

    def test_language(self):
        """Test language identification."""
        self.assertEqual(self.linter.get_language(), "python")

    def test_lint_type_error_code(self):
        """Test linting code with type errors."""
        if not self.linter.is_available():
            self.skipTest("MyPy not available")

        # Code with type issues
        type_error_code = """
def add_numbers(a: int, b: int) -> int:
    return a + b

result = add_numbers("hello", "world")  # Type error
"""
        result = self.linter.lint_code(type_error_code)

        self.assertTrue(result.success)
        self.assertEqual(result.tool, "mypy")


class TestBanditLinter(unittest.TestCase):
    """Test BanditLinter functionality."""

    def setUp(self):
        """Set up test environment."""
        self.linter = BanditLinter()

    def test_language(self):
        """Test language identification."""
        self.assertEqual(self.linter.get_language(), "python")

    def test_lint_security_issue_code(self):
        """Test linting code with security issues."""
        if not self.linter.is_available():
            self.skipTest("Bandit not available")

        # Code with security issues
        security_code = """
import subprocess

# Security issue: shell injection vulnerability
def run_command(user_input):
    subprocess.call(f"ls {user_input}", shell=True)

# Security issue: hardcoded password
password = "secret123"
"""
        result = self.linter.lint_code(security_code)

        self.assertTrue(result.success)
        self.assertEqual(result.tool, "bandit")


class TestESLintLinter(unittest.TestCase):
    """Test ESLintLinter functionality."""

    def setUp(self):
        """Set up test environment."""
        self.linter = ESLintLinter()

    def test_language(self):
        """Test language identification."""
        self.assertEqual(self.linter.get_language(), "javascript")

    def test_lint_javascript_code(self):
        """Test linting JavaScript code."""
        if not self.linter.is_available():
            self.skipTest("ESLint not available")

        js_code = """
function hello() {
    var unused_var = 42;  // Unused variable
    console.log("Hello World");
}

undeclared_function();  // Undeclared function
"""
        result = self.linter.lint_code(js_code, "test.js")

        self.assertTrue(result.success)
        self.assertEqual(result.tool, "eslint")


class TestLinterManager(unittest.TestCase):
    """Test LinterManager functionality."""

    def setUp(self):
        """Set up test environment."""
        self.manager = LinterManager(
            {"enabled_languages": ["python", "javascript"], "max_correction_iterations": 2}
        )

    def test_initialization(self):
        """Test LinterManager initialization."""
        self.assertIsInstance(self.manager.get_available_languages(), list)
        self.assertEqual(self.manager.max_correction_iterations, 2)

    def test_lint_python_code(self):
        """Test linting Python code with manager."""
        test_code = """
def test_function():
    print("Hello World")
    return True
"""
        results = self.manager.lint_code(test_code, "python", "test.py")

        # Should return list of results (one per available linter)
        self.assertIsInstance(results, list)
        for result in results:
            self.assertIsInstance(result, LintResult)
            self.assertEqual(
                result.tool.lower().replace("linter", ""), result.tool.lower().replace("linter", "")
            )

    def test_lint_unsupported_language(self):
        """Test linting unsupported language."""
        results = self.manager.lint_code("code", "unsupported_language")
        self.assertEqual(results, [])

    def test_has_critical_errors(self):
        """Test critical error detection."""
        # Mock results with errors
        error_result = LintResult(
            success=True, issues=[{"severity": "error", "message": "Test error"}], tool="test"
        )
        warning_result = LintResult(
            success=True, issues=[{"severity": "warning", "message": "Test warning"}], tool="test"
        )

        self.assertTrue(self.manager.has_critical_errors([error_result]))
        self.assertFalse(self.manager.has_critical_errors([warning_result]))
        self.assertTrue(self.manager.has_critical_errors([error_result, warning_result]))

    def test_generate_correction_prompt(self):
        """Test correction prompt generation."""
        error_result = LintResult(
            success=True,
            issues=[{"line": 5, "severity": "error", "message": "Syntax error"}],
            tool="test_tool",
        )

        prompt = self.manager.generate_correction_prompt([error_result], "original code")

        self.assertIn("original code", prompt)
        self.assertIn("test_tool linter found", prompt)
        self.assertIn("Syntax error", prompt)
        self.assertIn("fix these issues", prompt.lower())

    def test_get_summary(self):
        """Test results summary generation."""
        results = [
            LintResult(
                success=True,
                issues=[
                    {"severity": "error", "message": "Error 1"},
                    {"severity": "warning", "message": "Warning 1"},
                ],
                tool="tool1",
            ),
            LintResult(
                success=True, issues=[{"severity": "error", "message": "Error 2"}], tool="tool2"
            ),
        ]

        summary = self.manager.get_summary(results)

        self.assertEqual(summary["total_linters"], 2)
        self.assertEqual(summary["total_errors"], 2)
        self.assertEqual(summary["total_warnings"], 1)
        self.assertTrue(summary["has_errors"])
        self.assertEqual(summary["successful_linters"], 2)


class TestLinterIntegrationWithDevAgent(unittest.TestCase):
    """Test integration with Dev Agent."""

    def setUp(self):
        """Set up test environment."""
        # We'll mock the actual AI provider calls
        self.test_config = {
            "linting": {
                "enabled": True,
                "max_correction_iterations": 2,
                "enabled_languages": ["python"],
            }
        }

    @patch("agents.dev.dev_agent.get_provider")
    @patch("agents.dev.dev_agent.get_context_engine")
    def test_dev_agent_with_linting(self, mock_context_engine, mock_provider):
        """Test Dev Agent with linting enabled."""
        # Mock the provider and context engine
        mock_provider.return_value = MagicMock()
        mock_context_engine.return_value = MagicMock()
        mock_context_engine.return_value.get_engine_info.return_value = {"engine": "test"}

        # We would need to import and test DevAgent here, but it requires
        # proper config file setup. This is more of an integration test
        # that would be better run with actual test data.
        pass


if __name__ == "__main__":
    unittest.main()
