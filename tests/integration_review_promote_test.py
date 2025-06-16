#!/usr/bin/env python3
"""
Integration tests for Review → Promote workflow

Tests the complete flow from AI review through promotion pipeline.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agents.review.reviewer_agent import ReviewerAgent
from scripts.check_review_status import extract_status_from_report
from utils.github_review import GitHubReviewer


@pytest.fixture
def temp_git_repo():
    """Create a temporary git repository for testing."""
    temp_dir = tempfile.mkdtemp()
    repo_dir = Path(temp_dir) / "test_repo"
    repo_dir.mkdir()
    
    # Initialize git repo
    os.chdir(repo_dir)
    subprocess.run(["git", "init"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)
    
    # Create initial commit
    readme = repo_dir / "README.md"
    readme.write_text("# Test Repository")
    subprocess.run(["git", "add", "README.md"], check=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], check=True)
    
    yield repo_dir
    
    # Cleanup
    os.chdir(project_root)
    shutil.rmtree(temp_dir)


@pytest.fixture
def good_code_milestone(temp_git_repo):
    """Create a milestone with good quality code."""
    milestone_dir = temp_git_repo / "milestone-good"
    milestone_dir.mkdir()
    
    # Create well-structured Python code
    main_py = milestone_dir / "main.py"
    main_py.write_text('''#!/usr/bin/env python3
"""
A well-documented Python module with proper structure.
"""

from typing import List, Optional


def calculate_total(items: List[float]) -> float:
    """Calculate the total of a list of numbers.
    
    Args:
        items: List of numbers to sum
        
    Returns:
        The total sum
    """
    return sum(items)


def format_currency(amount: float, currency: str = "USD") -> str:
    """Format amount as currency string.
    
    Args:
        amount: Amount to format
        currency: Currency code (default: USD)
        
    Returns:
        Formatted currency string
    """
    return f"{amount:.2f} {currency}"


if __name__ == "__main__":
    items = [10.99, 25.50, 5.75]
    total = calculate_total(items)
    formatted = format_currency(total)
    print(f"Total: {formatted}")
''')
    
    # Create comprehensive tests
    test_py = milestone_dir / "test_main.py"
    test_py.write_text('''#!/usr/bin/env python3
"""
Comprehensive tests for main module.
"""

import pytest
from main import calculate_total, format_currency


class TestCalculateTotal:
    """Test calculate_total function."""
    
    def test_positive_numbers(self):
        """Test with positive numbers."""
        assert calculate_total([1.0, 2.0, 3.0]) == 6.0
    
    def test_empty_list(self):
        """Test with empty list."""
        assert calculate_total([]) == 0.0
    
    def test_mixed_numbers(self):
        """Test with mixed positive and negative numbers."""
        assert calculate_total([10.0, -5.0, 2.5]) == 7.5
    
    def test_single_item(self):
        """Test with single item."""
        assert calculate_total([42.0]) == 42.0


class TestFormatCurrency:
    """Test format_currency function."""
    
    def test_default_currency(self):
        """Test with default USD currency."""
        assert format_currency(10.5) == "10.50 USD"
    
    def test_custom_currency(self):
        """Test with custom currency."""
        assert format_currency(25.75, "EUR") == "25.75 EUR"
    
    def test_zero_amount(self):
        """Test with zero amount."""
        assert format_currency(0.0) == "0.00 USD"
    
    def test_rounding(self):
        """Test proper rounding."""
        assert format_currency(10.999) == "11.00 USD"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
''')
    
    # Create README documentation
    readme = milestone_dir / "README.md"
    readme.write_text('''# Good Code Milestone

This milestone demonstrates high-quality Python code with:

## Features
- Type annotations for all functions
- Comprehensive docstrings
- 100% test coverage
- Clean code structure

## Testing
Run tests with: `python -m pytest test_main.py -v`

## Usage
```python
from main import calculate_total, format_currency

total = calculate_total([10.99, 25.50])
formatted = format_currency(total)
print(formatted)
```
''')
    
    return milestone_dir


@pytest.fixture
def bad_code_milestone(temp_git_repo):
    """Create a milestone with poor quality code."""
    milestone_dir = temp_git_repo / "milestone-bad"
    milestone_dir.mkdir()
    
    # Create poorly written code
    bad_py = milestone_dir / "bad_code.py"
    bad_py.write_text('''# No shebang, no docstring, many issues

import *  # Bad practice
import sys, os  # Multiple imports on one line

def badFunction(x,y):  # Poor naming, no types, no docstring
    result=x+y  # No spaces around operators
    if result>10:
        print("Result is big")  # Direct print instead of return/logging
    return result

class badClass:  # Poor naming
    def __init__(self,value):  # No spaces, no types
        self.value=value
        
    def process(self):  # No error handling
        return self.value/0  # Will always raise ZeroDivisionError

# Security issue: eval usage
def execute_code(user_input):
    return eval(user_input)  # Dangerous!

# No main guard
x = badFunction(5, 7)
obj = badClass(x)
print(obj.process())  # This will crash
''')
    
    # Create file with syntax errors
    syntax_error_py = milestone_dir / "syntax_error.py"
    syntax_error_py.write_text('''
def broken_function(
    # Missing closing parenthesis and colon

def another_function():
    return "missing quote

# Invalid indentation
if True:
print("Bad indentation")

# Unclosed bracket
my_list = [1, 2, 3
''')
    
    return milestone_dir


class TestReviewPromoteIntegration:
    """Integration tests for review → promote workflow."""

    @patch("agents.review.reviewer_agent.get_provider")
    def test_good_code_review_passes(self, mock_get_provider, good_code_milestone):
        """Test that good code passes review and can be promoted."""
        # Mock AI provider to return positive review
        mock_provider = MagicMock()
        mock_provider.generate_code.return_value = """{
            "summary": "Code quality is excellent with comprehensive tests and documentation",
            "comments": [
                {"file": "main.py", "line": 0, "severity": "info", "message": "Well-structured code with good practices"},
                {"file": "test_main.py", "line": 0, "severity": "info", "message": "Comprehensive test coverage"}
            ],
            "insights": [
                "Code follows Python best practices",
                "Excellent type annotations and documentation",
                "Comprehensive test suite"
            ]
        }"""
        mock_get_provider.return_value = mock_provider
        
        # Mock static analysis tools to return clean results
        with patch.object(ReviewerAgent, '_run_ruff') as mock_ruff, \
             patch.object(ReviewerAgent, '_run_mypy') as mock_mypy, \
             patch.object(ReviewerAgent, '_run_pytest') as mock_pytest:
            
            mock_ruff.return_value = {
                "success": True,
                "violations": [],
                "error_count": 0,
                "warning_count": 0,
                "return_code": 0
            }
            
            mock_mypy.return_value = {
                "success": True,
                "output": "",
                "errors": "",
                "return_code": 0,
                "has_errors": False
            }
            
            mock_pytest.return_value = {
                "success": True,
                "output": "8 passed",
                "errors": "",
                "return_code": 0,
                "test_files": 1,
                "passed": True
            }
            
            # Run review
            reviewer = ReviewerAgent()
            review_result = reviewer.review(good_code_milestone)
            
            # Verify review passes
            assert review_result["status"] == "pass"
            assert "excellent" in review_result["summary"].lower()
            
            # Verify review report was created
            report_file = good_code_milestone / "review-report.md"
            assert report_file.exists()
            
            # Test status extraction
            status = extract_status_from_report(report_file)
            assert status == "pass"

    @patch("agents.review.reviewer_agent.get_provider")
    def test_bad_code_review_fails(self, mock_get_provider, bad_code_milestone):
        """Test that bad code fails review and blocks promotion."""
        # Mock AI provider to return negative review
        mock_provider = MagicMock()
        mock_provider.generate_code.return_value = """{
            "summary": "Multiple critical security and quality issues found",
            "comments": [
                {"file": "bad_code.py", "line": 3, "severity": "high", "message": "Wildcard import is dangerous and pollutes namespace"},
                {"file": "bad_code.py", "line": 23, "severity": "high", "message": "eval() usage is a critical security vulnerability"},
                {"file": "bad_code.py", "line": 18, "severity": "high", "message": "Division by zero will always raise exception"},
                {"file": "syntax_error.py", "line": 2, "severity": "high", "message": "Syntax error: missing parenthesis"}
            ],
            "insights": [
                "Critical security vulnerabilities detected",
                "Code quality is below acceptable standards",
                "Multiple syntax errors present"
            ]
        }"""
        mock_get_provider.return_value = mock_provider
        
        # Mock static analysis tools to return failures
        with patch.object(ReviewerAgent, '_run_ruff') as mock_ruff, \
             patch.object(ReviewerAgent, '_run_mypy') as mock_mypy, \
             patch.object(ReviewerAgent, '_run_pytest') as mock_pytest:
            
            mock_ruff.return_value = {
                "success": True,
                "violations": [
                    {"code": "E999", "message": "SyntaxError: invalid syntax"},
                    {"code": "F403", "message": "unable to detect undefined names"},
                    {"code": "E302", "message": "expected 2 blank lines"}
                ],
                "error_count": 3,
                "warning_count": 2,
                "return_code": 1
            }
            
            mock_mypy.return_value = {
                "success": True,
                "output": "bad_code.py:6: error: Function is missing a type annotation",
                "errors": "",
                "return_code": 1,
                "has_errors": True
            }
            
            mock_pytest.return_value = {
                "success": True,
                "output": "",
                "errors": "",
                "return_code": 0,
                "test_files": 0,
                "passed": True,
                "no_tests": True
            }
            
            # Run review
            reviewer = ReviewerAgent()
            review_result = reviewer.review(bad_code_milestone)
            
            # Verify review fails
            assert review_result["status"] == "fail"
            assert "critical" in review_result["summary"].lower() or "issues" in review_result["summary"].lower()
            
            # Should have high severity comments
            high_severity_comments = [
                c for c in review_result["comments"]
                if c.get("severity") == "high"
            ]
            assert len(high_severity_comments) >= 3
            
            # Test status extraction
            report_file = bad_code_milestone / "review-report.md"
            assert report_file.exists()
            status = extract_status_from_report(report_file)
            assert status == "fail"

    def test_github_review_integration_offline(self, good_code_milestone):
        """Test GitHub review integration in offline mode."""
        with patch.dict(os.environ, {"NO_NETWORK": "1"}):
            github_reviewer = GitHubReviewer()
            
            # Should gracefully handle offline mode
            status = github_reviewer.get_status()
            assert status["can_post_reviews"] is False
            assert status["no_network_mode"] is True
            
            # Should return appropriate failure response
            sample_review = {
                "status": "pass",
                "summary": "Test review",
                "comments": [],
                "static_analysis": {}
            }
            
            result = github_reviewer.post_review_to_pr(sample_review)
            assert result["success"] is False
            assert result["reason"] == "offline_mode"

    @patch("subprocess.run")
    def test_github_review_integration_with_gh(self, mock_run, good_code_milestone):
        """Test GitHub review integration with gh CLI."""
        # Mock gh CLI responses
        mock_run.side_effect = [
            MagicMock(returncode=0),  # gh --version
            MagicMock(returncode=0),  # gh auth status
            MagicMock(returncode=0, stdout='{"number": 42}'),  # gh pr view
            MagicMock(returncode=0),  # post comment 1
            MagicMock(returncode=0)   # post summary comment
        ]
        
        github_reviewer = GitHubReviewer()
        
        sample_review = {
            "status": "pass",
            "summary": "Code review completed successfully",
            "comments": [
                {"file": "main.py", "line": 10, "severity": "info", "message": "Good code structure"}
            ],
            "static_analysis": {
                "ruff": {"success": True, "error_count": 0, "warning_count": 0},
                "mypy": {"success": True, "has_errors": False},
                "pytest": {"success": True, "passed": True, "test_files": 1}
            },
            "ai_insights": ["Code follows best practices"]
        }
        
        result = github_reviewer.post_review_to_pr(sample_review)
        
        assert result["success"] is True
        assert result["pr_number"] == 42
        assert "inline_comments" in result
        assert "summary_comment" in result

    def test_promotion_workflow_logic(self, temp_git_repo):
        """Test promotion workflow logic without actual Git operations."""
        from scripts.check_review_status import extract_status_from_report
        
        # Create a passing review report
        review_dir = temp_git_repo / "promotion_test"
        review_dir.mkdir()
        
        report_file = review_dir / "review-report.md"
        report_file.write_text("""# Code Review Report

**Status**: PASS
**Timestamp**: 2024-01-01 12:00:00

## Summary

Code quality is excellent with no issues found.

## Static Analysis Results

### ✅ Ruff Linter
- Errors: 0
- Warnings: 0

### ✅ MyPy Type Checking
- Status: PASS

### ✅ Tests
- Status: PASS (5 test files)

## Review Comments

No issues found.

---
*Generated by SoloPilot ReviewerAgent*
""")
        
        # Test status extraction
        status = extract_status_from_report(report_file)
        assert status == "pass"
        
        # Create a failing review report
        failing_report = review_dir / "failing-review-report.md"
        failing_report.write_text("""# Code Review Report

**Status**: FAIL
**Timestamp**: 2024-01-01 12:00:00

## Summary

Multiple critical issues found that require immediate attention.

## Static Analysis Results

### ❌ Ruff Linter
- Errors: 3
- Warnings: 5

### ❌ MyPy Type Checking
- Status: FAIL

## Review Comments

### 🔴 bad_code.py:15
Security vulnerability: eval() usage detected

---
*Generated by SoloPilot ReviewerAgent*
""")
        
        # Test failing status extraction
        fail_status = extract_status_from_report(failing_report)
        assert fail_status == "fail"

    def test_review_report_parsing_for_github(self, good_code_milestone):
        """Test parsing review report for GitHub posting."""
        from scripts.post_review_to_pr import parse_review_report
        
        # Create a sample review report
        report_file = good_code_milestone / "sample-review-report.md"
        report_file.write_text("""# Code Review Report

**Status**: PASS
**Timestamp**: 2024-01-01 12:00:00
**Milestone**: test-milestone

## Summary

Code quality looks good with minor improvements needed.

## Static Analysis Results

### ✅ Ruff Linter
- Errors: 0
- Warnings: 2

### ✅ MyPy Type Checking
- Status: PASS

### ✅ Tests
- Status: PASS (1 test files)

## Review Comments

### 🟡 main.py:10

Consider adding more comprehensive error handling.

### ℹ️ general

Overall code structure is well organized.

## AI Insights

- Code follows Python best practices
- Test coverage could be improved

---
*Generated by SoloPilot ReviewerAgent*
""")
        
        # Parse the report
        parsed = parse_review_report(report_file)
        
        assert parsed["status"] == "pass"
        assert "Code quality looks good" in parsed["summary"]
        assert len(parsed["comments"]) >= 1
        assert len(parsed["ai_insights"]) >= 1
        assert "static_analysis" in parsed

    def test_end_to_end_workflow_simulation(self, good_code_milestone):
        """Test complete end-to-end workflow simulation."""
        # Step 1: Run review (mocked)
        with patch("agents.review.reviewer_agent.get_provider") as mock_provider_getter:
            mock_provider = MagicMock()
            mock_provider.generate_code.return_value = """{
                "summary": "Code review completed successfully",
                "comments": [],
                "insights": ["Good code quality"]
            }"""
            mock_provider_getter.return_value = mock_provider
            
            with patch.object(ReviewerAgent, '_run_ruff') as mock_ruff, \
                 patch.object(ReviewerAgent, '_run_mypy') as mock_mypy, \
                 patch.object(ReviewerAgent, '_run_pytest') as mock_pytest:
                
                # Mock clean static analysis results
                mock_ruff.return_value = {"success": True, "error_count": 0, "warning_count": 0}
                mock_mypy.return_value = {"success": True, "has_errors": False}
                mock_pytest.return_value = {"success": True, "passed": True, "test_files": 1}
                
                reviewer = ReviewerAgent()
                review_result = reviewer.review(good_code_milestone)
        
        # Step 2: Verify review passes
        assert review_result["status"] == "pass"
        
        # Step 3: Test GitHub integration (offline mode)
        with patch.dict(os.environ, {"NO_NETWORK": "1"}):
            github_reviewer = GitHubReviewer()
            github_result = github_reviewer.post_review_to_pr(review_result)
            
            # Should gracefully handle offline mode
            assert github_result["success"] is False
            assert github_result["reason"] == "offline_mode"
        
        # Step 4: Test promotion logic
        report_file = good_code_milestone / "review-report.md"
        assert report_file.exists()
        
        status = extract_status_from_report(report_file)
        assert status == "pass"
        
        # In a real promotion, this would trigger git operations
        # Here we just verify the logic works correctly


class TestCIWorkflowIntegration:
    """Test CI workflow components."""

    def test_sonarcloud_configuration_exists(self):
        """Test that SonarCloud configuration file exists."""
        sonar_file = project_root / "sonar-project.properties"
        assert sonar_file.exists()
        
        content = sonar_file.read_text()
        assert "sonar.projectKey" in content
        assert "sonar.sources" in content
        assert "sonar.tests" in content

    def test_ci_workflow_updated(self):
        """Test that CI workflow includes new jobs."""
        ci_file = project_root / ".github" / "workflows" / "ci.yml"
        assert ci_file.exists()
        
        content = ci_file.read_text()
        assert "sonarcloud:" in content
        assert "code-review:" in content
        assert "promote:" in content
        assert "SonarCloud Scan" in content

    def test_makefile_targets_added(self):
        """Test that new Makefile targets are available."""
        makefile = project_root / "Makefile"
        assert makefile.exists()
        
        content = makefile.read_text()
        assert "review:" in content
        assert "promote:" in content
        assert "announce:" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])