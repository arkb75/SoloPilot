"""Tests for Vercel project manager."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from scripts.vercel_project_manager import VercelProjectManager


class TestVercelProjectManager:
    """Test Vercel project management functionality."""

    @patch("scripts.vercel_project_manager.requests.post")
    def test_create_project_success(self, mock_post):
        """Test successful project creation."""
        # Mock API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "prj_abc123",
            "name": "client-smith-consulting-site-20250701",
            "accountId": "team_123",
            "framework": "nextjs",
            "createdAt": 1719849600000,
        }
        mock_post.return_value = mock_response

        # Create manager and project
        manager = VercelProjectManager("test-token")
        project_id, project_name = manager.create_project("Smith Consulting", "site", "nextjs")

        # Verify results
        assert project_id == "prj_abc123"
        assert project_name == "client-smith-consulting-site-20250701"

        # Verify API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://api.vercel.com/v10/projects"

        # Check request body
        request_data = call_args[1]["json"]
        assert request_data["name"] == project_name
        assert request_data["framework"] == "nextjs"
        assert request_data["publicSource"] is False

    def test_generate_project_name(self):
        """Test project name generation."""
        manager = VercelProjectManager("test-token")

        # Test basic sanitization
        name = manager._generate_project_name("Smith Consulting", "site")
        assert name.startswith("client-smith-consulting-site-")
        assert len(name) <= 100

        # Test special characters
        name = manager._generate_project_name("ABC & Co., Inc.", "app")
        assert "client-abc-co-inc-app-" in name
        assert "&" not in name
        assert "," not in name
        assert "." not in name

        # Test long names
        long_name = "A" * 100
        name = manager._generate_project_name(long_name, "api")
        assert len(name) <= 100
        assert name.startswith("client-")
        assert name.endswith(datetime.now().strftime("%Y%m%d"))

    @patch("scripts.vercel_project_manager.requests.get")
    def test_get_project_by_name(self, mock_get):
        """Test finding project by name."""
        # Mock list response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "projects": [
                {"id": "prj_123", "name": "client-abc-site-20250630"},
                {"id": "prj_456", "name": "client-smith-consulting-site-20250701"},
            ]
        }
        mock_get.return_value = mock_response

        manager = VercelProjectManager("test-token")
        project = manager._get_project_by_name("client-smith-consulting-site-20250701")

        assert project is not None
        assert project["id"] == "prj_456"
        assert project["name"] == "client-smith-consulting-site-20250701"

    @patch("scripts.vercel_project_manager.requests.post")
    @patch("scripts.vercel_project_manager.requests.get")
    def test_get_or_create_existing_project(self, mock_get, mock_post):
        """Test get_or_create when project exists."""
        # Mock existing project
        mock_get_response = MagicMock()
        mock_get_response.status_code = 200
        mock_get_response.json.return_value = {
            "projects": [{"id": "prj_existing", "name": "client-test-site-20250701"}]
        }
        mock_get.return_value = mock_get_response

        manager = VercelProjectManager("test-token")

        # Mock name generation to return consistent name
        with patch.object(
            manager, "_generate_project_name", return_value="client-test-site-20250701"
        ):
            project_id, project_name = manager.get_or_create_project("Test", "site")

        # Should return existing project
        assert project_id == "prj_existing"
        assert project_name == "client-test-site-20250701"

        # Should not create new project
        mock_post.assert_not_called()

    @patch("scripts.vercel_project_manager.requests.post")
    def test_update_environment_variables(self, mock_post):
        """Test updating project environment variables."""
        # Mock successful update
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_post.return_value = mock_response

        manager = VercelProjectManager("test-token")

        # Mock get_env_var_id to return None (new var)
        with patch.object(manager, "_get_env_var_id", return_value=None):
            success = manager.update_project_env_vars(
                "prj_123", {"API_KEY": "secret123", "DATABASE_URL": "postgres://..."}
            )

        assert success is True
        assert mock_post.call_count == 2  # One for each env var

    @patch("scripts.vercel_project_manager.requests.delete")
    def test_delete_project(self, mock_delete):
        """Test project deletion."""
        # Mock successful deletion
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_delete.return_value = mock_response

        manager = VercelProjectManager("test-token")
        success = manager.delete_project("prj_123")

        assert success is True
        mock_delete.assert_called_once_with(
            "https://api.vercel.com/v10/projects/prj_123",
            headers=manager.headers,
            params={},
        )

    def test_framework_configuration(self):
        """Test framework-specific configurations."""
        manager = VercelProjectManager("test-token")

        # Test Next.js
        assert manager._get_install_command("nextjs") == "npm install"
        assert manager._get_build_command("nextjs") == "npm run build"
        assert manager._get_output_directory("nextjs") == ".next"

        # Test Python
        assert manager._get_install_command("python") == "pip install -r requirements.txt"
        assert manager._get_build_command("python") == ""
        assert manager._get_output_directory("python") == "."

        # Test unknown framework
        assert manager._get_install_command("unknown") == "npm install"
        assert manager._get_build_command("unknown") == "npm run build"
        assert manager._get_output_directory("unknown") == "."

    def test_missing_token(self):
        """Test error when token is missing."""
        with patch.dict("os.environ", {"VERCEL_TOKEN": ""}):
            with pytest.raises(ValueError, match="Vercel API token is required"):
                VercelProjectManager()

    @patch("scripts.vercel_project_manager.requests.post")
    def test_create_project_api_error(self, mock_post):
        """Test handling API errors during project creation."""
        # Mock API error
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"error": {"message": "Invalid project name"}}'
        mock_post.return_value = mock_response

        manager = VercelProjectManager("test-token")

        with pytest.raises(Exception, match="Failed to create project"):
            manager.create_project("Invalid@Name", "site")
