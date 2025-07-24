#!/usr/bin/env python3
"""
Post Review to PR Script

Posts AI review findings to GitHub PR using the GitHubReviewer utility.
Used by CI pipeline to automatically post review comments.
"""

import json
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.github_review import GitHubReviewer


def parse_review_report(report_path: Path) -> dict:
    """
    Parse review report markdown file into review result format.

    Args:
        report_path: Path to review-report.md file

    Returns:
        Dictionary in ReviewerAgent result format
    """
    if not report_path.exists():
        return {
            "status": "unknown",
            "summary": "Review report not found",
            "comments": [],
            "static_analysis": {},
            "ai_insights": [],
        }

    try:
        content = report_path.read_text(encoding="utf-8")

        # Extract status
        status = "unknown"
        if "**Status**: PASS" in content:
            status = "pass"
        elif "**Status**: FAIL" in content:
            status = "fail"

        # Extract summary (first paragraph after status)
        summary_start = content.find("## Summary")
        summary = "Review completed"
        if summary_start != -1:
            summary_section = content[summary_start : content.find("\n##", summary_start + 1)]
            lines = summary_section.split("\n")[2:]  # Skip header and empty line
            summary = " ".join(line.strip() for line in lines if line.strip())[:200]

        # Parse static analysis results
        static_analysis = {}

        # Extract ruff results
        if "Ruff Linter" in content:
            if "✅" in content and "Ruff Linter" in content:
                static_analysis["ruff"] = {"success": True, "error_count": 0, "warning_count": 0}
            elif "❌" in content and "Ruff Linter" in content:
                static_analysis["ruff"] = {"success": True, "error_count": 1, "warning_count": 0}

        # Extract basic comments (simplified parsing)
        comments = []
        if "Review Comments" in content:
            # Look for file references in markdown
            import re

            file_matches = re.findall(
                r"### [🔴🟡🟢ℹ️]+ (.+?)\n\n(.+?)(?=\n###|\n##|\Z)", content, re.DOTALL
            )
            for file_ref, message in file_matches:
                severity = "medium"
                if "🔴" in content:
                    severity = "high"
                elif "🟢" in content:
                    severity = "low"
                elif "ℹ️" in content:
                    severity = "info"

                comments.append(
                    {
                        "file": file_ref.split(":")[0] if ":" in file_ref else file_ref,
                        "line": (
                            int(file_ref.split(":")[1])
                            if ":" in file_ref and file_ref.split(":")[1].isdigit()
                            else 0
                        ),
                        "severity": severity,
                        "message": message.strip(),
                    }
                )

        # Extract AI insights
        ai_insights = []
        insights_start = content.find("## AI Insights")
        if insights_start != -1:
            insights_section = content[insights_start : content.find("\n##", insights_start + 1)]
            for line in insights_section.split("\n"):
                if line.strip().startswith("- "):
                    ai_insights.append(line.strip()[2:])

        return {
            "status": status,
            "summary": summary,
            "comments": comments,
            "static_analysis": static_analysis,
            "ai_insights": ai_insights,
        }

    except (OSError, UnicodeDecodeError) as e:
        return {
            "status": "error",
            "summary": f"Failed to parse review report: {e}",
            "comments": [],
            "static_analysis": {},
            "ai_insights": [],
        }


def main():
    """Main function for CLI usage."""
    if len(sys.argv) != 2:
        print("Usage: python post_review_to_pr.py <path_to_review_report.md>")
        sys.exit(1)

    report_path = Path(sys.argv[1])

    # Parse review report
    review_result = parse_review_report(report_path)

    # Initialize GitHub reviewer
    github_reviewer = GitHubReviewer()

    # Check if we can post reviews
    status = github_reviewer.get_status()
    print(f"GitHub Integration Status: {json.dumps(status, indent=2)}")

    if not status["can_post_reviews"]:
        print("Cannot post reviews - skipping GitHub integration")
        print(
            f"Reason: No network={status['no_network_mode']}, "
            f"GH CLI available={status['gh_cli_available']}, "
            f"Token available={status['github_token_available']}"
        )
        return

    # Post review to PR
    print("Posting review to GitHub PR...")
    result = github_reviewer.post_review_to_pr(review_result)

    print(f"Review posting result: {json.dumps(result, indent=2)}")

    if result["success"]:
        print(f"✅ Successfully posted review to PR #{result['pr_number']}")
        print(f"Posted {result['inline_comments']['posted']} inline comments")
        if result["summary_comment"]["success"]:
            print("✅ Posted summary comment")
        else:
            print("❌ Failed to post summary comment")
    else:
        print(f"❌ Failed to post review: {result.get('message', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
