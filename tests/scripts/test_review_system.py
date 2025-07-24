#!/usr/bin/env python3
"""
Test Review System Script

Tests the AI review system with intentionally bad code to ensure
quality gates are working properly.
"""

import subprocess
import sys
from pathlib import Path


def run_review_on_bad_code():
    """Run the review system on our test bad code file."""
    print("🔍 Testing AI Review System with Bad Code Example")
    print("=" * 60)

    # Create test directory
    test_dir = Path("temp_review_test/milestone-test")
    test_dir.mkdir(parents=True, exist_ok=True)

    # Copy bad code file to test directory
    bad_code_file = Path("tests/test_bad_code_example.py")
    if not bad_code_file.exists():
        print("❌ Bad code test file not found!")
        return False

    target_file = test_dir / "test_bad_code_example.py"
    target_file.write_text(bad_code_file.read_text())

    print(f"📄 Copied bad code file to: {target_file}")

    # Run reviewer agent
    print("\n🤖 Running AI Reviewer Agent...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "src.agents.review.reviewer_agent", str(test_dir)],
            capture_output=True,
            text=True,
            timeout=120,
        )

        print("\nReviewer Output:")
        print("-" * 40)
        print(result.stdout)
        if result.stderr:
            print("Errors:")
            print(result.stderr)
        print("-" * 40)

    except subprocess.TimeoutExpired:
        print("❌ Review timed out!")
        return False
    except Exception as e:
        print(f"❌ Error running reviewer: {e}")
        return False

    # Check review report
    report_file = test_dir / "review-report.md"
    if not report_file.exists():
        print("❌ Review report not generated!")
        return False

    print(f"\n📊 Review report generated: {report_file}")

    # Check review status
    try:
        status_result = subprocess.run(
            [sys.executable, "scripts/check_review_status.py", str(report_file)],
            capture_output=True,
            text=True,
        )

        status = status_result.stdout.strip()
        print(f"\n🏷️  Review Status: {status}")

        # Expect FAIL for bad code
        if status == "fail":
            print("✅ Review correctly identified issues in bad code!")

            # Display some of the report
            print("\n📋 Review Report Preview:")
            print("-" * 60)
            report_content = report_file.read_text()
            preview_lines = report_content.split("\n")[:50]  # First 50 lines
            print("\n".join(preview_lines))
            if len(report_content.split("\n")) > 50:
                print("\n... (truncated) ...")
            print("-" * 60)

            return True
        else:
            print(f"❌ Expected FAIL status for bad code, got: {status}")
            return False

    except Exception as e:
        print(f"❌ Error checking review status: {e}")
        return False


def test_github_integration():
    """Test GitHub integration components."""
    print("\n\n🔧 Testing GitHub Integration Components")
    print("=" * 60)

    # Check if GitHub utilities exist
    github_review_path = Path("utils/github_review.py")
    if github_review_path.exists():
        print("✅ GitHub review utility found")
    else:
        print("❌ GitHub review utility missing")
        return False

    # Check if post script exists
    post_script = Path("scripts/post_review_to_pr.py")
    if post_script.exists():
        print("✅ Post review to PR script found")
    else:
        print("❌ Post review to PR script missing")
        return False

    # Test GitHub reviewer status
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from src.utils.github_review import GitHubReviewer; "
                "reviewer = GitHubReviewer(); "
                "import json; "
                "print(json.dumps(reviewer.get_status(), indent=2))",
            ],
            capture_output=True,
            text=True,
        )

        print("\n📊 GitHub Integration Status:")
        print(result.stdout)

        if result.returncode == 0:
            print("✅ GitHub integration components working")
            return True
        else:
            print("❌ GitHub integration error:")
            print(result.stderr)
            return False

    except Exception as e:
        print(f"❌ Error testing GitHub integration: {e}")
        return False


def main():
    """Run all review system tests."""
    print("🚀 SoloPilot AI Review System Test")
    print("=" * 80)

    # Test 1: Review bad code
    test1_passed = run_review_on_bad_code()

    # Test 2: GitHub integration
    test2_passed = test_github_integration()

    # Summary
    print("\n\n📊 Test Summary")
    print("=" * 60)
    print(f"Bad Code Review Test: {'✅ PASSED' if test1_passed else '❌ FAILED'}")
    print(f"GitHub Integration Test: {'✅ PASSED' if test2_passed else '❌ FAILED'}")

    if test1_passed and test2_passed:
        print("\n✅ All tests passed! Review system is working correctly.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed. Please check the output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
