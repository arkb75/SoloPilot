#!/usr/bin/env python3
"""
Tests for Serena LSP Context Engine

Tests the symbol-aware context management system for token optimization
and precise code understanding via Language Server Protocol integration.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.dev.context_engine.serena_engine import SerenaContextEngine


class TestSerenaContextEngine(unittest.TestCase):
    """Test cases for Serena LSP context engine."""

    def setUp(self):
        """Set up test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.milestone_dir = self.temp_dir / "milestone-001"
        self.milestone_dir.mkdir(parents=True)

        # Create a basic milestone.json
        milestone_data = {
            "name": "Test Milestone",
            "components": ["UserController", "AuthService"],
            "functions": ["authenticate", "validateToken"],
            "classes": ["User", "Token"],
        }

        with open(self.milestone_dir / "milestone.json", "w") as f:
            json.dump(milestone_data, f)

        # Create sample Python files
        (self.temp_dir / "auth.py").write_text(
            """
class UserController:
    def authenticate(self, username, password):
        return AuthService.validate(username, password)

class AuthService:
    @staticmethod
    def validate(username, password):
        return username == "admin" and password == "secret"
"""
        )

        (self.temp_dir / "models.py").write_text(
            """
class User:
    def __init__(self, username):
        self.username = username

class Token:
    def __init__(self, value):
        self.value = value
"""
        )

    def tearDown(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("agents.dev.context_engine.serena_engine.subprocess.run")
    def test_serena_unavailable_fallback(self, mock_run):
        """Test fallback to legacy engine when Serena is unavailable."""
        # Mock Serena as unavailable
        mock_run.return_value.returncode = 1

        with patch("agents.dev.context_engine.LegacyContextEngine") as mock_legacy:
            mock_legacy.return_value.build_context.return_value = (
                "legacy context",
                {"engine": "legacy"},
            )

            engine = SerenaContextEngine(project_root=self.temp_dir)
            context, metadata = engine.build_context(self.milestone_dir, "test prompt")

            # Should fallback to legacy engine with progressive context
            self.assertIn("Progressive Context", context)
            self.assertIn("fallback", metadata["engine"])

    @patch("agents.dev.context_engine.serena_engine.subprocess.run")
    def test_serena_available_basic_context(self, mock_run):
        """Test basic context building when Serena is available."""
        # Mock Serena as available
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "available"

        engine = SerenaContextEngine(project_root=self.temp_dir)
        context, metadata = engine.build_context(
            self.milestone_dir, "Implement authentication system"
        )

        # Verify context structure
        self.assertIn("SoloPilot Progressive Context", context)
        self.assertIn("milestone-001", context)
        self.assertIn("Implement authentication system", context)

        # Verify metadata
        self.assertEqual(metadata["engine"], "serena_lsp_progressive")
        self.assertEqual(metadata["milestone_path"], str(self.milestone_dir))
        self.assertIn("symbols_found", metadata)
        self.assertIn("tokens_estimated", metadata)
        self.assertIn("tokens_saved", metadata)

    @patch("agents.dev.context_engine.serena_engine.subprocess.run")
    def test_symbol_extraction_from_milestone(self, mock_run):
        """Test symbol extraction from milestone JSON."""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "available"

        engine = SerenaContextEngine(project_root=self.temp_dir)
        symbols = engine._extract_relevant_symbols(self.milestone_dir, "")

        # Should extract symbols from milestone.json
        expected_symbols = {
            "UserController",
            "AuthService",
            "authenticate",
            "validateToken",
            "User",
            "Token",
        }
        actual_symbols = set(symbols)

        # Should contain at least some of the expected symbols
        self.assertTrue(expected_symbols.intersection(actual_symbols))

    @patch("agents.dev.context_engine.serena_engine.subprocess.run")
    def test_symbol_context_search(self, mock_run):
        """Test symbol context search in project files."""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "available"

        engine = SerenaContextEngine(project_root=self.temp_dir)

        # Test finding UserController class
        context = engine._find_symbol_context("UserController")
        self.assertIsNotNone(context)
        self.assertIn("class UserController", context)
        self.assertIn("auth.py", context)

        # Test finding authenticate method
        context = engine._find_symbol_context("authenticate")
        self.assertIsNotNone(context)
        self.assertIn("def authenticate", context)

    @patch("agents.dev.context_engine.serena_engine.subprocess.run")
    def test_engine_info_collection(self, mock_run):
        """Test engine information and statistics collection."""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "available"

        engine = SerenaContextEngine(project_root=self.temp_dir)

        # Build context to populate stats
        engine.build_context(self.milestone_dir, "test")

        info = engine.get_engine_info()

        self.assertEqual(info["engine"], "serena_lsp_progressive")
        self.assertIn("description", info)
        self.assertIn("features", info)
        self.assertTrue(info["serena_available"])
        self.assertIn("stats", info)

        # Check stats structure
        stats = info["stats"]
        self.assertIn("queries_performed", stats)
        self.assertIn("symbols_found", stats)
        self.assertIn("tokens_saved", stats)
        self.assertIn("avg_response_time_ms", stats)

    @patch("agents.dev.context_engine.serena_engine.subprocess.run")
    def test_token_optimization_calculation(self, mock_run):
        """Test token optimization calculation for performance metrics."""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "available"

        engine = SerenaContextEngine(project_root=self.temp_dir)
        context, metadata = engine.build_context(self.milestone_dir, "test prompt")

        # Should have token optimization metrics
        self.assertIn("tokens_estimated", metadata)
        self.assertIn("tokens_saved", metadata)
        self.assertGreaterEqual(metadata["tokens_saved"], 0)

        # Should track response time
        self.assertIn("response_time_ms", metadata)
        self.assertGreater(metadata["response_time_ms"], 0)

    @patch("agents.dev.context_engine.serena_engine.subprocess.run")
    def test_language_detection(self, mock_run):
        """Test project language detection."""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "available"

        engine = SerenaContextEngine(project_root=self.temp_dir)
        languages = engine._detect_project_languages()

        # Should detect Python due to .py files
        self.assertIn("python", languages)

    def test_workspace_initialization(self):
        """Test Serena workspace initialization."""
        with patch("agents.dev.context_engine.serena_engine.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "available"

            engine = SerenaContextEngine(project_root=self.temp_dir)

            # Should create .serena directory
            serena_dir = self.temp_dir / ".serena"
            self.assertTrue(serena_dir.exists())

            # Should start MCP server (mocked as available)
            self.assertTrue(hasattr(engine, "_serena_available"))

    def test_error_handling_and_fallback(self):
        """Test error handling and fallback mechanisms."""
        with patch("agents.dev.context_engine.serena_engine.subprocess.run") as mock_run:
            # Mock Serena as unavailable
            mock_run.side_effect = FileNotFoundError("Serena not found")

            # Should not raise exception, should fallback
            engine = SerenaContextEngine(project_root=self.temp_dir)
            context, metadata = engine.build_context(self.milestone_dir, "test")

            # Should use fallback mode
            self.assertIn("fallback", metadata["engine"])
            self.assertFalse(metadata["lsp_available"])

    def test_invalid_balanced_target_env_var(self):
        """Test graceful handling of invalid SERENA_BALANCED_TARGET."""
        with patch.dict(os.environ, {"SERENA_BALANCED_TARGET": "invalid"}):
            with patch("agents.dev.context_engine.serena_engine.subprocess.run") as mock_run:
                # Mock Serena as available
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "available"

                # Should not raise exception even with invalid env var
                engine = SerenaContextEngine(project_root=self.temp_dir)

                # Should use default value of 1500 for BALANCED mode
                self.assertEqual(engine.max_tokens, 1500)  # Default for BALANCED mode


class TestSerenaIntegration(unittest.TestCase):
    """Integration tests for Serena with SoloPilot context engine factory."""

    def test_context_engine_factory_serena_support(self):
        """Test that context engine factory supports Serena."""
        from agents.dev.context_engine import get_context_engine

        with patch.dict("os.environ", {"CONTEXT_ENGINE": "serena", "NO_NETWORK": ""}):
            with patch("agents.dev.context_engine.serena_engine.subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "available"

                engine = get_context_engine()

                # Should return SerenaContextEngine
                self.assertIsInstance(engine, SerenaContextEngine)

                # Should have correct engine info
                info = engine.get_engine_info()
                self.assertEqual(info["engine"], "serena_lsp_progressive")

    def test_serena_fallback_in_factory(self):
        """Test Serena fallback to legacy in factory when unavailable."""
        from agents.dev.context_engine import LegacyContextEngine, get_context_engine

        with patch.dict("os.environ", {"CONTEXT_ENGINE": "serena"}):
            with patch(
                "agents.dev.context_engine.serena_engine.SerenaContextEngine"
            ) as mock_serena:
                mock_serena.side_effect = Exception("Serena failed")

                engine = get_context_engine()

                # Should fallback to LegacyContextEngine
                self.assertIsInstance(engine, LegacyContextEngine)


if __name__ == "__main__":
    unittest.main()
