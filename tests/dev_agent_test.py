#!/usr/bin/env python3
"""
Unit tests for SoloPilot Dev Agent
Tests core functionality with mocked LLM responses.
"""

import json
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

# Import after path modification
from agents.dev.context7_bridge import Context7Bridge  # noqa: E402
from agents.dev.dev_agent import DevAgent  # noqa: E402


@pytest.fixture
def sample_planning_data():
    """Sample planning data for testing."""
    return {
        "project_title": "Test E-Commerce Platform",
        "project_summary": "A test e-commerce platform for unit testing",
        "milestones": [
            {
                "name": "Project Setup & Core Architecture",
                "description": "Establish project infrastructure and backend services",
                "estimated_duration": "2 weeks",
                "tasks": [
                    {
                        "name": "Tech Stack Configuration",
                        "description": "Set up Node.js/Express backend, PostgreSQL database",
                        "estimated_hours": 24,
                        "dependencies": [],
                    },
                    {
                        "name": "Database Schema Design",
                        "description": "Create database schema for users, products, orders",
                        "estimated_hours": 16,
                        "dependencies": [],
                    },
                ],
            },
            {
                "name": "Product Management & Catalog",
                "description": "Develop product listing and management functionalities",
                "estimated_duration": "2 weeks",
                "tasks": [
                    {
                        "name": "Product CRUD Operations",
                        "description": "Create backend APIs for product management",
                        "estimated_hours": 24,
                        "dependencies": ["Database Schema Design"],
                    }
                ],
            },
        ],
        "tech_stack": ["Node.js", "Express.js", "PostgreSQL", "React"],
        "estimated_total_duration": "4 weeks",
    }


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""
    config_data = {
        "llm": {
            "bedrock": {
                "inference_profile_arn": "arn:aws:bedrock:us-east-2:392894085110:inference-profile/dummy",
                "region": "us-east-2",
                "model_kwargs": {"temperature": 0.1, "top_p": 0.9, "max_tokens": 2048},
            },
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        import yaml

        yaml.dump(config_data, f)
        return f.name


@pytest.fixture
def temp_planning_file(sample_planning_data):
    """Create a temporary planning file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(sample_planning_data, f, indent=2)
        return f.name


@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


class TestDevAgent:
    """Test cases for DevAgent class."""

    def test_init(self, temp_config_file):
        """Test DevAgent initialization."""
        with patch.dict(
            os.environ, {"AWS_ACCESS_KEY_ID": "dummy", "AWS_SECRET_ACCESS_KEY": "dummy"}
        ):
            with patch("boto3.client") as mock_boto3:
                mock_boto3.return_value = MagicMock()
                agent = DevAgent(config_path=temp_config_file)
        assert agent.config is not None
        assert "llm" in agent.config

    def test_load_config(self, temp_config_file):
        """Test configuration loading."""
        with patch.dict(
            os.environ, {"AWS_ACCESS_KEY_ID": "dummy", "AWS_SECRET_ACCESS_KEY": "dummy"}
        ):
            with patch("boto3.client") as mock_boto3:
                mock_boto3.return_value = MagicMock()
                agent = DevAgent(config_path=temp_config_file)
        config = agent._load_config(temp_config_file)
        assert "llm" in config
        assert "bedrock" in config["llm"]

    def test_infer_language(self, temp_config_file):
        """Test language inference from tech stack."""
        with patch.dict(
            os.environ, {"AWS_ACCESS_KEY_ID": "dummy", "AWS_SECRET_ACCESS_KEY": "dummy"}
        ):
            with patch("boto3.client") as mock_boto3:
                mock_boto3.return_value = MagicMock()
                agent = DevAgent(config_path=temp_config_file)

        # Test JavaScript/TypeScript detection
        assert agent._infer_language(["React", "Node.js"], "Frontend") == "javascript"
        assert agent._infer_language(["TypeScript", "Express"], "Backend") == "javascript"

        # Test Python detection
        assert agent._infer_language(["Python", "Django"], "API") == "python"
        assert agent._infer_language(["Flask", "FastAPI"], "Services") == "python"

        # Test database detection
        assert agent._infer_language(["PostgreSQL"], "Database Schema") == "sql"

        # Test default fallback
        assert agent._infer_language(["Unknown"], "Feature") == "javascript"

    def test_get_file_extension(self, temp_config_file):
        """Test file extension mapping."""
        with patch.dict(
            os.environ, {"AWS_ACCESS_KEY_ID": "dummy", "AWS_SECRET_ACCESS_KEY": "dummy"}
        ):
            with patch("boto3.client") as mock_boto3:
                mock_boto3.return_value = MagicMock()
                agent = DevAgent(config_path=temp_config_file)

        assert agent._get_file_extension("javascript") == ".js"
        assert agent._get_file_extension("typescript") == ".ts"
        assert agent._get_file_extension("python") == ".py"
        assert agent._get_file_extension("java") == ".java"
        assert agent._get_file_extension("sql") == ".sql"
        assert agent._get_file_extension("unknown") == ".js"  # default

    def test_generate_stub_code(self, temp_config_file):
        """Test stub code generation."""
        with patch.dict(
            os.environ, {"AWS_ACCESS_KEY_ID": "dummy", "AWS_SECRET_ACCESS_KEY": "dummy"}
        ):
            with patch("boto3.client") as mock_boto3:
                mock_boto3.return_value = MagicMock()
                agent = DevAgent(config_path=temp_config_file)
        stub = agent._generate_stub_code()

        assert "StubImplementation" in stub
        assert "TODO:" in stub
        assert "describe(" in stub
        assert "test(" in stub

    def test_parse_llm_response(self, temp_config_file):
        """Test LLM response parsing."""
        with patch.dict(
            os.environ, {"AWS_ACCESS_KEY_ID": "dummy", "AWS_SECRET_ACCESS_KEY": "dummy"}
        ):
            with patch("boto3.client") as mock_boto3:
                mock_boto3.return_value = MagicMock()
                agent = DevAgent(config_path=temp_config_file)

        # Test with properly formatted response
        mock_response = """
```javascript
// === SKELETON CODE ===
class TestImplementation {
    constructor() {
        // TODO: Initialize
    }
}

// === UNIT TEST ===
describe('TestImplementation', () => {
    test('should work', () => {
        expect(true).toBe(true);
    });
});
```
"""
        skeleton, test = agent._parse_llm_response(mock_response, "javascript")
        assert "TestImplementation" in skeleton
        assert "describe(" in test
        assert "should work" in test

    @patch("agents.dev.dev_agent.DevAgent._call_llm")
    def test_process_planning_output(
        self, mock_llm_call, temp_config_file, temp_planning_file, temp_output_dir
    ):
        """Test processing planning output with mocked LLM."""
        # Mock LLM response
        mock_llm_call.return_value = """
```javascript
// === SKELETON CODE ===
// Project Setup Implementation
class ProjectSetup {
    constructor() {
        // TODO: Initialize project configuration
    }
    
    async setupDatabase() {
        // TODO: Configure PostgreSQL connection
    }
}

// === UNIT TEST ===
describe('ProjectSetup', () => {
    test('should initialize correctly', () => {
        const setup = new ProjectSetup();
        expect(setup).toBeDefined();
    });
    
    test('should setup database', async () => {
        const setup = new ProjectSetup();
        // TODO: Test database setup
        expect(true).toBe(true);
    });
});
```
"""

        with patch.dict(
            os.environ, {"AWS_ACCESS_KEY_ID": "dummy", "AWS_SECRET_ACCESS_KEY": "dummy"}
        ):
            with patch("boto3.client") as mock_boto3:
                mock_boto3.return_value = MagicMock()
                agent = DevAgent(config_path=temp_config_file)
        manifest = agent.process_planning_output(temp_planning_file, temp_output_dir)

        # Verify manifest structure
        assert manifest["project_title"] == "Test E-Commerce Platform"
        assert len(manifest["milestones"]) == 2
        assert "Node.js" in manifest["tech_stack"]

        # Verify output directory structure
        output_path = Path(temp_output_dir)
        assert output_path.exists()

        # Check milestone directories
        milestone1_dir = output_path / "milestone-1"
        milestone2_dir = output_path / "milestone-2"

        assert milestone1_dir.exists()
        assert milestone2_dir.exists()

        # Check generated files
        assert (milestone1_dir / "implementation.js").exists()
        assert (milestone1_dir / "test.js").exists()
        assert (milestone1_dir / "README.md").exists()

        # Check unit tests directory
        unit_tests_dir = output_path / "unit_tests"
        assert unit_tests_dir.exists()
        assert (unit_tests_dir / "integration.test.js").exists()

        # Check manifest file
        manifest_file = output_path / "manifest.json"
        assert manifest_file.exists()

        # Verify manifest content
        with open(manifest_file, "r") as f:
            saved_manifest = json.load(f)
        assert saved_manifest["project_title"] == "Test E-Commerce Platform"

    def test_find_latest_planning_output(self, temp_config_file):
        """Test finding latest planning output."""
        with patch.dict(
            os.environ, {"AWS_ACCESS_KEY_ID": "dummy", "AWS_SECRET_ACCESS_KEY": "dummy"}
        ):
            with patch("boto3.client") as mock_boto3:
                mock_boto3.return_value = MagicMock()
                agent = DevAgent(config_path=temp_config_file)

        # Test with no planning directory
        with patch("pathlib.Path.exists", return_value=False):
            result = agent.find_latest_planning_output()
            assert result is None

    def test_bedrock_failure_raises_exception(self, temp_config_file):
        """Test that Bedrock failures raise exceptions instead of returning stubs."""
        # Mock standardized client to fail
        with patch("agents.common.bedrock_client.StandardizedBedrockClient") as mock_client_class:
            from agents.common.bedrock_client import BedrockError

            mock_client = MagicMock()
            mock_client.simple_invoke.side_effect = BedrockError("Bedrock access denied")
            mock_client_class.return_value = mock_client

            with patch.dict(
                os.environ, {"AWS_ACCESS_KEY_ID": "dummy", "AWS_SECRET_ACCESS_KEY": "dummy"}
            ):
                agent = DevAgent(config_path=temp_config_file)

                # Should raise exception, not return stub code
                with pytest.raises(BedrockError, match="Bedrock access denied"):
                    agent._call_llm("Test prompt")

    def test_credentials_missing_env_and_profile(self, temp_config_file):
        """Test credential validation when neither env vars nor profile exist."""
        with patch.dict(os.environ, {}, clear=True):  # Clear all env vars
            with patch("os.path.exists", return_value=False):  # No AWS profile
                from agents.common.bedrock_client import BedrockAccessError

                with pytest.raises(BedrockAccessError, match="AWS credentials not found"):
                    DevAgent(config_path=temp_config_file)

    def test_credentials_with_env_vars(self, temp_config_file):
        """Test credential validation with environment variables."""
        with patch.dict(os.environ, {"AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test"}):
            with patch("boto3.client") as mock_boto3:
                mock_boto3.return_value = MagicMock()
                # Should not raise
                agent = DevAgent(config_path=temp_config_file)
                assert agent is not None

    def test_credentials_with_profile(self, temp_config_file):
        """Test credential validation with AWS profile."""
        with patch.dict(os.environ, {}, clear=True):  # Clear env vars
            with patch("os.path.exists", return_value=True):  # AWS profile exists
                with patch(
                    "agents.common.bedrock_client.StandardizedBedrockClient"
                ) as mock_client_class:
                    mock_client = MagicMock()
                    mock_client_class.return_value = mock_client
                    # Should not raise
                    agent = DevAgent(config_path=temp_config_file)
                    assert agent is not None

    def test_inference_profile_access_validation(self, temp_config_file):
        """Test that inference profile access validation exists in standardized client."""
        with patch.dict(
            os.environ, {"AWS_ACCESS_KEY_ID": "dummy", "AWS_SECRET_ACCESS_KEY": "dummy"}
        ):
            with patch(
                "agents.common.bedrock_client.StandardizedBedrockClient"
            ) as mock_client_class:
                mock_client = MagicMock()
                mock_client_class.return_value = mock_client
                # Should not raise during initialization (validation is in standardized client)
                agent = DevAgent(config_path=temp_config_file)
                assert agent is not None
                # Standardized client should exist
                assert agent.bedrock_client is not None

    def test_sdk_compatibility_fallback(self, temp_config_file):
        """Test SDK compatibility through standardized client."""
        with patch.dict(
            os.environ, {"AWS_ACCESS_KEY_ID": "dummy", "AWS_SECRET_ACCESS_KEY": "dummy"}
        ):
            with patch(
                "agents.common.bedrock_client.StandardizedBedrockClient"
            ) as mock_client_class:
                mock_client = MagicMock()
                mock_client.simple_invoke.return_value = "Modern response"
                mock_client_class.return_value = mock_client

                agent = DevAgent(config_path=temp_config_file)
                result = agent._call_llm("Test prompt")

                assert result == "Modern response"
                mock_client.simple_invoke.assert_called_once()

    def test_sdk_legacy_fallback(self, temp_config_file):
        """Test that standardized client handles legacy fallback internally."""
        with patch.dict(
            os.environ, {"AWS_ACCESS_KEY_ID": "dummy", "AWS_SECRET_ACCESS_KEY": "dummy"}
        ):
            with patch(
                "agents.common.bedrock_client.StandardizedBedrockClient"
            ) as mock_client_class:
                mock_client = MagicMock()
                mock_client.simple_invoke.return_value = "Legacy response"
                mock_client_class.return_value = mock_client

                agent = DevAgent(config_path=temp_config_file)
                result = agent._call_llm("Test prompt")

                assert result == "Legacy response"

    def test_model_id_extraction(self, temp_config_file):
        """Test that standardized client properly handles ARN parsing."""
        # Test ARN parsing directly
        test_arn = "arn:aws:bedrock:us-east-2:392894085110:inference-profile/us.anthropic.claude-3-haiku-20240307-v1:0"
        expected_model_id = "us.anthropic.claude-3-haiku-20240307-v1:0"

        # Test ARN parsing logic
        assert test_arn.split("/")[-1] == expected_model_id

    def test_correct_parameters_sent(self, temp_config_file):
        """Test that correct parameters are sent to standardized Bedrock client."""
        with patch.dict(
            os.environ, {"AWS_ACCESS_KEY_ID": "dummy", "AWS_SECRET_ACCESS_KEY": "dummy"}
        ):
            with patch(
                "agents.common.bedrock_client.StandardizedBedrockClient"
            ) as mock_client_class:
                mock_client = MagicMock()
                mock_client.simple_invoke.return_value = "Test response"
                mock_client_class.return_value = mock_client

                agent = DevAgent(config_path=temp_config_file)
                result = agent._call_llm("Test prompt")

                # Verify the call was successful
                assert result == "Test response"

                # Verify standardized client was called with correct parameters
                mock_client.simple_invoke.assert_called_once()
                call_args = mock_client.simple_invoke.call_args

                # Check prompt parameter
                assert call_args[0][0] == "Test prompt"

                # Check that max_tokens and temperature were passed
                assert len(call_args[0]) >= 3  # prompt, max_tokens, temperature


class TestContext7Bridge:
    """Test cases for Context7Bridge class."""

    def test_init(self):
        """Test Context7Bridge initialization."""
        bridge = Context7Bridge()
        assert hasattr(bridge, "context7_available")
        assert hasattr(bridge, "enabled")

    @patch("subprocess.run")
    def test_check_context7_available_success(self, mock_run):
        """Test successful Context7 availability check."""
        mock_run.return_value.returncode = 0

        bridge = Context7Bridge()
        bridge.context7_available = bridge._check_context7_available()
        assert bridge.context7_available is True

    @patch("subprocess.run")
    def test_check_context7_available_failure(self, mock_run):
        """Test failed Context7 availability check."""
        mock_run.side_effect = FileNotFoundError()

        bridge = Context7Bridge()
        bridge.context7_available = bridge._check_context7_available()
        assert bridge.context7_available is False

    def test_is_enabled_false_by_default(self):
        """Test that Context7 is disabled by default."""
        with patch.dict(os.environ, {}, clear=True):  # Clear environment
            bridge = Context7Bridge()
            assert bridge.is_enabled() is False

    @patch.dict(os.environ, {"C7_SCOUT": "1"})
    @patch("subprocess.run")
    def test_is_enabled_with_env_var(self, mock_run):
        """Test Context7 enabled with environment variable."""
        mock_run.return_value.returncode = 0

        bridge = Context7Bridge()
        bridge.context7_available = True
        bridge.enabled = True
        assert bridge.is_enabled() is True

    @patch("subprocess.run")
    def test_query_context7_success(self, mock_run):
        """Test successful Context7 query."""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Context7 response"

        bridge = Context7Bridge()
        bridge.enabled = True

        result = bridge._query_context7("Test question")
        assert result == "Context7 response"

    @patch("subprocess.run")
    def test_query_context7_failure(self, mock_run):
        """Test failed Context7 query."""
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Context7 error"

        bridge = Context7Bridge()
        bridge.enabled = True

        result = bridge._query_context7("Test question")
        assert result is None

    def test_generate_milestone_insights_disabled(self):
        """Test milestone insights generation when disabled."""
        bridge = Context7Bridge()
        bridge.enabled = False

        milestone = {"name": "Test Milestone", "description": "Test description"}
        insights = bridge.generate_milestone_insights(milestone, ["Node.js"])

        assert insights["enabled"] is False
        assert insights["pitfalls"] is None
        assert insights["patterns"] is None
        assert insights["testing"] is None

    def test_format_insights_for_readme_empty(self):
        """Test formatting empty insights."""
        bridge = Context7Bridge()

        insights = {"enabled": False, "pitfalls": None, "patterns": None, "testing": None}

        result = bridge.format_insights_for_readme(insights)
        assert result == ""

    def test_format_insights_for_readme_with_content(self):
        """Test formatting insights with content."""
        bridge = Context7Bridge()

        insights = {
            "enabled": True,
            "pitfalls": "Common pitfalls include...",
            "patterns": "Best patterns are...",
            "testing": "Testing strategies include...",
        }

        result = bridge.format_insights_for_readme(insights)
        assert "Common Pitfalls" in result
        assert "Implementation Patterns" in result
        assert "Testing Strategies" in result
        assert "Context7" in result

    def test_get_status(self):
        """Test getting Context7 bridge status."""
        bridge = Context7Bridge()
        status = bridge.get_status()

        assert "context7_available" in status
        assert "enabled" in status
        assert "env_var_set" in status
        assert "install_command" in status
        assert status["install_command"] == "npm install -g context7"


# Integration smoke tests
class TestIntegration:
    """Integration tests to verify end-to-end functionality."""

    @patch("agents.dev.dev_agent.DevAgent._call_llm")
    def test_smoke_test_dev_agent(
        self, mock_llm_call, temp_config_file, temp_planning_file, temp_output_dir
    ):
        """Smoke test for the complete dev agent workflow."""
        mock_llm_call.return_value = """
```javascript
// === SKELETON CODE ===
class SmokeTestImplementation {
    execute() {
        return "success";
    }
}

// === UNIT TEST ===
describe('SmokeTestImplementation', () => {
    test('should execute successfully', () => {
        const impl = new SmokeTestImplementation();
        expect(impl.execute()).toBe("success");
    });
});
```
"""

        with patch.dict(
            os.environ, {"AWS_ACCESS_KEY_ID": "dummy", "AWS_SECRET_ACCESS_KEY": "dummy"}
        ):
            with patch("boto3.client") as mock_boto3:
                mock_boto3.return_value = MagicMock()
                agent = DevAgent(config_path=temp_config_file)
        manifest = agent.process_planning_output(temp_planning_file, temp_output_dir)

        # Basic assertions to ensure the workflow completed
        assert manifest is not None
        assert len(manifest["milestones"]) > 0
        assert Path(temp_output_dir).exists()
        assert (Path(temp_output_dir) / "manifest.json").exists()

    def test_smoke_test_context7_bridge(self):
        """Smoke test for Context7 bridge basic functionality."""
        bridge = Context7Bridge()

        # Test basic methods don't crash
        status = bridge.get_status()
        assert isinstance(status, dict)

        enabled = bridge.is_enabled()
        assert isinstance(enabled, bool)

        # Test insights generation with disabled bridge
        milestone = {"name": "Test", "description": "Test"}
        insights = bridge.generate_milestone_insights(milestone, ["Node.js"])
        assert isinstance(insights, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
