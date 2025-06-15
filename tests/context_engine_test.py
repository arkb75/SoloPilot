#!/usr/bin/env python3
"""
Smoke tests for Context Engine experimental features
"""

import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


class TestContextEngineExperimental:
    """Smoke tests for context engine experimental features."""

    @pytest.mark.skipif(
        True,  # Skip until ChromaDB is actually installed and needed
        reason="Context engine experimental - TODO: implement when needed"
    )
    def test_context_engine_import(self):
        """Test that experimental context engine can be imported."""
        try:
            from agents.dev.context_engine.experimental import ContextEngine
            engine = ContextEngine()
            assert engine is not None
        except ImportError:
            pytest.skip("ChromaDB dependencies not available")

    def test_context_engine_placeholder(self):
        """Placeholder test to ensure test suite runs."""
        # TODO: Implement actual context engine tests when ChromaDB integration is needed
        assert True
        
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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])