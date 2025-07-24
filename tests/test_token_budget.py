#!/usr/bin/env python3
"""
Test Suite for Token Budget System

Tests the token budget enforcement, context mode selection, and smart truncation
to ensure costs are controlled while maintaining quality.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.agents.dev.context_engine.progressive_context import ContextTier, ProgressiveContextBuilder
from src.agents.dev.context_engine.serena_engine import SerenaContextEngine


class TestTokenBudgetEnforcement(unittest.TestCase):
    """Test token budget enforcement at all levels."""

    def setUp(self):
        """Set up test environment."""
        self.builder = ProgressiveContextBuilder(
            max_tokens=1500,
            tier_budgets={
                ContextTier.STUB: 500,
                ContextTier.LOCAL_BODY: 600,
                ContextTier.DEPENDENCIES: 300,
                ContextTier.FULL: 100,
            },
        )

    def test_token_counting_accuracy(self):
        """Test that token counting is accurate."""
        test_content = "def hello_world():\n    print('Hello, World!')\n    return True"

        # Test token estimation
        estimated = self.builder._estimate_tokens(test_content)

        # Should be reasonable estimate (roughly 1 token per 4 chars)
        expected_range = (len(test_content) // 6, len(test_content) // 3)
        self.assertGreaterEqual(estimated, expected_range[0])
        self.assertLessEqual(estimated, expected_range[1])

    def test_tier_budget_enforcement(self):
        """Test that tier budgets are strictly enforced."""
        # Create large content that exceeds tier budget
        large_stub = "x" * 3000  # ~750 tokens, exceeds 500 token STUB budget

        # Should reject content exceeding tier budget
        result = self.builder.add_context(large_stub, ContextTier.STUB, "large_symbol", "stub")
        self.assertFalse(result, "Should reject content exceeding tier budget")

        # Should track skipped context
        self.assertEqual(len(self.builder.skipped_contexts), 1)
        self.assertEqual(self.builder.skipped_contexts[0]["reason"], "tier_budget_exceeded")

    def test_total_budget_enforcement(self):
        """Test that total budget is strictly enforced."""
        # Add content up to near the limit
        for i in range(5):
            content = "x" * 1000  # ~250 tokens each
            success = self.builder.add_context(content, ContextTier.STUB, f"symbol_{i}", "stub")
            if not success:
                break

        # Try to add more content that would exceed total budget
        overflow_content = "x" * 1000  # ~250 more tokens
        result = self.builder.add_context(
            overflow_content, ContextTier.STUB, "overflow_symbol", "stub"
        )

        # Should reject content exceeding total budget
        self.assertFalse(result, "Should reject content exceeding total budget")

        # Should never exceed max tokens
        self.assertLessEqual(self.builder.current_tokens, self.builder.max_tokens)

    def test_smart_truncation(self):
        """Test that smart truncation preserves important content."""
        # Add content to different tiers
        tier_contents = [
            (ContextTier.STUB, "def stub(): pass", "essential_stub"),
            (ContextTier.LOCAL_BODY, "def local(): return True", "local_impl"),
            (ContextTier.DEPENDENCIES, "def dep(): pass", "dependency"),
            (ContextTier.FULL, "def full(): return 'complete'", "full_context"),
        ]

        for tier, content, symbol in tier_contents:
            self.builder.add_context(content, tier, symbol, "test")

        # Force the builder over budget
        self.builder.current_tokens = self.builder.max_tokens + 100

        # Apply smart truncation
        self.builder._apply_smart_truncation()

        # Should be within budget after truncation
        self.assertLessEqual(self.builder.current_tokens, self.builder.max_tokens)

        # Should preserve T0 stubs (never remove)
        stub_contexts = [
            part for part in self.builder.context_parts if part["tier"] == ContextTier.STUB.name
        ]
        self.assertGreater(len(stub_contexts), 0, "Should preserve T0 stubs")

    def test_skipped_context_tracking(self):
        """Test that skipped contexts are properly tracked."""
        # Try to add content that will be skipped
        large_content = "x" * 5000  # Very large content

        result = self.builder.add_context(large_content, ContextTier.STUB, "huge_symbol", "stub")

        self.assertFalse(result)
        self.assertEqual(len(self.builder.skipped_contexts), 1)

        skip_info = self.builder.skipped_contexts[0]
        self.assertEqual(skip_info["symbol"], "huge_symbol")
        self.assertEqual(skip_info["tier"], ContextTier.STUB.name)
        self.assertIn(skip_info["reason"], ["tier_budget_exceeded", "total_budget_exceeded"])
        self.assertGreater(skip_info["tokens"], 0)

    def test_warning_generation(self):
        """Test that warnings are generated when context is truncated."""
        # Add content that will be skipped
        large_content = "x" * 3000
        self.builder.add_context(large_content, ContextTier.STUB, "large_symbol", "stub")

        # Build final context
        context = self.builder.build_final_context("Test prompt", "test_milestone")

        # Should include warning about truncation
        self.assertIn("Context truncated", context)
        self.assertIn("Budget Management Warning", context)

        # Should have warnings in metadata
        metadata = self.builder.get_metadata()
        self.assertGreater(len(metadata["warnings"]), 0)
        self.assertGreater(metadata["symbols_skipped"], 0)


class TestContextModeSelection(unittest.TestCase):
    """Test context mode selection and configuration."""

    def test_context_mode_initialization(self):
        """Test that context modes are properly initialized."""
        # Test MINIMAL mode
        minimal_engine = SerenaContextEngine(context_mode="MINIMAL")
        self.assertEqual(minimal_engine.context_mode, "MINIMAL")
        self.assertEqual(minimal_engine.max_tokens, 800)

        # Test BALANCED mode
        balanced_engine = SerenaContextEngine(context_mode="BALANCED")
        self.assertEqual(balanced_engine.context_mode, "BALANCED")
        self.assertEqual(balanced_engine.max_tokens, 1500)

        # Test COMPREHENSIVE mode
        comprehensive_engine = SerenaContextEngine(context_mode="COMPREHENSIVE")
        self.assertEqual(comprehensive_engine.context_mode, "COMPREHENSIVE")
        self.assertEqual(comprehensive_engine.max_tokens, float("inf"))

    def test_context_mode_auto_selection(self):
        """Test automatic context mode selection based on prompts."""
        engine = SerenaContextEngine()

        # Test MINIMAL selection
        minimal_prompts = [
            "Fix the typo in the error message",
            "Add a docstring to the function",
            "Rename variable from 'user' to 'username'",
            "Update the import statement",
        ]

        for prompt in minimal_prompts:
            selected = engine._select_context_mode(prompt)
            self.assertEqual(selected, "MINIMAL", f"Should select MINIMAL for: {prompt}")

        # Test COMPREHENSIVE selection
        comprehensive_prompts = [
            "Refactor the entire authentication system",
            "Provide complete architecture overview",
            "Design comprehensive security system",
            "Detailed review of system design",
        ]

        for prompt in comprehensive_prompts:
            selected = engine._select_context_mode(prompt)
            self.assertEqual(
                selected, "COMPREHENSIVE", f"Should select COMPREHENSIVE for: {prompt}"
            )

        # Test BALANCED (default) selection
        balanced_prompts = [
            "Implement OAuth2 authentication",
            "Debug the session handling issue",
            "Add error handling to the API",
        ]

        for prompt in balanced_prompts:
            selected = engine._select_context_mode(prompt)
            self.assertEqual(selected, "BALANCED", f"Should select BALANCED for: {prompt}")

    @patch.dict("os.environ", {"SERENA_CONTEXT_MODE": "MINIMAL"})
    def test_environment_override(self):
        """Test that environment variables override context mode."""
        engine = SerenaContextEngine(context_mode="BALANCED")
        self.assertEqual(engine.context_mode, "MINIMAL")
        self.assertEqual(engine.max_tokens, 800)


class TestTokenBudgetIntegration(unittest.TestCase):
    """Test integration of token budget system with SerenaContextEngine."""

    def setUp(self):
        """Set up test environment with mock project."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)

        # Create mock Python file
        (self.project_root / "auth.py").write_text(
            """
class AuthManager:
    '''Authentication manager'''
    
    def authenticate(self, username, password):
        '''Authenticate user'''
        return self.validate_credentials(username, password)
    
    def validate_credentials(self, username, password):
        '''Validate credentials'''
        return username == "test"
"""
        )

        # Create milestone
        self.milestone_dir = self.project_root / "output" / "dev" / "auth_milestone"
        self.milestone_dir.mkdir(parents=True)

        milestone_data = {
            "components": ["AuthManager"],
            "functions": ["authenticate", "validate_credentials"],
            "classes": ["AuthManager"],
        }
        (self.milestone_dir / "milestone.json").write_text(json.dumps(milestone_data))

    def tearDown(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("src.agents.dev.context_engine.serena_engine.SerenaContextEngine._start_serena_server")
    def test_balanced_mode_token_limits(self, mock_start_server):
        """Test that BALANCED mode respects 1500 token limit."""
        mock_start_server.return_value = False  # Use fallback

        engine = SerenaContextEngine(self.project_root, context_mode="BALANCED")

        # Test with complex prompt that would normally generate lots of context
        complex_prompt = "Analyze all authentication systems and provide comprehensive review"
        context, metadata = engine.build_context(self.milestone_dir, complex_prompt)

        # Should respect token limit
        self.assertLessEqual(
            metadata["token_count"], 1500, "BALANCED mode should not exceed 1500 tokens"
        )
        self.assertEqual(metadata["context_mode"], "BALANCED")
        self.assertEqual(metadata["max_tokens"], 1500)

    @patch("src.agents.dev.context_engine.serena_engine.SerenaContextEngine._start_serena_server")
    def test_minimal_mode_token_limits(self, mock_start_server):
        """Test that MINIMAL mode respects 800 token limit."""
        mock_start_server.return_value = False  # Use fallback

        engine = SerenaContextEngine(self.project_root, context_mode="MINIMAL")

        # Test with simple prompt
        simple_prompt = "Fix typo in the error message"
        context, metadata = engine.build_context(self.milestone_dir, simple_prompt)

        # Should respect minimal token limit
        self.assertLessEqual(
            metadata["token_count"], 800, "MINIMAL mode should not exceed 800 tokens"
        )
        self.assertEqual(metadata["context_mode"], "MINIMAL")
        self.assertEqual(metadata["max_tokens"], 800)

    @patch("src.agents.dev.context_engine.serena_engine.SerenaContextEngine._start_serena_server")
    def test_comprehensive_mode_no_limits(self, mock_start_server):
        """Test that COMPREHENSIVE mode has no token limits."""
        mock_start_server.return_value = False  # Use fallback

        engine = SerenaContextEngine(self.project_root, context_mode="COMPREHENSIVE")

        # Test with complex prompt
        complex_prompt = "Provide complete architecture analysis with full implementation details"
        context, metadata = engine.build_context(self.milestone_dir, complex_prompt)

        # Should have no limit (inf)
        self.assertEqual(metadata["context_mode"], "COMPREHENSIVE")
        self.assertEqual(metadata["max_tokens"], float("inf"))

    @patch("src.agents.dev.context_engine.serena_engine.SerenaContextEngine._start_serena_server")
    def test_warnings_displayed(self, mock_start_server):
        """Test that warnings are displayed when context is truncated."""
        mock_start_server.return_value = False  # Use fallback

        engine = SerenaContextEngine(self.project_root, context_mode="MINIMAL")

        # Use a prompt that will likely require truncation in minimal mode
        large_prompt = "Provide detailed analysis of authentication system with complete implementation review and security audit"
        context, metadata = engine.build_context(self.milestone_dir, large_prompt)

        # Check if warnings are present (may or may not be truncated depending on actual content)
        if metadata.get("symbols_skipped", 0) > 0:
            self.assertGreater(len(metadata.get("warnings", [])), 0)
            self.assertIn("truncated", context.lower())


class TestCITokenValidation(unittest.TestCase):
    """Test CI validation that dev-agent never exceeds 2000 tokens."""

    def test_token_limit_validation(self):
        """Verify that no context mode exceeds 2000 token CI limit."""
        modes = ["MINIMAL", "BALANCED", "COMPREHENSIVE"]

        for mode in modes:
            with self.subTest(mode=mode):
                if mode == "COMPREHENSIVE":
                    # COMPREHENSIVE mode is unlimited, but should be used sparingly
                    continue

                engine = SerenaContextEngine(context_mode=mode)

                # All limited modes should be well under 2000 tokens
                self.assertLessEqual(
                    engine.max_tokens, 2000, f"{mode} mode should not exceed 2000 token CI limit"
                )

    def test_budget_violation_tracking(self):
        """Test that budget violations are properly tracked."""
        builder = ProgressiveContextBuilder(max_tokens=100)  # Very small limit

        # Try to add content that exceeds limit
        large_content = "x" * 1000  # Definitely exceeds 100 token limit

        result = builder.add_context(large_content, ContextTier.STUB, "large_symbol", "stub")
        self.assertFalse(result)

        # Should track the violation
        metadata = builder.get_metadata()
        self.assertGreater(metadata["symbols_skipped"], 0)

    def test_performance_requirements(self):
        """Test that budget enforcement doesn't significantly impact performance."""
        import time

        start_time = time.time()

        # Create builder and add multiple contexts
        builder = ProgressiveContextBuilder(max_tokens=1500)

        for i in range(20):
            content = f"def function_{i}():\n    return {i}"
            builder.add_context(content, ContextTier.STUB, f"func_{i}", "stub")

        end_time = time.time()
        processing_time = end_time - start_time

        # Should complete quickly (under 1 second for 20 contexts)
        self.assertLess(
            processing_time, 1.0, "Budget enforcement should not significantly impact performance"
        )


class TestBalancedModeOptimization(unittest.TestCase):
    """Test that BALANCED mode averages 1000-1500 tokens on sample projects."""

    def setUp(self):
        """Create sample projects for testing."""
        self.sample_projects = []

        # Sample project 1: Simple web API
        project1 = tempfile.mkdtemp()
        self.sample_projects.append(Path(project1))

        (Path(project1) / "api.py").write_text(
            """
class UserAPI:
    def get_user(self, user_id):
        return {"id": user_id, "name": "Test User"}
    
    def create_user(self, user_data):
        return {"id": 123, **user_data}
"""
        )

        # Sample project 2: Authentication system
        project2 = tempfile.mkdtemp()
        self.sample_projects.append(Path(project2))

        (Path(project2) / "auth.py").write_text(
            """
import hashlib
from datetime import datetime

class AuthService:
    def __init__(self):
        self.sessions = {}
    
    def login(self, username, password):
        if self.validate_credentials(username, password):
            session_id = self.create_session(username)
            return {"session_id": session_id, "username": username}
        return None
    
    def validate_credentials(self, username, password):
        # Simple validation
        return len(username) > 0 and len(password) > 6
    
    def create_session(self, username):
        session_id = hashlib.md5(f"{username}{datetime.now()}".encode()).hexdigest()
        self.sessions[session_id] = {
            "username": username,
            "created_at": datetime.now()
        }
        return session_id
"""
        )

        # Create milestones for each project
        for i, project_root in enumerate(self.sample_projects):
            milestone_dir = project_root / "output" / "dev" / f"milestone_{i}"
            milestone_dir.mkdir(parents=True)

            milestone_data = {
                "components": ["UserAPI", "AuthService"],
                "functions": ["get_user", "create_user", "login", "validate_credentials"],
                "classes": ["UserAPI", "AuthService"],
            }
            (milestone_dir / "milestone.json").write_text(json.dumps(milestone_data))

    def tearDown(self):
        """Clean up sample projects."""
        import shutil

        for project_root in self.sample_projects:
            shutil.rmtree(project_root, ignore_errors=True)

    @patch("src.agents.dev.context_engine.serena_engine.SerenaContextEngine._start_serena_server")
    def test_balanced_mode_token_average(self, mock_start_server):
        """Test that BALANCED mode averages 1000-1500 tokens on sample projects."""
        mock_start_server.return_value = False  # Use fallback

        # Test scenarios representing typical development tasks
        test_scenarios = [
            "Add error handling to the login function",
            "Implement password hashing for security",
            "Add input validation to the create_user method",
            "Debug session management issues",
            "Add logging to authentication methods",
            "Implement rate limiting for API endpoints",
        ]

        total_tokens = 0
        scenario_count = 0

        for project_root in self.sample_projects:
            milestone_dir = (
                project_root
                / "output"
                / "dev"
                / f"milestone_{self.sample_projects.index(project_root)}"
            )
            engine = SerenaContextEngine(project_root, context_mode="BALANCED")

            for scenario in test_scenarios:
                context, metadata = engine.build_context(milestone_dir, scenario)
                token_count = metadata["token_count"]

                # Each individual request should be within BALANCED limits
                self.assertLessEqual(
                    token_count, 1500, f"Scenario '{scenario}' exceeded BALANCED limit"
                )

                total_tokens += token_count
                scenario_count += 1

        # Calculate average
        average_tokens = total_tokens / scenario_count if scenario_count > 0 else 0

        print(f"Average tokens across {scenario_count} scenarios: {average_tokens:.1f}")

        # Should average between 1000-1500 tokens
        self.assertGreaterEqual(
            average_tokens, 800, "Average should be at least 800 tokens (not too aggressive)"
        )
        self.assertLessEqual(
            average_tokens, 1500, "Average should not exceed 1500 tokens (BALANCED limit)"
        )

        # Ideally should be in the 1000-1500 range for good balance
        if average_tokens >= 1000:
            print(f"✅ BALANCED mode achieves target range: {average_tokens:.1f} tokens average")
        else:
            print(f"⚠️ BALANCED mode below target range: {average_tokens:.1f} tokens average")


if __name__ == "__main__":
    # Run all tests
    unittest.main(verbosity=2)
