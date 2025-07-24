#!/usr/bin/env python3
"""
Test Suite for Progressive Context System

Validates the Progressive Context implementation against efficiency and quality benchmarks.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.agents.dev.context_engine.progressive_context import (
    ContextTier,
    ProgressiveContextBuilder,
    SymbolSelector,
)
from src.agents.dev.context_engine.serena_engine import SerenaContextEngine


class TestProgressiveContextBuilder(unittest.TestCase):
    """Test the core ProgressiveContextBuilder functionality."""

    def setUp(self):
        """Set up test environment."""
        self.builder = ProgressiveContextBuilder(max_tokens=1800)

    def test_tier_escalation(self):
        """Test automatic tier escalation based on prompt complexity."""
        # Simple prompt should not escalate
        simple_prompt = "Fix the typo in the error message"
        self.assertFalse(self.builder.should_escalate(simple_prompt))

        # Complex prompts should escalate
        complex_prompts = [
            "Refactor authentication to use OAuth2",
            "Find and fix the race condition in job processing",
            "Implement caching layer for performance optimization",
            "Debug cross-file dependency issues",
        ]

        for prompt in complex_prompts:
            builder = ProgressiveContextBuilder(max_tokens=1800)
            self.assertTrue(builder.should_escalate(prompt), f"Should escalate for: {prompt}")

    def test_token_budget_management(self):
        """Test token budget enforcement and tier limits."""
        # Test tier limits
        tier_limits = {
            ContextTier.STUB: 400,
            ContextTier.LOCAL_BODY: 800,
            ContextTier.DEPENDENCIES: 1200,
            ContextTier.FULL: 1800,
        }

        for tier, limit in tier_limits.items():
            builder = ProgressiveContextBuilder(max_tokens=1800)
            builder.tier = tier

            # Should accept content within limit
            content_within_limit = "x" * (limit * 4 - 100)  # Leave some margin
            self.assertTrue(builder.can_add_context(content_within_limit, tier))

            # Should reject content exceeding limit
            content_exceeding_limit = "x" * (limit * 4 + 100)
            self.assertFalse(builder.can_add_context(content_exceeding_limit, tier))

    def test_context_addition_and_tracking(self):
        """Test context addition and metadata tracking."""
        builder = ProgressiveContextBuilder(max_tokens=1800)

        # Add stub context
        stub_content = "def example_function():\n    '''Example function'''\n    ..."
        self.assertTrue(
            builder.add_context(stub_content, ContextTier.STUB, "example_function", "stub")
        )

        # Check metadata
        metadata = builder.get_metadata()
        self.assertEqual(metadata["symbols_processed"], 1)
        self.assertGreater(metadata["tokens_used"], 0)
        self.assertIn(ContextTier.STUB.name, metadata["tier_progression"])

        # Add full body context
        full_content = (
            "def example_function():\n    '''Example function'''\n    return 'Hello, World!'"
        )
        self.assertTrue(
            builder.add_context(
                full_content, ContextTier.LOCAL_BODY, "example_function", "full_body"
            )
        )

        # Check tier progression
        metadata = builder.get_metadata()
        self.assertEqual(metadata["symbols_processed"], 2)
        self.assertIn(ContextTier.LOCAL_BODY.name, metadata["tier_progression"])

    def test_final_context_building(self):
        """Test final context string generation."""
        builder = ProgressiveContextBuilder(max_tokens=1800)

        # Add some context
        builder.add_context("def test_func(): pass", ContextTier.STUB, "test_func", "stub")
        builder.add_context(
            "class TestClass: pass", ContextTier.LOCAL_BODY, "TestClass", "full_body"
        )

        # Build final context
        final_context = builder.build_final_context("Test prompt", "test_milestone")

        # Verify structure
        self.assertIn("SoloPilot Progressive Context", final_context)
        self.assertIn("test_milestone", final_context)
        self.assertIn("Test prompt", final_context)
        self.assertIn("test_func", final_context)
        self.assertIn("TestClass", final_context)
        self.assertIn("Context Metadata", final_context)


class TestSymbolSelector(unittest.TestCase):
    """Test smart symbol selection algorithms."""

    def test_primary_target_identification(self):
        """Test identification of primary targets from prompts."""
        symbols = [
            "UserManager",
            "user_service",
            "authenticate_user",
            "login_handler",
            "create_session",
        ]

        # Test direct mention
        prompt1 = "Refactor the UserManager class to use dependency injection"
        targets1 = SymbolSelector.identify_primary_targets(prompt1, symbols)
        self.assertIn("UserManager", targets1)

        # Test action-based detection
        prompt2 = "Fix authenticate_user function"
        targets2 = SymbolSelector.identify_primary_targets(prompt2, symbols)
        self.assertIn("authenticate_user", targets2)

        # Test partial matching
        prompt3 = "Update user authentication logic"
        targets3 = SymbolSelector.identify_primary_targets(prompt3, symbols)
        # Should find symbols containing "user" or "auth"
        found_user_related = any(
            "user" in target.lower() or "auth" in target.lower() for target in targets3
        )
        self.assertTrue(found_user_related)

    def test_symbol_prioritization(self):
        """Test symbol prioritization by relevance."""
        symbols = ["DatabaseManager", "UserService", "auth_handler", "cache_utils", "log_message"]

        # Test auth-related prompt
        auth_prompt = "Implement OAuth authentication system"
        prioritized = SymbolSelector.prioritize_symbols_by_relevance(auth_prompt, symbols)

        # Auth-related symbols should be ranked higher
        auth_symbols = [s for s in prioritized if "auth" in s.lower() or "user" in s.lower()]
        non_auth_symbols = [s for s in prioritized if s not in auth_symbols]

        if auth_symbols and non_auth_symbols:
            auth_index = prioritized.index(auth_symbols[0])
            non_auth_index = prioritized.index(non_auth_symbols[0])
            self.assertLess(
                auth_index, non_auth_index, "Auth symbols should be prioritized for auth prompt"
            )


class TestSerenaProgressiveIntegration(unittest.TestCase):
    """Test integration of progressive context with Serena engine."""

    def setUp(self):
        """Set up test environment with mock project."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)

        # Create mock Python files
        (self.project_root / "main.py").write_text(
            """
def main():
    '''Main entry point'''
    user_mgr = UserManager()
    return user_mgr.authenticate("test")

class UserManager:
    '''Manages user operations'''
    
    def authenticate(self, username):
        '''Authenticate user'''
        return self.validate_credentials(username)
    
    def validate_credentials(self, username):
        '''Validate user credentials'''
        return username == "test"
"""
        )

        # Create milestone directory
        self.milestone_dir = self.project_root / "output" / "dev" / "milestone1"
        self.milestone_dir.mkdir(parents=True)

        milestone_data = {
            "components": ["UserManager", "authenticate"],
            "functions": ["main", "validate_credentials"],
            "classes": ["UserManager"],
        }
        (self.milestone_dir / "milestone.json").write_text(json.dumps(milestone_data))

    def tearDown(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("src.agents.dev.context_engine.serena_engine.SerenaContextEngine._start_serena_server")
    def test_progressive_context_building(self, mock_start_server):
        """Test progressive context building in SerenaContextEngine."""
        # Mock Serena as unavailable to test fallback
        mock_start_server.return_value = False

        engine = SerenaContextEngine(self.project_root)

        # Test simple prompt (should use T0)
        simple_prompt = "Fix typo in error message"
        context1, metadata1 = engine.build_context(self.milestone_dir, simple_prompt)

        self.assertIsInstance(context1, str)
        self.assertIsInstance(metadata1, dict)
        self.assertIn("engine", metadata1)

        # Test complex prompt (should escalate)
        complex_prompt = "Refactor authentication system for OAuth2 integration"
        context2, metadata2 = engine.build_context(self.milestone_dir, complex_prompt)

        self.assertIsInstance(context2, str)
        self.assertIsInstance(metadata2, dict)

    def test_stub_context_extraction(self):
        """Test stub context extraction functionality."""
        engine = SerenaContextEngine(self.project_root)

        # Test stub extraction for existing symbol
        stub = engine._get_symbol_stub("UserManager")
        if stub:  # May be None if method uses Serena MCP
            self.assertIn("class UserManager", stub)
            self.assertIn("Manages user operations", stub)

        # Test stub extraction for function
        stub_func = engine._get_symbol_stub("authenticate")
        if stub_func:
            self.assertIn("def authenticate", stub_func)

    def test_dependency_extraction(self):
        """Test dependency extraction for symbols."""
        engine = SerenaContextEngine(self.project_root)

        # Test dependency extraction
        deps = engine._get_symbol_dependencies("UserManager")
        self.assertIsInstance(deps, list)

        # Dependencies might include validate_credentials, or imported modules
        # This test verifies the method doesn't crash and returns a list

    def test_on_demand_context_fetching(self):
        """Test on-demand context fetching capability."""
        engine = SerenaContextEngine(self.project_root)

        # Test different tiers
        tiers = ["stub", "body", "dependencies", "file"]

        for tier in tiers:
            context = engine.fetch_more_context("UserManager", tier)
            self.assertIsInstance(context, str)
            self.assertGreater(len(context), 0)

        # Test invalid tier
        invalid_context = engine.fetch_more_context("UserManager", "invalid_tier")
        self.assertIn("Unknown context tier", invalid_context)


class TestProgressiveContextBenchmarks(unittest.TestCase):
    """Benchmark tests for progressive context efficiency."""

    def setUp(self):
        """Set up benchmark environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.project_root = Path(self.temp_dir)

        # Create a larger mock codebase for benchmarking
        files = {
            "auth.py": """
class AuthManager:
    '''Authentication manager with OAuth2 support'''
    
    def __init__(self):
        self.oauth_client = OAuthClient()
        self.session_store = SessionStore()
    
    def authenticate(self, username, password):
        '''Authenticate user with username/password'''
        if self.validate_credentials(username, password):
            return self.create_session(username)
        return None
    
    def oauth_authenticate(self, token):
        '''Authenticate using OAuth2 token'''
        user_info = self.oauth_client.verify_token(token)
        if user_info:
            return self.create_session(user_info['username'])
        return None
    
    def validate_credentials(self, username, password):
        '''Validate user credentials against database'''
        # Complex validation logic here
        return True
    
    def create_session(self, username):
        '''Create new user session'''
        session = Session(username)
        self.session_store.save(session)
        return session
""",
            "oauth.py": """
class OAuthClient:
    '''OAuth2 client implementation'''
    
    def verify_token(self, token):
        '''Verify OAuth2 token'''
        # Token verification logic
        return {'username': 'test_user'}
    
    def refresh_token(self, refresh_token):
        '''Refresh OAuth2 token'''
        # Token refresh logic
        return 'new_token'
""",
            "session.py": """
class Session:
    '''User session management'''
    
    def __init__(self, username):
        self.username = username
        self.created_at = datetime.now()
    
    def is_valid(self):
        '''Check if session is still valid'''
        return True

class SessionStore:
    '''Session storage manager'''
    
    def save(self, session):
        '''Save session to storage'''
        pass
    
    def get(self, session_id):
        '''Get session by ID'''
        pass
""",
        }

        for filename, content in files.items():
            (self.project_root / filename).write_text(content)

        # Create milestone
        self.milestone_dir = self.project_root / "output" / "dev" / "auth_milestone"
        self.milestone_dir.mkdir(parents=True)

        milestone_data = {
            "components": ["AuthManager", "OAuthClient", "Session", "SessionStore"],
            "functions": [
                "authenticate",
                "oauth_authenticate",
                "validate_credentials",
                "create_session",
            ],
            "classes": ["AuthManager", "OAuthClient", "Session", "SessionStore"],
        }
        (self.milestone_dir / "milestone.json").write_text(json.dumps(milestone_data))

    def tearDown(self):
        """Clean up benchmark environment."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_simple_task_efficiency(self):
        """Benchmark: Simple tasks should use ≤500 tokens."""
        builder = ProgressiveContextBuilder(max_tokens=1800)

        simple_prompts = [
            "Fix the typo in the error message",
            "Add a docstring to the authenticate method",
            "Change variable name from 'user' to 'username'",
        ]

        for prompt in simple_prompts:
            builder.reset()

            # Simulate adding stub context for simple task
            stub_content = (
                "def authenticate(username, password):\n    '''Authenticate user'''\n    ..."
            )
            builder.add_context(stub_content, ContextTier.STUB, "authenticate", "stub")

            # Simple tasks should not escalate
            should_escalate = builder.should_escalate(prompt)
            self.assertFalse(should_escalate, f"Simple task should not escalate: {prompt}")

            # Token usage should be minimal
            self.assertLessEqual(
                builder.current_tokens, 125, f"Simple task should use ≤500 tokens: {prompt}"
            )  # 500/4

    def test_complex_task_escalation(self):
        """Benchmark: Complex tasks should escalate appropriately."""
        complex_prompts = [
            "Refactor authentication to use OAuth2",
            "Find and fix the race condition in job processing",
            "Implement comprehensive security audit for auth system",
        ]

        for prompt in complex_prompts:
            builder = ProgressiveContextBuilder(max_tokens=1800)

            # Should detect complexity and escalate
            should_escalate = builder.should_escalate(prompt)
            self.assertTrue(should_escalate, f"Complex task should escalate: {prompt}")

            # Simulate progressive context building
            # T0: Stubs
            stub_content = "def authenticate(username, password): ..."
            builder.add_context(stub_content, ContextTier.STUB, "authenticate", "stub")

            # T1: Full bodies for primary targets
            if builder.should_escalate(prompt):
                builder.escalate_tier(ContextTier.LOCAL_BODY, "complex_detected")
                full_content = """
def authenticate(self, username, password):
    '''Authenticate user with username/password'''
    if self.validate_credentials(username, password):
        return self.create_session(username)
    return None
"""
                builder.add_context(
                    full_content, ContextTier.LOCAL_BODY, "authenticate", "full_body"
                )

            # Should stay within limits
            self.assertLessEqual(
                builder.current_tokens, 1800, f"Should not exceed max tokens: {prompt}"
            )
            self.assertLessEqual(
                builder.current_tokens, 375, f"Complex task should use ≤1500 tokens: {prompt}"
            )  # 1500/4

    def test_token_efficiency_vs_quality(self):
        """Benchmark: Ensure token efficiency doesn't compromise quality."""
        builder = ProgressiveContextBuilder(max_tokens=1800)

        # OAuth refactor task (should escalate to T1-T2)
        oauth_prompt = "Refactor authentication system to use OAuth2 instead of username/password"

        # Simulate symbol discovery
        symbols = ["AuthManager", "authenticate", "oauth_authenticate", "OAuthClient", "Session"]
        prioritized = SymbolSelector.prioritize_symbols_by_relevance(oauth_prompt, symbols)

        # OAuth-related symbols should be prioritized
        oauth_symbols = [s for s in prioritized if "oauth" in s.lower() or "auth" in s.lower()]
        self.assertGreater(len(oauth_symbols), 0, "Should find OAuth-related symbols")

        # Build progressive context
        for symbol in prioritized[:3]:  # Top 3 symbols
            stub = f"def {symbol.lower()}(): ..."
            builder.add_context(stub, ContextTier.STUB, symbol, "stub")

        # Should escalate for OAuth task
        self.assertTrue(builder.should_escalate(oauth_prompt))

        # Add full context for primary targets
        if builder.escalate_tier(ContextTier.LOCAL_BODY, "oauth_refactor"):
            primary_targets = SymbolSelector.identify_primary_targets(oauth_prompt, prioritized)
            for target in primary_targets[:2]:
                full_impl = f"class {target}:\n    def method(self): pass"
                builder.add_context(full_impl, ContextTier.LOCAL_BODY, target, "full_body")

        # Quality check: Should have adequate context for OAuth refactor
        final_context = builder.build_final_context(oauth_prompt, "oauth_milestone")
        self.assertIn("oauth", final_context.lower(), "Should include OAuth context")
        self.assertIn("auth", final_context.lower(), "Should include auth context")

        # Efficiency check: Should not exceed 1200 tokens for T1-T2
        self.assertLessEqual(
            builder.current_tokens, 300, "OAuth refactor should use ≤1200 tokens"
        )  # 1200/4

    def test_hard_token_limit_enforcement(self):
        """Benchmark: Never exceed 1800 token hard limit."""
        builder = ProgressiveContextBuilder(max_tokens=1800)

        # Try to add massive amounts of context
        large_content = "x" * 10000  # Very large content

        # Should reject content that would exceed limit
        for i in range(10):
            can_add = builder.can_add_context(large_content)
            if can_add:
                builder.add_context(large_content, ContextTier.FULL, f"symbol_{i}", "large")
            else:
                break

        # Should never exceed hard limit
        self.assertLessEqual(builder.current_tokens, 1800, "Should never exceed hard token limit")

        # Should be close to limit but not over
        self.assertGreater(
            builder.current_tokens,
            1000,
            "Should use substantial portion of budget when hitting limit",
        )


if __name__ == "__main__":
    # Run all tests
    unittest.main(verbosity=2)
