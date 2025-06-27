#!/usr/bin/env python3
"""
Check Review Status Script

Reads a review report markdown file and extracts the status.
Used by CI pipeline to determine if code should be promoted.
"""

import re
import sys
from pathlib import Path


def extract_status_from_report(report_path: Path) -> str:
    """
    Extract status from review report markdown file.

    Args:
        report_path: Path to review-report.md file

    Returns:
        Status string: 'pass', 'fail', or 'unknown'
    """
    if not report_path.exists():
        return "unknown"

    try:
        content = report_path.read_text(encoding="utf-8")

        # Look for status line: **Status**: PASS or **Status**: FAIL
        status_match = re.search(r"\*\*Status\*\*:\s*(\w+)", content, re.IGNORECASE)

        if status_match:
            status = status_match.group(1).lower()
            if status in ["pass", "fail"]:
                return status

        # Fallback: look for status emoji in headers
        if "✅" in content and "pass" in content.lower():
            return "pass"
        elif "❌" in content and "fail" in content.lower():
            return "fail"

        return "unknown"

    except (IOError, UnicodeDecodeError):
        return "unknown"


def main():
    """Main function for CLI usage."""
    if len(sys.argv) != 2:
        print("Usage: python check_review_status.py <path_to_review_report.md>")
        sys.exit(1)

    report_path = Path(sys.argv[1])
    status = extract_status_from_report(report_path)

    # Print status for shell capture
    print(status)

    # Exit with appropriate code
    if status == "pass":
        sys.exit(0)
    elif status == "fail":
        sys.exit(1)
    else:
        sys.exit(2)  # Unknown status


if __name__ == "__main__":
    main()
