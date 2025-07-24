#!/usr/bin/env python3
"""
Unit tests for ReviewerAgent

Tests both happy path (good code passes) and fail path (bad code fails).
"""

import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.review.reviewer_agent import ReviewerAgent


@pytest.fixture
def temp_milestone_dir():
    """Create a temporary milestone directory for testing."""
    temp_dir = tempfile.mkdtemp()
    milestone_dir = Path(temp_dir) / "test-milestone"
    milestone_dir.mkdir()
    yield milestone_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_provider():
    """Create a mock AI provider for testing."""
    provider = MagicMock()
    provider.generate_code.return_value = """{
        "summary": "Code quality looks good with minor improvements needed",
        "comments": [
            {"file": "main.py", "line": 10, "severity": "medium", "message": "Consider adding type hints"},
            {"file": "general", "line": 0, "severity": "info", "message": "Overall code structure is well organized"}
        ],
        "insights": [
            "Code follows Python best practices",
            "Test coverage could be improved"
        ]
    }"""
    return provider


@pytest.fixture
def good_code_milestone(temp_milestone_dir):
    """Create a milestone with good quality code."""
    # Create a well-structured Python file
    main_py = temp_milestone_dir / "main.py"
    main_py.write_text(
        """#!/usr/bin/env python3
\"\"\"
A well-documented Python module.
\"\"\"

from typing import List, Optional


def calculate_sum(numbers: List[int]) -> int:
    \"\"\"Calculate the sum of a list of numbers.
    
    Args:
        numbers: List of integers to sum
        
    Returns:
        The sum of all numbers
    \"\"\"
    return sum(numbers)


def process_data(data: Optional[str] = None) -> str:
    \"\"\"Process input data with proper error handling.
    
    Args:
        data: Optional input data string
        
    Returns:
        Processed data string
    \"\"\"
    if data is None:
        return "No data provided"
    
    return data.strip().upper()


if __name__ == "__main__":
    # Example usage
    numbers = [1, 2, 3, 4, 5]
    result = calculate_sum(numbers)
    print(f"Sum: {result}")
    
    processed = process_data("  hello world  ")
    print(f"Processed: {processed}")
"""
    )

    # Create a test file
    test_py = temp_milestone_dir / "test_main.py"
    test_py.write_text(
        """#!/usr/bin/env python3
\"\"\"
Tests for main module.
\"\"\"

import pytest
from main import calculate_sum, process_data


def test_calculate_sum():
    \"\"\"Test calculate_sum function.\"\"\"
    assert calculate_sum([1, 2, 3]) == 6
    assert calculate_sum([]) == 0
    assert calculate_sum([-1, 1]) == 0


def test_process_data():
    \"\"\"Test process_data function.\"\"\"
    assert process_data("hello") == "HELLO"
    assert process_data("  world  ") == "WORLD"
    assert process_data(None) == "No data provided"
    assert process_data("") == ""


if __name__ == "__main__":
    pytest.main([__file__])
"""
    )

    # Create a README
    readme = temp_milestone_dir / "README.md"
    readme.write_text(
        """# Test Milestone

This is a well-documented test milestone with proper code structure.

## Features
- Type-annotated functions
- Comprehensive tests
- Clear documentation
"""
    )

    return temp_milestone_dir


@pytest.fixture
def bad_code_milestone(temp_milestone_dir):
    """Create a milestone with poor quality code."""
    # Create a poorly written Python file
    bad_py = temp_milestone_dir / "bad_code.py"
    bad_py.write_text(
        """# No shebang, no docstring, poor formatting

import *  # Bad import
import unused_module

def badFunction(x,y):  # Poor naming, no types, no docstring
    result=x+y  # No spaces
    if result>10:
        print("Big number")  # Direct print instead of return
    return result

class badClass:  # Poor naming, no inheritance
    def __init__(self,value):  # No spaces, no types
        self.value=value
        
    def getValue(self):
        return self.value  # No error handling

# Unreachable code
if True:
    pass
else:
    print("This will never execute")

# No main guard
x = badFunction(5, 7)
obj = badClass(x)
print(obj.getValue())
"""
    )

    # Create a file with syntax errors
    syntax_error_py = temp_milestone_dir / "syntax_error.py"
    syntax_error_py.write_text(
        """#!/usr/bin/env python3
# File with syntax errors

def broken_function(
    # Missing closing parenthesis and colon

def another_function():
    return "missing quote

# Invalid indentation
if True:
print("Bad indentation")

# Unclosed bracket
my_list = [1, 2, 3
"""
    )

    # Create a very large file (over size limit)
    large_py = temp_milestone_dir / "large_file.py"
    large_content = "# Large file\n" + "\n".join([f"# Line {i}" for i in range(15000)])
    large_py.write_text(large_content)

    return temp_milestone_dir


@pytest.fixture
def empty_milestone(temp_milestone_dir):
    """Create an empty milestone directory."""
    return temp_milestone_dir


class TestReviewerAgent:
    """Test cases for ReviewerAgent class."""

    def test_init_with_default_config(self):
        """Test ReviewerAgent initialization with default config."""
        with patch("agents.review.reviewer_agent.get_provider") as mock_get_provider:
            mock_get_provider.return_value = MagicMock()

            reviewer = ReviewerAgent()

            assert reviewer.config is not None
            assert "llm" in reviewer.config
            assert "reviewer" in reviewer.config
            assert reviewer.provider is not None

    def test_init_with_custom_config(self, temp_milestone_dir):
        """Test ReviewerAgent initialization with custom config."""
        config_file = temp_milestone_dir / "test_config.yaml"
        config_file.write_text(
            """
llm:
  primary: "fake"
reviewer:
  strict_mode: false
  min_test_coverage: 50
"""
        )

        with patch("agents.review.reviewer_agent.get_provider") as mock_get_provider:
            mock_get_provider.return_value = MagicMock()

            reviewer = ReviewerAgent(str(config_file))

            assert reviewer.config["llm"]["primary"] == "fake"
            assert reviewer.config["reviewer"]["strict_mode"] is False
            assert reviewer.config["reviewer"]["min_test_coverage"] == 50

    def test_review_nonexistent_directory(self):
        """Test review of non-existent directory."""
        with patch("agents.review.reviewer_agent.get_provider") as mock_get_provider:
            mock_get_provider.return_value = MagicMock()

            reviewer = ReviewerAgent()
            result = reviewer.review(Path("/nonexistent/directory"))

            assert result["status"] == "fail"
            assert "not found" in result["summary"]
            assert len(result["comments"]) == 0

    @patch("src.agents.review.reviewer_agent.get_provider")
    def test_review_good_code_passes(self, mock_get_provider, good_code_milestone, mock_provider):
        """Test that good quality code passes review."""
        mock_get_provider.return_value = mock_provider

        # Mock static analysis tools to return success
        with patch.object(ReviewerAgent, "_run_ruff") as mock_ruff, patch.object(
            ReviewerAgent, "_run_mypy"
        ) as mock_mypy, patch.object(ReviewerAgent, "_run_pytest") as mock_pytest:

            mock_ruff.return_value = {
                "success": True,
                "violations": [],
                "error_count": 0,
                "warning_count": 0,
                "return_code": 0,
            }

            mock_mypy.return_value = {
                "success": True,
                "output": "",
                "errors": "",
                "return_code": 0,
                "has_errors": False,
            }

            mock_pytest.return_value = {
                "success": True,
                "output": "test session starts\n2 passed",
                "errors": "",
                "return_code": 0,
                "test_files": 1,
                "passed": True,
            }

            reviewer = ReviewerAgent()
            result = reviewer.review(good_code_milestone)

            # Good code should pass
            assert result["status"] == "pass"
            assert "summary" in result
            assert "comments" in result
            assert "static_analysis" in result

            # Check that review report was created
            report_file = good_code_milestone / "review-report.md"
            assert report_file.exists()

    @patch("src.agents.review.reviewer_agent.get_provider")
    def test_review_bad_code_fails(self, mock_get_provider, bad_code_milestone):
        """Test that poor quality code fails review."""
        # Mock provider to return critical issues
        mock_provider = MagicMock()
        mock_provider.generate_code.return_value = """{
            "summary": "Multiple critical issues found",
            "comments": [
                {"file": "bad_code.py", "line": 5, "severity": "high", "message": "Wildcard import is dangerous"},
                {"file": "bad_code.py", "line": 8, "severity": "high", "message": "Function naming violates PEP 8"},
                {"file": "bad_code.py", "line": 15, "severity": "high", "message": "No error handling in critical path"},
                {"file": "syntax_error.py", "line": 5, "severity": "high", "message": "Syntax error: missing parenthesis"}
            ],
            "insights": [
                "Code quality is below acceptable standards",
                "Multiple PEP 8 violations detected",
                "Error handling is insufficient"
            ]
        }"""
        mock_get_provider.return_value = mock_provider

        # Mock static analysis tools to return failures
        with patch.object(ReviewerAgent, "_run_ruff") as mock_ruff, patch.object(
            ReviewerAgent, "_run_mypy"
        ) as mock_mypy, patch.object(ReviewerAgent, "_run_pytest") as mock_pytest:

            mock_ruff.return_value = {
                "success": True,
                "violations": [
                    {"code": "E999", "message": "SyntaxError: invalid syntax"},
                    {"code": "E302", "message": "expected 2 blank lines"},
                    {"code": "F403", "message": "unable to detect undefined names"},
                ],
                "error_count": 3,
                "warning_count": 1,
                "return_code": 1,
            }

            mock_mypy.return_value = {
                "success": True,
                "output": "bad_code.py:8: error: Function is missing a type annotation",
                "errors": "",
                "return_code": 1,
                "has_errors": True,
            }

            mock_pytest.return_value = {
                "success": True,
                "output": "",
                "errors": "",
                "return_code": 0,
                "test_files": 0,
                "passed": True,
                "no_tests": True,
            }

            reviewer = ReviewerAgent()
            result = reviewer.review(bad_code_milestone)

            # Bad code should fail
            assert result["status"] == "fail"
            assert "critical" in result["summary"] or "issues" in result["summary"]
            assert len(result["comments"]) > 0

            # Check for high severity issues
            high_severity_comments = [c for c in result["comments"] if c.get("severity") == "high"]
            assert len(high_severity_comments) > 0

    @patch("src.agents.review.reviewer_agent.get_provider")
    def test_review_empty_milestone(self, mock_get_provider, empty_milestone, mock_provider):
        """Test review of empty milestone directory."""
        mock_get_provider.return_value = mock_provider

        reviewer = ReviewerAgent()
        result = reviewer.review(empty_milestone)

        assert result["status"] in ["pass", "fail"]  # Could be either
        assert "summary" in result
        assert "static_analysis" in result

    def test_static_analysis_tools_not_available(self, good_code_milestone):
        """Test behavior when static analysis tools are not available."""
        with patch("agents.review.reviewer_agent.get_provider") as mock_get_provider:
            mock_get_provider.return_value = MagicMock()

            # Mock subprocess to raise FileNotFoundError (tool not found)
            with patch("subprocess.run", side_effect=FileNotFoundError("Tool not found")):
                reviewer = ReviewerAgent()
                result = reviewer.review(good_code_milestone)

                # Should still complete review, just with limited static analysis
                assert result["status"] in ["pass", "fail"]
                assert "static_analysis" in result

                # All tools should report as unsuccessful
                static = result["static_analysis"]
                assert static["ruff"]["success"] is False
                assert static["mypy"]["success"] is False
                assert static["pytest"]["success"] is False

    def test_ai_provider_failure(self, good_code_milestone):
        """Test behavior when AI provider fails."""
        with patch("agents.review.reviewer_agent.get_provider") as mock_get_provider:
            # Mock provider that raises exception
            mock_provider = MagicMock()
            mock_provider.generate_code.side_effect = Exception("AI service unavailable")
            mock_get_provider.return_value = mock_provider

            reviewer = ReviewerAgent()
            result = reviewer.review(good_code_milestone)

            # Should still complete review with static analysis only
            assert result["status"] in ["pass", "fail"]
            assert "AI review failed" in result.get("ai_insights", [""])[0]

    def test_file_stats_analysis(self, good_code_milestone):
        """Test file statistics analysis."""
        with patch("agents.review.reviewer_agent.get_provider") as mock_get_provider:
            mock_get_provider.return_value = MagicMock()

            reviewer = ReviewerAgent()

            # Test file stats analysis
            stats = reviewer._analyze_file_stats(good_code_milestone)

            assert stats["python_files"] >= 2  # main.py and test_main.py
            assert stats["test_files"] >= 1  # test_main.py
            assert stats["total_lines"] > 0
            assert stats["avg_file_size"] > 0

    def test_determine_status_logic(self, good_code_milestone):
        """Test status determination logic."""
        with patch("agents.review.reviewer_agent.get_provider") as mock_get_provider:
            mock_get_provider.return_value = MagicMock()

            reviewer = ReviewerAgent()

            # Test pass scenario
            static_results = {
                "ruff": {"error_count": 0, "warning_count": 1},
                "mypy": {"has_errors": False},
                "pytest": {"success": True, "passed": True},
            }
            ai_review = {
                "comments": [
                    {"severity": "low", "message": "Minor issue"},
                    {"severity": "medium", "message": "Medium issue"},
                ]
            }

            status = reviewer._determine_status(static_results, ai_review)
            assert status == "pass"

            # Test fail scenario - ruff errors
            static_results["ruff"]["error_count"] = 1
            status = reviewer._determine_status(static_results, ai_review)
            assert status == "fail"

            # Test fail scenario - too many high severity AI issues
            static_results["ruff"]["error_count"] = 0
            ai_review["comments"] = [
                {"severity": "high", "message": "Critical issue 1"},
                {"severity": "high", "message": "Critical issue 2"},
                {"severity": "high", "message": "Critical issue 3"},
            ]
            status = reviewer._determine_status(static_results, ai_review)
            assert status == "fail"

    def test_offline_mode_compatibility(self, good_code_milestone):
        """Test that reviewer works in offline mode."""
        with patch.dict(os.environ, {"NO_NETWORK": "1", "AI_PROVIDER": "fake"}):
            with patch("agents.review.reviewer_agent.get_provider") as mock_get_provider:
                # Mock fake provider
                fake_provider = MagicMock()
                fake_provider.generate_code.return_value = """{
                    "summary": "Offline review completed",
                    "comments": [],
                    "insights": ["Review completed in offline mode"]
                }"""
                mock_get_provider.return_value = fake_provider

                reviewer = ReviewerAgent()
                result = reviewer.review(good_code_milestone)

                assert result["status"] in ["pass", "fail"]
                assert "summary" in result


class TestReviewerAgentIntegration:
    """Integration tests for ReviewerAgent."""

    @patch("src.agents.review.reviewer_agent.get_provider")
    def test_end_to_end_review_workflow(
        self, mock_get_provider, good_code_milestone, mock_provider
    ):
        """Test complete end-to-end review workflow."""
        mock_get_provider.return_value = mock_provider

        reviewer = ReviewerAgent()
        result = reviewer.review(good_code_milestone)

        # Verify all expected components are present
        assert "status" in result
        assert "summary" in result
        assert "comments" in result
        assert "static_analysis" in result
        assert "ai_insights" in result
        assert "timestamp" in result
        assert "milestone_dir" in result

        # Verify static analysis components
        static = result["static_analysis"]
        assert "ruff" in static
        assert "mypy" in static
        assert "pytest" in static
        assert "file_stats" in static

        # Verify review report was created
        report_file = good_code_milestone / "review-report.md"
        assert report_file.exists()

        # Verify report content
        report_content = report_file.read_text()
        assert "Code Review Report" in report_content
        assert result["status"].upper() in report_content
        assert "Static Analysis Results" in report_content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
