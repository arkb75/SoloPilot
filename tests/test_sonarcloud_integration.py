#!/usr/bin/env python3
"""
Integration tests for SonarCloud auto-provisioning functionality.
Tests the enhanced retry logic, error handling, and zero-manual-intervention setup.
"""

import os

# Add project root to path
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.sonarcloud_integration import SonarCloudClient


class TestSonarCloudIntegration:
    """Test suite for SonarCloud integration functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.original_env = {}

        # Store original environment variables
        for key in ["SONAR_TOKEN", "SONAR_ORGANIZATION", "NO_NETWORK"]:
            self.original_env[key] = os.getenv(key)

        # Set up test environment
        os.environ["NO_NETWORK"] = "0"
        os.environ["SONAR_ORGANIZATION"] = "test-org"

    def teardown_method(self):
        """Clean up test environment."""
        # Restore original environment variables
        for key, value in self.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_git_url_parsing(self):
        """Test Git URL parsing with various formats."""
        test_cases = [
            # GitHub HTTPS
            (
                "https://github.com/owner/repo.git",
                {"owner": "owner", "repo": "repo", "project_key": "owner_repo"},
            ),
            (
                "https://github.com/owner/repo",
                {"owner": "owner", "repo": "repo", "project_key": "owner_repo"},
            ),
            (
                "https://www.github.com/owner/repo/",
                {"owner": "owner", "repo": "repo", "project_key": "owner_repo"},
            ),
            # GitHub SSH
            (
                "git@github.com:owner/repo.git",
                {"owner": "owner", "repo": "repo", "project_key": "owner_repo"},
            ),
            (
                "git@github.com:owner/repo",
                {"owner": "owner", "repo": "repo", "project_key": "owner_repo"},
            ),
            # GitLab HTTPS
            (
                "https://gitlab.com/owner/repo.git",
                {"owner": "owner", "repo": "repo", "project_key": "owner_repo"},
            ),
            (
                "https://www.gitlab.com/owner/repo",
                {"owner": "owner", "repo": "repo", "project_key": "owner_repo"},
            ),
            # GitLab SSH
            (
                "git@gitlab.com:owner/repo.git",
                {"owner": "owner", "repo": "repo", "project_key": "owner_repo"},
            ),
            # Invalid formats
            ("invalid-url", None),
            ("", None),
            ("https://example.com/repo", None),
            ("ftp://github.com/owner/repo", None),
        ]

        for git_url, expected in test_cases:
            result = SonarCloudClient.parse_git_url(git_url)
            if expected is None:
                assert result is None, f"Expected None for {git_url}, got {result}"
            else:
                assert result == expected, f"Expected {expected} for {git_url}, got {result}"

    def test_configuration_validation_no_token(self):
        """Test configuration validation without token."""
        # Remove token
        os.environ.pop("SONAR_TOKEN", None)

        client = SonarCloudClient()
        validation = client.validate_configuration()

        assert not validation["valid"]
        assert not validation["token_valid"]
        assert not validation["organization_exists"]
        assert "SONAR_TOKEN environment variable not set" in validation["issues"]

    def test_configuration_validation_offline_mode(self):
        """Test configuration validation in offline mode."""
        os.environ["NO_NETWORK"] = "1"
        os.environ["SONAR_TOKEN"] = "fake-token"

        client = SonarCloudClient()
        validation = client.validate_configuration()

        assert not validation["valid"]
        assert not validation["token_valid"]
        assert not validation["organization_exists"]
        assert "NO_NETWORK=1 - SonarCloud integration disabled" in validation["issues"]

    @patch("src.utils.sonarcloud_integration.requests.Session")
    def test_configuration_validation_success(self, mock_session_class):
        """Test successful configuration validation."""
        # Set up environment
        os.environ["SONAR_TOKEN"] = "valid-token"

        # Mock successful API response
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "organizations": [{"key": "test-org", "name": "Test Organization"}]
        }
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = SonarCloudClient()
        validation = client.validate_configuration()

        assert validation["valid"]
        assert validation["token_valid"]
        assert validation["organization_exists"]
        assert len(validation["issues"]) == 0

    @patch("src.utils.sonarcloud_integration.requests.Session")
    def test_configuration_validation_invalid_org(self, mock_session_class):
        """Test configuration validation with invalid organization."""
        # Set up environment
        os.environ["SONAR_TOKEN"] = "valid-token"

        # Mock API response without the target organization
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "organizations": [{"key": "other-org", "name": "Other Organization"}]
        }
        mock_session.get.return_value = mock_response
        mock_session_class.return_value = mock_session

        client = SonarCloudClient()
        validation = client.validate_configuration()

        assert not validation["valid"]
        assert validation["token_valid"]
        assert not validation["organization_exists"]
        assert "Organization 'test-org' not found or no access" in validation["issues"]

    @patch("src.utils.sonarcloud_integration.requests.Session")
    def test_project_creation_success(self, mock_session_class):
        """Test successful project creation."""
        # Set up environment
        os.environ["SONAR_TOKEN"] = "valid-token"

        # Mock session and responses
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock validation response (successful)
        validation_response = Mock()
        validation_response.status_code = 200
        validation_response.json.return_value = {
            "organizations": [{"key": "test-org", "name": "Test Organization"}]
        }

        # Mock project existence check (project doesn't exist)
        existence_response = Mock()
        existence_response.status_code = 200
        existence_response.json.return_value = {"components": []}

        # Mock project creation response (successful)
        creation_response = Mock()
        creation_response.status_code = 200
        creation_response.json.return_value = {
            "project": {
                "key": "test-org_test-project",
                "name": "Test Project",
                "visibility": "private",
            }
        }

        # Mock verification response (project exists after creation)
        verification_response = Mock()
        verification_response.status_code = 200
        verification_response.json.return_value = {
            "components": [{"key": "test-org_test-project", "name": "Test Project"}]
        }

        # Set up session mock to return appropriate responses
        mock_session.get.side_effect = [
            validation_response,  # For validate_configuration
            existence_response,  # For _check_project_exists (before creation)
            verification_response,  # For _verify_project_creation
        ]
        mock_session.post.return_value = creation_response

        client = SonarCloudClient()
        result = client.create_project("Test Project")

        assert result is not None
        assert result["project_key"] == "test-org_test-project"
        assert result["project_name"] == "Test Project"
        assert result["organization"] == "test-org"
        assert result["visibility"] == "private"
        assert "url" in result
        assert result.get("existed") is not True

    @patch("src.utils.sonarcloud_integration.requests.Session")
    def test_project_creation_already_exists(self, mock_session_class):
        """Test project creation when project already exists."""
        # Set up environment
        os.environ["SONAR_TOKEN"] = "valid-token"

        # Mock session and responses
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock validation response (successful)
        validation_response = Mock()
        validation_response.status_code = 200
        validation_response.json.return_value = {
            "organizations": [{"key": "test-org", "name": "Test Organization"}]
        }

        # Mock project existence check (project already exists)
        existence_response = Mock()
        existence_response.status_code = 200
        existence_response.json.return_value = {
            "components": [{"key": "test-org_existing-project", "name": "Existing Project"}]
        }

        mock_session.get.side_effect = [
            validation_response,  # For validate_configuration
            existence_response,  # For _check_project_exists
        ]

        client = SonarCloudClient()
        result = client.create_project("Existing Project", "test-org_existing-project")

        assert result is not None
        assert result["project_key"] == "test-org_existing-project"
        assert result["existed"] is True

    @patch("src.utils.sonarcloud_integration.requests.Session")
    def test_project_creation_retry_logic(self, mock_session_class):
        """Test retry logic for project creation."""
        # Set up environment
        os.environ["SONAR_TOKEN"] = "valid-token"

        # Mock session and responses
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock validation response (successful)
        validation_response = Mock()
        validation_response.status_code = 200
        validation_response.json.return_value = {
            "organizations": [{"key": "test-org", "name": "Test Organization"}]
        }

        # Mock project existence check (project doesn't exist)
        existence_response = Mock()
        existence_response.status_code = 200
        existence_response.json.return_value = {"components": []}

        # Mock verification response (project exists after creation)
        verification_response = Mock()
        verification_response.status_code = 200
        verification_response.json.return_value = {
            "components": [{"key": "test-org_retry-project", "name": "Retry Project"}]
        }

        mock_session.get.side_effect = [
            validation_response,  # For validate_configuration
            existence_response,  # For _check_project_exists
            verification_response,  # For _verify_project_creation
        ]

        # Mock POST to fail twice, then succeed
        import requests

        failed_response = Mock()
        failed_response.side_effect = requests.RequestException("Connection failed")

        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "project": {
                "key": "test-org_retry-project",
                "name": "Retry Project",
                "visibility": "private",
            }
        }

        mock_session.post.side_effect = [
            requests.RequestException("Connection failed"),  # First attempt fails
            requests.RequestException("Timeout"),  # Second attempt fails
            success_response,  # Third attempt succeeds
        ]

        client = SonarCloudClient()

        # This should succeed despite the first two failures
        with patch("time.sleep"):  # Speed up test by mocking sleep
            result = client.create_project("Retry Project")

        assert result is not None
        assert result["project_key"] == "test-org_retry-project"

        # Verify that POST was called 3 times (2 failures + 1 success)
        assert mock_session.post.call_count == 3

    @patch("src.utils.sonarcloud_integration.requests.Session")
    def test_setup_project_from_git_url_success(self, mock_session_class):
        """Test complete project setup from Git URL."""
        # Set up environment
        os.environ["SONAR_TOKEN"] = "valid-token"

        # Mock session and responses
        mock_session = Mock()
        mock_session_class.return_value = mock_session

        # Mock all required API responses
        validation_response = Mock()
        validation_response.status_code = 200
        validation_response.json.return_value = {
            "organizations": [{"key": "test-org", "name": "Test Organization"}]
        }

        existence_response = Mock()
        existence_response.status_code = 200
        existence_response.json.return_value = {"components": []}

        creation_response = Mock()
        creation_response.status_code = 200
        creation_response.json.return_value = {
            "project": {
                "key": "test-org_owner_repo",
                "name": "owner - repo",
                "visibility": "private",
            }
        }

        verification_response = Mock()
        verification_response.status_code = 200
        verification_response.json.return_value = {
            "components": [{"key": "test-org_owner_repo", "name": "owner - repo"}]
        }

        quality_gate_response = Mock()
        quality_gate_response.status_code = 204

        branch_config_response = Mock()
        branch_config_response.status_code = 404  # Expected for new projects

        mock_session.get.side_effect = [
            validation_response,  # For validate_configuration
            existence_response,  # For _check_project_exists
            verification_response,  # For _verify_project_creation
        ]
        mock_session.post.side_effect = [
            creation_response,  # For project creation
            quality_gate_response,  # For quality gate setup
            branch_config_response,  # For branch configuration
        ]

        client = SonarCloudClient()
        result = client.setup_project_from_git_url("https://github.com/owner/repo.git")

        assert result is not None
        assert result["project_key"] == "test-org_owner_repo"
        assert result["git_url"] == "https://github.com/owner/repo.git"
        assert result["git_owner"] == "owner"
        assert result["git_repo"] == "repo"
        assert "url" in result

    def test_offline_stub_functionality(self):
        """Test that offline mode provides proper stub responses."""
        # Set offline mode
        os.environ["NO_NETWORK"] = "1"
        os.environ["SONAR_TOKEN"] = "fake-token"

        client = SonarCloudClient()

        # Test that client reports as unavailable
        assert not client.is_available()

        # Test that methods return appropriate offline responses
        assert client.get_project_metrics() is None
        assert client.get_project_issues() == []
        assert client.get_quality_gate_status() is None

        # Test generate_review_summary returns offline status
        summary = client.generate_review_summary()
        assert not summary["available"]
        assert summary["reason"] == "offline_mode"

    def test_project_key_sanitization(self):
        """Test project key sanitization for SonarCloud requirements."""
        # Set up environment
        os.environ["SONAR_TOKEN"] = "valid-token"

        with patch("src.utils.sonarcloud_integration.requests.Session"):
            client = SonarCloudClient()

            # Mock validate_configuration to return valid
            with patch.object(client, "validate_configuration") as mock_validate:
                mock_validate.return_value = {"valid": True, "issues": []}

                # Mock _check_project_exists to return None (project doesn't exist)
                with patch.object(client, "_check_project_exists") as mock_check:
                    mock_check.return_value = None

                    # Test various project names and their sanitization
                    test_cases = [
                        ("Test Project!", "test-org_test_project"),
                        ("My@App#2023", "test-org_my_app_2023"),
                        ("Multi___Underscore", "test-org_multi_underscore"),
                        ("Special!@#$%Characters", "test-org_special_characters"),
                    ]

                    for project_name, expected_key in test_cases:
                        # Mock session.post to avoid actual API call
                        with patch.object(client.session, "post") as mock_post:
                            mock_response = Mock()
                            mock_response.status_code = 200
                            mock_response.json.return_value = {
                                "project": {"key": expected_key, "name": project_name}
                            }
                            mock_post.return_value = mock_response

                            # Mock verification
                            with patch.object(client, "_verify_project_creation") as mock_verify:
                                mock_verify.return_value = True

                                result = client.create_project(project_name)

                                # Verify the sanitized project key was used
                                assert result is not None
                                call_args = mock_post.call_args[1]["data"]
                                assert call_args["project"] == expected_key


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
