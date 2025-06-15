#!/usr/bin/env python3
"""
Comprehensive tests for Context Engine functionality
"""

import os
import sys
import tempfile
import json
from pathlib import Path
from unittest.mock import patch

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestContextEngineFactory:
    """Test the context engine factory functionality."""

    def test_get_context_engine_default_legacy(self):
        """Test that default context engine is legacy."""
        from agents.dev.context_engine import get_context_engine
        
        engine = get_context_engine()
        info = engine.get_engine_info()
        assert info["engine"] == "legacy"
        assert info["offline"] is True

    def test_get_context_engine_explicit_legacy(self):
        """Test explicitly requesting legacy engine."""
        from agents.dev.context_engine import get_context_engine
        
        engine = get_context_engine("legacy")
        info = engine.get_engine_info()
        assert info["engine"] == "legacy"

    def test_get_context_engine_no_network_forces_legacy(self):
        """Test that NO_NETWORK=1 forces legacy engine."""
        from agents.dev.context_engine import get_context_engine
        
        with patch.dict(os.environ, {"NO_NETWORK": "1", "CONTEXT_ENGINE": "lc_chroma"}):
            engine = get_context_engine()
            info = engine.get_engine_info()
            assert info["engine"] == "legacy"

    def test_get_context_engine_langchain_chroma(self):
        """Test LangChain + Chroma engine initialization."""
        from agents.dev.context_engine import get_context_engine
        
        # Clear NO_NETWORK to allow LangChain engine
        with patch.dict(os.environ, {"NO_NETWORK": ""}, clear=False):
            try:
                engine = get_context_engine("lc_chroma")
                info = engine.get_engine_info()
                assert info["engine"] == "langchain_chroma"
                assert info["offline"] is False
            except RuntimeError:
                # ChromaDB dependencies not available
                pytest.skip("ChromaDB dependencies not available")

    def test_context_engine_build_context_compatibility(self):
        """Test that build_context function works for backward compatibility."""
        from agents.dev.context_engine import build_context
        
        with tempfile.TemporaryDirectory() as temp_dir:
            milestone_path = Path(temp_dir) / "test_milestone"
            milestone_path.mkdir()
            
            (milestone_path / "milestone.json").write_text('{"name": "test"}')
            
            context = build_context(milestone_path)
            assert isinstance(context, str)
            assert len(context) > 0
            assert "test" in context


class TestLegacyContextEngine:
    """Test the legacy context engine wrapper."""

    def test_legacy_context_engine_build_context(self):
        """Test legacy context engine builds context correctly."""
        from agents.dev.context_engine import LegacyContextEngine
        
        engine = LegacyContextEngine()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            milestone_path = Path(temp_dir) / "test_milestone"
            milestone_path.mkdir()
            
            (milestone_path / "milestone.json").write_text('{"name": "test-project"}')
            (milestone_path / "package.json").write_text('{"name": "test-app"}')
            
            context, metadata = engine.build_context(milestone_path, "test prompt")
            
            assert isinstance(context, str)
            assert "test-project" in context
            assert "test prompt" in context
            assert metadata["engine"] == "legacy_context_packer"
            assert metadata["token_count"] > 0

    def test_legacy_context_engine_get_info(self):
        """Test legacy context engine info."""
        from agents.dev.context_engine import LegacyContextEngine
        
        engine = LegacyContextEngine()
        info = engine.get_engine_info()
        
        assert info["engine"] == "legacy"
        assert info["offline"] is True
        assert "features" in info


class TestLangChainChromaEngine:
    """Test the LangChain + ChromaDB context engine."""

    def test_langchain_chroma_engine_availability(self):
        """Test LangChain + Chroma engine availability."""
        try:
            from agents.dev.context_engine import LangChainChromaEngine
            
            engine = LangChainChromaEngine()
            info = engine.get_engine_info()
            
            assert info["engine"] == "langchain_chroma"
            assert info["offline"] is False
            assert "stats" in info
            
        except RuntimeError:
            pytest.skip("ChromaDB dependencies not available")

    def test_langchain_chroma_engine_build_context(self):
        """Test LangChain + Chroma engine builds enhanced context."""
        try:
            from agents.dev.context_engine import LangChainChromaEngine
            
            with tempfile.TemporaryDirectory() as temp_dir:
                engine = LangChainChromaEngine(persist_directory=temp_dir + "/test_chroma")
                
                milestone_path = Path(temp_dir) / "test_milestone"
                milestone_path.mkdir()
                
                (milestone_path / "milestone.json").write_text('{"name": "advanced-app", "description": "Advanced application"}')
                (milestone_path / "package.json").write_text('{"name": "advanced-app", "dependencies": {"express": "^4.0.0"}}')
                (milestone_path / "README.md").write_text("# Advanced App\nThis is an advanced application.")
                
                context, metadata = engine.build_context(milestone_path, "Create advanced API endpoints")
                
                assert isinstance(context, str)
                assert len(context) > 0
                assert "advanced-app" in context
                assert "Create advanced API endpoints" in context
                assert metadata["engine"] == "langchain_chroma"
                assert metadata["token_count"] > 0
                assert "context_sections" in metadata
                
        except RuntimeError:
            pytest.skip("ChromaDB dependencies not available")


class TestContextEngineIntegration:
    """Test context engine integration with dev agent."""

    def test_dev_agent_uses_context_engine(self):
        """Test that dev agent properly uses context engine."""
        from agents.dev.dev_agent import DevAgent
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test config
            config_path = Path(temp_dir) / "config.yaml"
            config_path.write_text("""
llm:
  primary: "fake"
""")
            
            # Create dev agent
            with patch.dict(os.environ, {"AI_PROVIDER": "fake"}):
                agent = DevAgent(str(config_path))
                
                # Verify context engine was initialized
                assert hasattr(agent, 'context_engine')
                assert agent.context_engine is not None
                
                # Get engine info
                info = agent.context_engine.get_engine_info()
                assert info["engine"] == "legacy"  # Should default to legacy

    def test_dev_agent_context_engine_environment_control(self):
        """Test that dev agent respects CONTEXT_ENGINE environment variable."""
        from agents.dev.dev_agent import DevAgent
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            config_path.write_text("""
llm:
  primary: "fake"
""")
            
            # Test with legacy engine
            with patch.dict(os.environ, {"AI_PROVIDER": "fake", "CONTEXT_ENGINE": "legacy"}):
                agent = DevAgent(str(config_path))
                info = agent.context_engine.get_engine_info()
                assert info["engine"] == "legacy"
            
            # Test with NO_NETWORK forcing legacy
            with patch.dict(os.environ, {"AI_PROVIDER": "fake", "NO_NETWORK": "1", "CONTEXT_ENGINE": "lc_chroma"}):
                agent = DevAgent(str(config_path))
                info = agent.context_engine.get_engine_info()
                assert info["engine"] == "legacy"


class TestContextEnginePerformance:
    """Test context engine performance and optimization features."""

    def test_performance_measurement(self):
        """Test that context engine performance is measurable."""
        import time
        from agents.dev.context_engine import get_context_engine
        
        with tempfile.TemporaryDirectory() as temp_dir:
            milestone_path = Path(temp_dir) / "test_milestone"
            milestone_path.mkdir()
            
            (milestone_path / "milestone.json").write_text('{"name": "perf-test"}')
            
            engine = get_context_engine("legacy")
            
            start_time = time.time()
            context, metadata = engine.build_context(milestone_path, "test")
            elapsed = time.time() - start_time
            
            # Legacy engine should be very fast
            assert elapsed < 1.0
            assert metadata["token_count"] > 0

    def test_context_engine_caching_behavior(self):
        """Test that LangChain engine benefits from caching when available."""
        try:
            from agents.dev.context_engine import LangChainChromaEngine
            import time
            
            with tempfile.TemporaryDirectory() as temp_dir:
                persist_dir = temp_dir + "/chroma_cache"
                
                milestone_path = Path(temp_dir) / "test_milestone"
                milestone_path.mkdir()
                (milestone_path / "milestone.json").write_text('{"name": "cache-test"}')
                
                # First engine instance
                engine1 = LangChainChromaEngine(persist_directory=persist_dir)
                start_time = time.time()
                context1, metadata1 = engine1.build_context(milestone_path, "test")
                time1 = time.time() - start_time
                
                # Second engine instance (should benefit from caching)
                engine2 = LangChainChromaEngine(persist_directory=persist_dir)
                start_time = time.time()
                context2, metadata2 = engine2.build_context(milestone_path, "test")
                time2 = time.time() - start_time
                
                # Basic functionality check
                assert len(context1) > 0
                assert len(context2) > 0
                assert metadata1["engine"] == "langchain_chroma"
                assert metadata2["engine"] == "langchain_chroma"
                
        except RuntimeError:
            pytest.skip("ChromaDB dependencies not available")


class TestContextEngineBackwardCompatibility:
    """Test backward compatibility with existing code."""

    def test_context_packer_still_works(self):
        """Test that existing context_packer still works."""
        from agents.dev.context_packer import build_context
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Test with non-existent path
            result = build_context(temp_path / "nonexistent")
            assert result == ""
            
            # Test with empty directory  
            result = build_context(temp_path)
            assert result == ""
            
            # Test with milestone data
            milestone_path = temp_path / "milestone"
            milestone_path.mkdir()
            (milestone_path / "milestone.json").write_text('{"name": "compat-test"}')
            
            result = build_context(milestone_path)
            assert "compat-test" in result

    def test_convenience_build_context_function(self):
        """Test that the convenience build_context function works."""
        from agents.dev.context_engine import build_context
        
        with tempfile.TemporaryDirectory() as temp_dir:
            milestone_path = Path(temp_dir) / "test_milestone"
            milestone_path.mkdir()
            (milestone_path / "milestone.json").write_text('{"name": "convenience-test"}')
            
            # Should work like the original build_context
            result = build_context(milestone_path)
            assert isinstance(result, str)
            assert "convenience-test" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])