#!/usr/bin/env python3
"""
Unit tests for GitHub Review Integration

Tests GitHub API integration with mock responses and offline compatibility.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.github_review import GitHubReviewer


@pytest.fixture
def sample_review_result():
    """Sample review result for testing."""
    return {
        "status": "pass",
        "summary": "Code quality looks good with minor improvements needed",
        "comments": [
            {
                "file": "main.py",
                "line": 10,
                "severity": "medium",
                "message": "Consider adding type hints for better code clarity"
            },
            {
                "file": "utils.py", 
                "line": 25,
                "severity": "low",
                "message": "This function could be simplified"
            },
            {
                "file": "general",
                "line": 0,
                "severity": "info",
                "message": "Overall code structure is well organized"
            }
        ],
        "static_analysis": {
            "ruff": {
                "success": True,
                "violations": [],
                "error_count": 0,
                "warning_count": 2,
                "return_code": 0
            },
            "mypy": {
                "success": True,
                "output": "",
                "errors": "",
                "return_code": 0,
                "has_errors": False
            },
            "pytest": {
                "success": True,
                "output": "2 passed",
                "errors": "",
                "return_code": 0,
                "test_files": 1,
                "passed": True
            },
            "file_stats": {
                "python_files": 3,
                "test_files": 1,
                "total_lines": 150
            }
        },
        "ai_insights": [
            "Code follows Python best practices",
            "Test coverage could be improved",
            "Documentation is comprehensive"
        ],
        "timestamp": 1234567890
    }


@pytest.fixture
def failing_review_result():
    """Sample failing review result for testing."""
    return {
        "status": "fail",
        "summary": "Multiple critical issues found that need immediate attention",
        "comments": [
            {
                "file": "bad_code.py",
                "line": 15,
                "severity": "high",
                "message": "Security vulnerability: SQL injection risk"
            },
            {
                "file": "bad_code.py",
                "line": 23,
                "severity": "high", 
                "message": "Memory leak: resources not properly released"
            },
            {
                "file": "style.py",
                "line": 5,
                "severity": "medium",
                "message": "PEP 8 violation: function naming"
            }
        ],
        "static_analysis": {
            "ruff": {
                "success": True,
                "violations": [{"code": "E999", "message": "SyntaxError"}],
                "error_count": 3,
                "warning_count": 5,
                "return_code": 1
            },
            "mypy": {
                "success": True,
                "output": "error: Function is missing type annotation",
                "errors": "",
                "return_code": 1,
                "has_errors": True
            },
            "pytest": {
                "success": True,
                "output": "",
                "errors": "FAILED test_feature.py::test_security",
                "return_code": 1,
                "test_files": 2,
                "passed": False
            }
        },
        "ai_insights": [
            "Critical security issues require immediate attention",
            "Code quality is below acceptable standards"
        ]
    }


class TestGitHubReviewer:
    """Test cases for GitHubReviewer class."""

    def test_init_with_environment(self):
        """Test GitHubReviewer initialization with environment variables."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}):
            reviewer = GitHubReviewer()
            assert reviewer.github_token == "test_token"
            assert reviewer.no_network is False

    def test_init_offline_mode(self):
        """Test GitHubReviewer initialization in offline mode."""
        with patch.dict(os.environ, {"NO_NETWORK": "1"}):
            reviewer = GitHubReviewer()
            assert reviewer.no_network is True
            assert reviewer.gh_available is False

    @patch("subprocess.run")
    def test_check_gh_available_success(self, mock_run):
        """Test successful GitHub CLI availability check."""
        # Mock gh --version success
        mock_run.side_effect = [
            MagicMock(returncode=0),  # gh --version
            MagicMock(returncode=0)   # gh auth status
        ]
        
        reviewer = GitHubReviewer()
        assert reviewer.gh_available is True

    @patch("subprocess.run")
    def test_check_gh_available_not_installed(self, mock_run):
        """Test GitHub CLI not installed."""
        mock_run.side_effect = FileNotFoundError("gh command not found")
        
        reviewer = GitHubReviewer()
        assert reviewer.gh_available is False

    @patch("subprocess.run")
    def test_check_gh_available_not_authenticated(self, mock_run):
        """Test GitHub CLI installed but not authenticated."""
        mock_run.side_effect = [
            MagicMock(returncode=0),  # gh --version success
            MagicMock(returncode=1)   # gh auth status fails
        ]
        
        reviewer = GitHubReviewer()
        assert reviewer.gh_available is False

    def test_post_review_offline_mode(self, sample_review_result):
        """Test posting review in offline mode."""
        with patch.dict(os.environ, {"NO_NETWORK": "1"}):
            reviewer = GitHubReviewer()
            result = reviewer.post_review_to_pr(sample_review_result)
            
            assert result["success"] is False
            assert result["reason"] == "offline_mode"
            assert "offline mode" in result["message"]

    @patch("subprocess.run")
    def test_get_current_pr_number_success(self, mock_run):
        """Test successful PR number detection."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"number": 42}'
        )
        
        reviewer = GitHubReviewer()
        reviewer.gh_available = True
        
        pr_number = reviewer._get_current_pr_number()
        assert pr_number == 42

    @patch("subprocess.run")
    def test_get_current_pr_number_no_pr(self, mock_run):
        """Test PR number detection when no PR exists."""
        mock_run.return_value = MagicMock(returncode=1)
        
        reviewer = GitHubReviewer()
        reviewer.gh_available = True
        
        pr_number = reviewer._get_current_pr_number()
        assert pr_number is None

    @patch("subprocess.run")
    def test_post_review_success(self, mock_run, sample_review_result):
        """Test successful review posting."""
        # Mock gh pr view to return PR number
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout='{"number": 42}'),  # get PR number
            MagicMock(returncode=0),  # post inline comment 1
            MagicMock(returncode=0),  # post inline comment 2
            MagicMock(returncode=0)   # post summary comment
        ]
        
        reviewer = GitHubReviewer()
        reviewer.no_network = False
        reviewer.gh_available = True
        
        result = reviewer.post_review_to_pr(sample_review_result)
        
        assert result["success"] is True
        assert result["pr_number"] == 42
        assert "inline_comments" in result
        assert "summary_comment" in result

    @patch("subprocess.run")
    def test_post_review_no_pr_found(self, mock_run, sample_review_result):
        """Test review posting when no PR is found."""
        mock_run.return_value = MagicMock(returncode=1)  # no PR found
        
        reviewer = GitHubReviewer()
        reviewer.no_network = False
        reviewer.gh_available = True
        
        result = reviewer.post_review_to_pr(sample_review_result)
        
        assert result["success"] is False
        assert result["reason"] == "no_pr"

    @patch("subprocess.run")
    def test_post_inline_comments(self, mock_run, sample_review_result):
        """Test posting inline comments."""
        mock_run.return_value = MagicMock(returncode=0)
        
        reviewer = GitHubReviewer()
        reviewer.no_network = False
        reviewer.gh_available = True
        
        result = reviewer._post_inline_comments(sample_review_result, 42)
        
        # Should post 2 inline comments (excluding general comment)
        assert result["posted"] == 2
        assert result["failed"] == 0
        assert len(result["posted_comments"]) == 2

    @patch("subprocess.run")
    def test_post_inline_comments_with_failures(self, mock_run, sample_review_result):
        """Test posting inline comments with some failures."""
        # First comment succeeds, second fails
        mock_run.side_effect = [
            MagicMock(returncode=0),  # success
            MagicMock(returncode=1)   # failure
        ]
        
        reviewer = GitHubReviewer()
        reviewer.no_network = False
        reviewer.gh_available = True
        
        result = reviewer._post_inline_comments(sample_review_result, 42)
        
        assert result["posted"] == 1
        assert result["failed"] == 1

    def test_build_summary_comment_pass(self, sample_review_result):
        """Test building summary comment for passing review."""
        reviewer = GitHubReviewer()
        
        summary = reviewer._build_summary_comment(sample_review_result)
        
        assert "✅ AI Code Review Results" in summary
        assert "PASS" in summary
        assert "Static Analysis Results" in summary
        assert "Ruff Linter" in summary
        assert "MyPy Type Check" in summary
        assert "Tests" in summary
        assert "File Statistics" in summary
        assert "Review Comments Summary" in summary
        assert "AI Insights" in summary
        assert "SoloPilot AI Reviewer" in summary

    def test_build_summary_comment_fail(self, failing_review_result):
        """Test building summary comment for failing review."""
        reviewer = GitHubReviewer()
        
        summary = reviewer._build_summary_comment(failing_review_result)
        
        assert "❌ AI Code Review Results" in summary
        assert "FAIL" in summary
        assert "🔴 **HIGH**: 2 issues" in summary
        assert "🟡 **MEDIUM**: 1 issues" in summary

    @patch("subprocess.run")
    def test_get_pr_info_success(self, mock_run):
        """Test getting PR information."""
        pr_data = {
            "number": 42,
            "title": "Add new feature",
            "body": "This PR adds a new feature",
            "state": "OPEN",
            "author": {"login": "developer"},
            "url": "https://github.com/owner/repo/pull/42"
        }
        
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(pr_data)
        )
        
        reviewer = GitHubReviewer()
        reviewer.no_network = False
        reviewer.gh_available = True
        
        result = reviewer.get_pr_info()
        assert result == pr_data

    @patch("subprocess.run")
    def test_get_pr_info_offline(self, mock_run):
        """Test getting PR info in offline mode."""
        reviewer = GitHubReviewer()
        reviewer.no_network = True
        
        result = reviewer.get_pr_info()
        assert result is None

    @patch("subprocess.run")
    def test_list_open_prs(self, mock_run):
        """Test listing open PRs."""
        prs_data = [
            {"number": 42, "title": "Feature A", "author": {"login": "dev1"}},
            {"number": 43, "title": "Bug fix B", "author": {"login": "dev2"}}
        ]
        
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps(prs_data)
        )
        
        reviewer = GitHubReviewer()
        reviewer.no_network = False
        reviewer.gh_available = True
        
        result = reviewer.list_open_prs()
        assert len(result) == 2
        assert result[0]["number"] == 42

    def test_get_status(self):
        """Test getting GitHub integration status."""
        with patch.dict(os.environ, {"GITHUB_TOKEN": "test_token"}):
            reviewer = GitHubReviewer()
            status = reviewer.get_status()
            
            assert "github_token_available" in status
            assert "no_network_mode" in status
            assert "gh_cli_available" in status
            assert "can_post_reviews" in status
            assert "auth_status" in status

    def test_post_review_with_explicit_pr_number(self, sample_review_result):
        """Test posting review with explicitly provided PR number."""
        with patch.object(GitHubReviewer, '_post_inline_comments') as mock_inline, \
             patch.object(GitHubReviewer, '_post_summary_comment') as mock_summary:
            
            mock_inline.return_value = {"posted": 2, "failed": 0}
            mock_summary.return_value = {"success": True}
            
            reviewer = GitHubReviewer()
            reviewer.no_network = False
            reviewer.gh_available = True
            
            result = reviewer.post_review_to_pr(sample_review_result, pr_number=123)
            
            assert result["success"] is True
            assert result["pr_number"] == 123
            mock_inline.assert_called_once_with(sample_review_result, 123)
            mock_summary.assert_called_once_with(sample_review_result, 123)

    @patch("subprocess.run")
    def test_post_summary_comment_success(self, mock_run, sample_review_result):
        """Test successful summary comment posting."""
        mock_run.return_value = MagicMock(returncode=0)
        
        reviewer = GitHubReviewer()
        result = reviewer._post_summary_comment(sample_review_result, 42)
        
        assert result["success"] is True
        assert "comment_length" in result

    @patch("subprocess.run")
    def test_post_summary_comment_failure(self, mock_run, sample_review_result):
        """Test failed summary comment posting."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stderr="API rate limit exceeded"
        )
        
        reviewer = GitHubReviewer()
        result = reviewer._post_summary_comment(sample_review_result, 42)
        
        assert result["success"] is False
        assert "error" in result

    def test_can_post_review_conditions(self):
        """Test different conditions for posting reviews."""
        # Online with gh available
        reviewer = GitHubReviewer()
        reviewer.no_network = False
        reviewer.gh_available = True
        assert reviewer._can_post_review() is True
        
        # Offline mode
        reviewer.no_network = True
        reviewer.gh_available = True
        assert reviewer._can_post_review() is False
        
        # Online but gh not available
        reviewer.no_network = False
        reviewer.gh_available = False
        assert reviewer._can_post_review() is False


class TestGitHubReviewerIntegration:
    """Integration tests for GitHubReviewer."""

    def test_offline_graceful_degradation(self, sample_review_result):
        """Test that GitHub integration gracefully handles offline mode."""
        with patch.dict(os.environ, {"NO_NETWORK": "1"}):
            reviewer = GitHubReviewer()
            
            # All operations should return graceful failures
            assert reviewer.get_pr_info() is None
            assert reviewer.list_open_prs() == []
            
            result = reviewer.post_review_to_pr(sample_review_result)
            assert result["success"] is False
            assert result["reason"] == "offline_mode"

    def test_status_reporting(self):
        """Test comprehensive status reporting."""
        reviewer = GitHubReviewer()
        status = reviewer.get_status()
        
        # Should contain all expected keys
        expected_keys = [
            "github_token_available",
            "no_network_mode", 
            "gh_cli_available",
            "can_post_reviews",
            "auth_status"
        ]
        
        for key in expected_keys:
            assert key in status
            
        # Values should be appropriate types
        assert isinstance(status["github_token_available"], bool)
        assert isinstance(status["no_network_mode"], bool)
        assert isinstance(status["gh_cli_available"], bool)
        assert isinstance(status["can_post_reviews"], bool)
        assert isinstance(status["auth_status"], str)

    @patch("subprocess.run")
    def test_end_to_end_review_posting(self, mock_run, sample_review_result):
        """Test complete end-to-end review posting workflow."""
        # Mock all subprocess calls
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout='{"number": 42}'),  # get current PR
            MagicMock(returncode=0),  # post comment 1
            MagicMock(returncode=0),  # post comment 2
            MagicMock(returncode=0)   # post summary
        ]
        
        reviewer = GitHubReviewer()
        reviewer.no_network = False
        reviewer.gh_available = True
        
        result = reviewer.post_review_to_pr(sample_review_result)
        
        # Verify complete workflow
        assert result["success"] is True
        assert result["pr_number"] == 42
        assert "inline_comments" in result
        assert "summary_comment" in result
        assert "timestamp" in result
        
        # Verify proper number of subprocess calls
        assert mock_run.call_count == 4


if __name__ == "__main__":
    pytest.main([__file__, "-v"])