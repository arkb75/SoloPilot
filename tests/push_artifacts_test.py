#!/usr/bin/env python3
"""
Unit tests for SoloPilot push artifacts script.
Tests git-push storage layer functionality with mocked subprocess calls.
"""

import json
import shutil
import subprocess

# Add project root to path for imports
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.push_artifacts import run_command, setup_git_repo, validate_git_url


class TestPushArtifacts:
    """Test cases for push artifacts functionality."""

    @pytest.fixture
    def temp_src_dir(self):
        """Create a temporary source directory with some files."""
        temp_dir = Path(tempfile.mkdtemp())

        # Create some mock artifact files
        (temp_dir / "manifest.json").write_text('{"project": "test"}')
        (temp_dir / "README.md").write_text("# Test Project")

        milestone_dir = temp_dir / "milestone-1"
        milestone_dir.mkdir()
        (milestone_dir / "implementation.js").write_text("// Test code")
        (milestone_dir / "test.js").write_text("// Test tests")

        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_validate_git_url_valid_urls(self):
        """Test git URL validation with valid URLs."""
        valid_urls = [
            "https://github.com/user/repo.git",
            "git@github.com:user/repo.git",
            "ssh://git@github.com/user/repo.git",
            "https://gitlab.com/user/repo.git",
        ]

        for url in valid_urls:
            assert validate_git_url(url), f"Should validate as valid: {url}"

    def test_validate_git_url_invalid_urls(self):
        """Test git URL validation with invalid URLs."""
        invalid_urls = [
            "",
            "not-a-url",
            "http://example.com",  # No .git and not a known git pattern
            "ftp://example.com/repo.git",
        ]

        for url in invalid_urls:
            assert not validate_git_url(url), f"Should validate as invalid: {url}"

    @patch("subprocess.run")
    def test_run_command_success(self, mock_run):
        """Test successful command execution."""
        mock_run.return_value = MagicMock(returncode=0, stdout="success output", stderr="")

        result = run_command(["git", "status"])

        assert result.stdout == "success output"
        mock_run.assert_called_once_with(
            ["git", "status"], cwd=None, capture_output=True, text=True, check=True
        )

    @patch("subprocess.run")
    def test_run_command_failure(self, mock_run):
        """Test command execution failure."""
        mock_run.side_effect = subprocess.CalledProcessError(
            1, ["git", "status"], stderr="fatal: not a git repository"
        )

        with pytest.raises(subprocess.CalledProcessError):
            run_command(["git", "status"])

    @patch("subprocess.run")
    def test_run_command_not_found(self, mock_run):
        """Test command not found error."""
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(FileNotFoundError):
            run_command(["nonexistent-command"])

    @patch("subprocess.run")
    def test_setup_git_repo_success(self, mock_run, temp_src_dir):
        """Test successful git repository setup and push."""
        # Mock all git commands to succeed
        mock_run.return_value = MagicMock(
            returncode=0, stdout="abc1234567890", stderr=""  # Mock commit hash
        )

        git_url = "https://github.com/user/test-repo.git"
        timestamp = "20250611_123456"

        result = setup_git_repo(temp_src_dir, git_url, timestamp)

        # Verify result structure
        assert result["branch_name"] == f"artifact/{timestamp}"
        assert result["remote_url"] == git_url
        assert result["timestamp"] == timestamp
        assert result["status"] == "pushed"
        assert "github.com" in result["branch_url"]

        # Verify git commands were called
        expected_calls = [
            call(["git", "init"], cwd=temp_src_dir, capture_output=True, text=True, check=True),
            call(
                ["git", "config", "user.name", "SoloPilot Bot"],
                cwd=temp_src_dir,
                capture_output=True,
                text=True,
                check=True,
            ),
            call(
                ["git", "config", "user.email", "bot@solopilot.dev"],
                cwd=temp_src_dir,
                capture_output=True,
                text=True,
                check=True,
            ),
            call(["git", "add", "."], cwd=temp_src_dir, capture_output=True, text=True, check=True),
            call(
                ["git", "status", "--porcelain"],
                cwd=temp_src_dir,
                capture_output=True,
                text=True,
                check=True,
            ),
            call(
                [
                    "git",
                    "commit",
                    "-m",
                    f"Add SoloPilot artifacts from {timestamp}\n\nGenerated by SoloPilot dev agent\nTimestamp: {timestamp}",
                ],
                cwd=temp_src_dir,
                capture_output=True,
                text=True,
                check=True,
            ),
            call(
                ["git", "checkout", "-b", f"artifact/{timestamp}"],
                cwd=temp_src_dir,
                capture_output=True,
                text=True,
                check=True,
            ),
            call(
                ["git", "remote", "add", "origin", git_url],
                cwd=temp_src_dir,
                capture_output=True,
                text=True,
                check=True,
            ),
            call(
                ["git", "push", "-u", "origin", f"artifact/{timestamp}"],
                cwd=temp_src_dir,
                capture_output=True,
                text=True,
                check=True,
            ),
            call(
                ["git", "rev-parse", "HEAD"],
                cwd=temp_src_dir,
                capture_output=True,
                text=True,
                check=True,
            ),
        ]

        mock_run.assert_has_calls(expected_calls, any_order=False)

    @patch("subprocess.run")
    def test_setup_git_repo_no_changes(self, mock_run, temp_src_dir):
        """Test git setup when there are no changes to commit."""

        def mock_command(cmd, **kwargs):
            if cmd == ["git", "status", "--porcelain"]:
                return MagicMock(returncode=0, stdout="", stderr="")
            return MagicMock(returncode=0, stdout="abc123", stderr="")

        mock_run.side_effect = mock_command

        git_url = "https://github.com/user/test-repo.git"
        timestamp = "20250611_123456"

        with pytest.raises(RuntimeError, match="No changes to commit"):
            setup_git_repo(temp_src_dir, git_url, timestamp)

    @patch("subprocess.run")
    def test_setup_git_repo_push_auth_failure(self, mock_run, temp_src_dir):
        """Test git setup when push fails due to authentication."""

        def mock_command(cmd, **kwargs):
            if cmd[0:2] == ["git", "push"]:
                raise subprocess.CalledProcessError(1, cmd, stderr="Permission denied (publickey)")
            elif cmd == ["git", "status", "--porcelain"]:
                return MagicMock(returncode=0, stdout="M file.txt", stderr="")
            return MagicMock(returncode=0, stdout="abc123", stderr="")

        mock_run.side_effect = mock_command

        git_url = "git@github.com:user/test-repo.git"
        timestamp = "20250611_123456"

        with pytest.raises(RuntimeError, match="authentication"):
            setup_git_repo(temp_src_dir, git_url, timestamp)

    @patch("subprocess.run")
    def test_setup_git_repo_repo_not_found(self, mock_run, temp_src_dir):
        """Test git setup when repository is not found."""

        def mock_command(cmd, **kwargs):
            if cmd[0:2] == ["git", "push"]:
                raise subprocess.CalledProcessError(1, cmd, stderr="Repository not found")
            elif cmd == ["git", "status", "--porcelain"]:
                return MagicMock(returncode=0, stdout="M file.txt", stderr="")
            return MagicMock(returncode=0, stdout="abc123", stderr="")

        mock_run.side_effect = mock_command

        git_url = "https://github.com/user/nonexistent-repo.git"
        timestamp = "20250611_123456"

        with pytest.raises(RuntimeError, match="Git repository not found"):
            setup_git_repo(temp_src_dir, git_url, timestamp)

    def test_setup_git_repo_nonexistent_source(self):
        """Test git setup with non-existent source directory."""
        nonexistent_path = Path("/nonexistent/path")
        git_url = "https://github.com/user/test-repo.git"
        timestamp = "20250611_123456"

        with pytest.raises(FileNotFoundError, match="Source path does not exist"):
            setup_git_repo(nonexistent_path, git_url, timestamp)

    def test_setup_git_repo_invalid_url(self, temp_src_dir):
        """Test git setup with invalid git URL."""
        invalid_url = "not-a-git-url"
        timestamp = "20250611_123456"

        with pytest.raises(ValueError, match="Invalid git URL format"):
            setup_git_repo(temp_src_dir, invalid_url, timestamp)

    @patch("subprocess.run")
    def test_setup_git_repo_gitlab_url(self, mock_run, temp_src_dir):
        """Test git setup with GitLab URL generates correct branch URL."""
        mock_run.return_value = MagicMock(returncode=0, stdout="abc1234567890", stderr="")

        git_url = "https://gitlab.com/user/test-repo.git"
        timestamp = "20250611_123456"

        result = setup_git_repo(temp_src_dir, git_url, timestamp)

        expected_branch_url = f"https://gitlab.com/user/test-repo/-/tree/artifact/{timestamp}"
        assert result["branch_url"] == expected_branch_url

    @patch("subprocess.run")
    def test_setup_git_repo_custom_git_config(self, mock_run, temp_src_dir):
        """Test git setup with custom git configuration from environment."""
        mock_run.return_value = MagicMock(returncode=0, stdout="abc123", stderr="")

        with patch.dict(
            "os.environ", {"GIT_USER_NAME": "Custom User", "GIT_USER_EMAIL": "custom@example.com"}
        ):
            git_url = "https://github.com/user/test-repo.git"
            timestamp = "20250611_123456"

            setup_git_repo(temp_src_dir, git_url, timestamp)

            # Check that custom git config was used
            config_calls = [
                call(
                    ["git", "config", "user.name", "Custom User"],
                    cwd=temp_src_dir,
                    capture_output=True,
                    text=True,
                    check=True,
                ),
                call(
                    ["git", "config", "user.email", "custom@example.com"],
                    cwd=temp_src_dir,
                    capture_output=True,
                    text=True,
                    check=True,
                ),
            ]

            for expected_call in config_calls:
                assert expected_call in mock_run.call_args_list

    @patch("scripts.push_artifacts.setup_git_repo")
    @patch("sys.argv")
    def test_main_success(self, mock_argv, mock_setup_git):
        """Test main function with successful execution."""
        mock_argv.__getitem__.side_effect = lambda i: [
            "push_artifacts.py",
            "--src",
            "output/dev/20250611_123456",
            "--remote",
            "https://github.com/user/repo.git",
        ][i]
        mock_argv.__len__.return_value = 5

        mock_setup_git.return_value = {
            "branch_name": "artifact/20250611_123456",
            "branch_url": "https://github.com/user/repo/tree/artifact/20250611_123456",
            "commit_hash": "abc123",
            "remote_url": "https://github.com/user/repo.git",
            "timestamp": "20250611_123456",
            "status": "pushed",
        }

        with patch("tempfile.mkdtemp") as mock_mkdtemp:
            # Create a real temporary directory for the test
            temp_dir = tempfile.mkdtemp()
            mock_mkdtemp.return_value = temp_dir

            try:
                # Create the expected source directory structure
                src_path = Path(temp_dir) / "output" / "dev" / "20250611_123456"
                src_path.mkdir(parents=True)
                (src_path / "test_file.txt").write_text("test content")

                with patch(
                    "sys.argv",
                    [
                        "push_artifacts.py",
                        "--src",
                        str(src_path),
                        "--remote",
                        "https://github.com/user/repo.git",
                    ],
                ):
                    with patch("builtins.print") as mock_print:
                        # Import main here to avoid import-time issues
                        from scripts.push_artifacts import main

                        main()

                        # Check that JSON was printed
                        printed_args = [call[0][0] for call in mock_print.call_args_list if call[0]]
                        json_outputs = [arg for arg in printed_args if arg.startswith("{")]
                        assert len(json_outputs) > 0

                        # Verify JSON structure
                        result = json.loads(json_outputs[0])
                        assert result["status"] == "pushed"
                        assert result["branch_name"] == "artifact/20250611_123456"

            finally:
                shutil.rmtree(temp_dir)

    @patch("sys.argv")
    def test_main_dry_run(self, mock_argv):
        """Test main function in dry run mode."""
        with patch(
            "sys.argv",
            [
                "push_artifacts.py",
                "--src",
                "output/dev/20250611_123456",
                "--remote",
                "https://github.com/user/repo.git",
                "--dry-run",
            ],
        ):
            with patch("builtins.print") as mock_print:
                # Create a temporary directory for the test
                with tempfile.TemporaryDirectory() as temp_dir:
                    src_path = Path(temp_dir) / "20250611_123456"
                    src_path.mkdir()
                    (src_path / "test.txt").write_text("test")

                    with patch(
                        "sys.argv",
                        [
                            "push_artifacts.py",
                            "--src",
                            str(src_path),
                            "--remote",
                            "https://github.com/user/repo.git",
                            "--dry-run",
                        ],
                    ):
                        from scripts.push_artifacts import main

                        main()

                        # Check that dry run output was printed
                        printed_args = [
                            str(call[0][0]) for call in mock_print.call_args_list if call[0]
                        ]
                        assert any("DRY RUN MODE" in arg for arg in printed_args)

                        # Check that JSON was still output
                        json_outputs = [arg for arg in printed_args if arg.startswith("{")]
                        assert len(json_outputs) > 0

                        result = json.loads(json_outputs[0])
                        assert result["status"] == "dry-run"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
