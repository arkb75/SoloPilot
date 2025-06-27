#!/usr/bin/env python3
"""
GitHub Review Integration for SoloPilot

Posts AI review findings as inline comments and summary comments on GitHub PRs.
Uses GitHub CLI (gh) for API interactions with graceful offline fallback.
"""

import json
import os
import subprocess
import time
from typing import Any, Dict, List, Optional


class GitHubReviewer:
    """GitHub integration for posting AI review findings to PRs."""

    def __init__(self):
        """Initialize GitHubReviewer with environment-based configuration."""
        self.github_token = os.getenv("GITHUB_TOKEN")
        self.no_network = os.getenv("NO_NETWORK") == "1"
        self.gh_available = self._check_gh_available()

    def _check_gh_available(self) -> bool:
        """Check if GitHub CLI is available and authenticated."""
        if self.no_network:
            return False

        try:
            # Check if gh CLI is installed
            result = subprocess.run(["gh", "--version"], capture_output=True, timeout=5)

            if result.returncode != 0:
                return False

            # Check if authenticated
            auth_result = subprocess.run(["gh", "auth", "status"], capture_output=True, timeout=10)

            return auth_result.returncode == 0

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def post_review_to_pr(
        self, review_result: Dict[str, Any], pr_number: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Post AI review findings to GitHub PR.

        Args:
            review_result: Review result from ReviewerAgent
            pr_number: Optional PR number (auto-detected if not provided)

        Returns:
            Dictionary with posting results and status
        """
        if not self._can_post_review():
            return {
                "success": False,
                "reason": "offline_mode",
                "message": "Skipping GitHub review posting (offline mode or no auth)",
            }

        try:
            # Auto-detect PR number if not provided
            if pr_number is None:
                pr_number = self._get_current_pr_number()

            if pr_number is None:
                return {
                    "success": False,
                    "reason": "no_pr",
                    "message": "No open PR found for current branch",
                }

            # Post inline comments
            inline_results = self._post_inline_comments(review_result, pr_number)

            # Post summary comment
            summary_result = self._post_summary_comment(review_result, pr_number)

            return {
                "success": True,
                "pr_number": pr_number,
                "inline_comments": inline_results,
                "summary_comment": summary_result,
                "timestamp": time.time(),
            }

        except Exception as e:
            return {"success": False, "reason": "error", "message": f"Failed to post review: {e}"}

    def _can_post_review(self) -> bool:
        """Check if we can post reviews to GitHub."""
        return not self.no_network and self.gh_available

    def _get_current_pr_number(self) -> Optional[int]:
        """Get PR number for current branch using gh CLI."""
        try:
            result = subprocess.run(
                ["gh", "pr", "view", "--json", "number"], capture_output=True, text=True, timeout=10
            )

            if result.returncode == 0:
                pr_data = json.loads(result.stdout)
                return pr_data.get("number")

        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass

        return None

    def _post_inline_comments(
        self, review_result: Dict[str, Any], pr_number: int
    ) -> Dict[str, Any]:
        """Post inline comments for specific file/line issues."""
        comments = review_result.get("comments", [])
        posted_comments = []
        failed_comments = []

        for comment in comments:
            file_path = comment.get("file", "")
            line_number = comment.get("line", 0)
            message = comment.get("message", "")
            severity = comment.get("severity", "info")

            # Skip general comments for inline posting
            if file_path == "general" or line_number <= 0:
                continue

            # Format comment with severity
            severity_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢", "info": "ℹ️"}.get(
                severity, "ℹ️"
            )

            formatted_message = f"{severity_emoji} **{severity.upper()}**: {message}"

            # Post inline comment using gh CLI
            success = self._post_single_inline_comment(
                pr_number, file_path, line_number, formatted_message
            )

            if success:
                posted_comments.append(
                    {
                        "file": file_path,
                        "line": line_number,
                        "message": message,
                        "severity": severity,
                    }
                )
            else:
                failed_comments.append(
                    {
                        "file": file_path,
                        "line": line_number,
                        "message": message,
                        "error": "Failed to post comment",
                    }
                )

        return {
            "posted": len(posted_comments),
            "failed": len(failed_comments),
            "posted_comments": posted_comments,
            "failed_comments": failed_comments,
        }

    def _post_single_inline_comment(
        self, pr_number: int, file_path: str, line_number: int, message: str
    ) -> bool:
        """Post a single inline comment to PR."""
        try:
            # Use gh CLI to post review comment
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "comment",
                    str(pr_number),
                    "--body",
                    f"**File: {file_path}:{line_number}**\n\n{message}",
                ],
                capture_output=True,
                timeout=15,
            )

            return result.returncode == 0

        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _post_summary_comment(
        self, review_result: Dict[str, Any], pr_number: int
    ) -> Dict[str, Any]:
        """Post comprehensive summary comment with review findings."""
        try:
            summary_body = self._build_summary_comment(review_result)

            result = subprocess.run(
                ["gh", "pr", "comment", str(pr_number), "--body", summary_body],
                capture_output=True,
                text=True,
                timeout=15,
            )

            if result.returncode == 0:
                return {"success": True, "comment_length": len(summary_body)}
            else:
                return {"success": False, "error": result.stderr or "Unknown error posting summary"}

        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            return {"success": False, "error": f"Failed to post summary: {e}"}

    def _build_summary_comment(self, review_result: Dict[str, Any]) -> str:
        """Build comprehensive summary comment for PR."""
        status = review_result.get("status", "unknown")
        summary = review_result.get("summary", "Review completed")
        comments = review_result.get("comments", [])
        static_analysis = review_result.get("static_analysis", {})
        ai_insights = review_result.get("ai_insights", [])

        # Status emoji
        status_emoji = "✅" if status == "pass" else "❌"

        lines = [
            f"## {status_emoji} AI Code Review Results",
            "",
            f"**Status**: {status.upper()}",
            f"**Summary**: {summary}",
            "",
            "### 📊 Static Analysis Results",
            "",
        ]

        # Add static analysis summary
        ruff_results = static_analysis.get("ruff", {})
        if ruff_results.get("success"):
            error_count = ruff_results.get("error_count", 0)
            warning_count = ruff_results.get("warning_count", 0)
            ruff_status = "✅" if error_count == 0 else "❌"
            lines.extend(
                [f"- **Ruff Linter**: {ruff_status} {error_count} errors, {warning_count} warnings"]
            )

        mypy_results = static_analysis.get("mypy", {})
        if mypy_results.get("success"):
            mypy_status = "✅" if not mypy_results.get("has_errors") else "❌"
            lines.extend(
                [
                    f"- **MyPy Type Check**: {mypy_status} {'PASS' if not mypy_results.get('has_errors') else 'FAIL'}"
                ]
            )

        pytest_results = static_analysis.get("pytest", {})
        if pytest_results.get("success"):
            if pytest_results.get("no_tests"):
                test_status = "⚠️ NO TESTS"
            else:
                test_status = "✅ PASS" if pytest_results.get("passed") else "❌ FAIL"
            lines.extend(
                [f"- **Tests**: {test_status} ({pytest_results.get('test_files', 0)} test files)"]
            )

        # Add file statistics
        file_stats = static_analysis.get("file_stats", {})
        if file_stats:
            lines.extend(
                [
                    "",
                    "### 📁 File Statistics",
                    f"- Python files: {file_stats.get('python_files', 0)}",
                    f"- Test files: {file_stats.get('test_files', 0)}",
                    f"- Total lines: {file_stats.get('total_lines', 0)}",
                    "",
                ]
            )

        # Add comment summary by severity
        if comments:
            severity_counts = {}
            for comment in comments:
                severity = comment.get("severity", "info")
                severity_counts[severity] = severity_counts.get(severity, 0) + 1

            lines.extend(["### 💬 Review Comments Summary", ""])

            for severity in ["high", "medium", "low", "info"]:
                count = severity_counts.get(severity, 0)
                if count > 0:
                    emoji = {"high": "🔴", "medium": "🟡", "low": "🟢", "info": "ℹ️"}[severity]
                    lines.append(f"- {emoji} **{severity.upper()}**: {count} issues")

            lines.append("")

        # Add AI insights
        if ai_insights:
            lines.extend(["### 🤖 AI Insights", ""])
            for insight in ai_insights[:5]:  # Limit to 5 insights
                lines.append(f"- {insight}")
            lines.append("")

        # Add footer
        lines.extend(
            [
                "---",
                f"*🤖 Generated by SoloPilot AI Reviewer at {time.strftime('%Y-%m-%d %H:%M:%S')}*",
            ]
        )

        return "\n".join(lines)

    def get_pr_info(self, pr_number: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get information about current or specified PR."""
        if not self._can_post_review():
            return None

        try:
            cmd = ["gh", "pr", "view", "--json", "number,title,body,state,author,url"]
            if pr_number:
                cmd.extend([str(pr_number)])

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

            if result.returncode == 0:
                return json.loads(result.stdout)

        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass

        return None

    def list_open_prs(self) -> List[Dict[str, Any]]:
        """List all open PRs in the repository."""
        if not self._can_post_review():
            return []

        try:
            result = subprocess.run(
                ["gh", "pr", "list", "--json", "number,title,author,state,url"],
                capture_output=True,
                text=True,
                timeout=15,
            )

            if result.returncode == 0:
                return json.loads(result.stdout)

        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
            pass

        return []

    def get_status(self) -> Dict[str, Any]:
        """Get GitHub integration status information."""
        return {
            "github_token_available": bool(self.github_token),
            "no_network_mode": self.no_network,
            "gh_cli_available": self.gh_available,
            "can_post_reviews": self._can_post_review(),
            "auth_status": "authenticated" if self.gh_available else "not_authenticated",
        }


def main():
    """Main function for testing GitHub integration."""
    github_reviewer = GitHubReviewer()

    # Print status
    status = github_reviewer.get_status()
    print("GitHub Integration Status:")
    for key, value in status.items():
        print(f"  {key}: {value}")

    # List open PRs if available
    if status["can_post_reviews"]:
        prs = github_reviewer.list_open_prs()
        print(f"\nOpen PRs: {len(prs)}")
        for pr in prs[:3]:  # Show first 3
            print(f"  #{pr['number']}: {pr['title']}")


if __name__ == "__main__":
    main()
