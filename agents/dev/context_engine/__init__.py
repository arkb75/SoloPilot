"""
Context Engine Factory for SoloPilot Dev Agent

Provides unified interface for context building with multiple backends:
- Legacy: Simple context_packer (fast, reliable)
- LangChain + Chroma: Advanced vector-based context with similarity search

Environment control:
- CONTEXT_ENGINE=legacy (default for stability)
- CONTEXT_ENGINE=lc_chroma (advanced features)
- NO_NETWORK=1 forces legacy mode for offline/CI
"""

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Tuple


class BaseContextEngine(ABC):
    """Abstract base class for context engines."""
    
    @abstractmethod
    def build_context(self, milestone_path: Path, prompt: str = "") -> Tuple[str, Dict[str, Any]]:
        """
        Build context for the given milestone and prompt.
        
        Args:
            milestone_path: Path to milestone directory
            prompt: Optional prompt for context enhancement
            
        Returns:
            Tuple of (context_string, metadata_dict)
        """
        pass
    
    @abstractmethod
    def get_engine_info(self) -> Dict[str, Any]:
        """Get information about this context engine."""
        pass


class LegacyContextEngine(BaseContextEngine):
    """Wrapper for legacy context_packer for backward compatibility."""
    
    def build_context(self, milestone_path: Path, prompt: str = "") -> Tuple[str, Dict[str, Any]]:
        """Build context using legacy context_packer."""
        from agents.dev.context_packer import build_context
        
        context = build_context(milestone_path)
        # Add prompt if provided
        if prompt.strip():
            context = context + "\n\n" + prompt if context.strip() else prompt
            
        metadata = {
            "engine": "legacy_context_packer",
            "milestone_path": str(milestone_path),
            "token_count": len(context) // 4,  # Simple heuristic
            "context_length": len(context)
        }
        
        return context, metadata
    
    def get_engine_info(self) -> Dict[str, Any]:
        """Get legacy engine information."""
        return {
            "engine": "legacy",
            "description": "Fast, reliable context packer",
            "features": ["milestone_json", "package_manifests", "design_guidelines"],
            "performance": "high",
            "offline": True
        }


class LangChainChromaEngine(BaseContextEngine):
    """LangChain + ChromaDB context engine with vector similarity search."""
    
    def __init__(self, persist_directory: str = None):
        """Initialize LangChain + Chroma engine."""
        self._persist_directory = persist_directory
        self._engine = None
        
    def _get_engine(self):
        """Lazy-load the experimental context engine."""
        if self._engine is None:
            try:
                from agents.dev.context_engine.experimental import ContextEngine
                self._engine = ContextEngine(persist_directory=self._persist_directory)
            except ImportError as e:
                raise RuntimeError(f"LangChain/ChromaDB dependencies not available: {e}")
        return self._engine
    
    def build_context(self, milestone_path: Path, prompt: str = "") -> Tuple[str, Dict[str, Any]]:
        """Build enhanced context using LangChain + ChromaDB."""
        engine = self._get_engine()
        return engine.build_enhanced_context(milestone_path, prompt)
    
    def get_engine_info(self) -> Dict[str, Any]:
        """Get LangChain + Chroma engine information."""
        try:
            engine = self._get_engine()
            stats = engine.get_context_stats()
            return {
                "engine": "langchain_chroma",
                "description": "Advanced vector-based context with similarity search",
                "features": ["vector_similarity", "context_persistence", "llm_templates"],
                "performance": "medium",
                "offline": False,
                "stats": stats
            }
        except Exception as e:
            return {
                "engine": "langchain_chroma",
                "error": str(e),
                "offline": False
            }


def get_context_engine(engine_type: str = None, **kwargs) -> BaseContextEngine:
    """
    Factory function to create appropriate context engine.
    
    Args:
        engine_type: Type of engine ("legacy" or "lc_chroma")
        **kwargs: Additional arguments for engine initialization
        
    Returns:
        BaseContextEngine instance
        
    Environment Variables:
        CONTEXT_ENGINE: Override engine type (legacy|lc_chroma)
        NO_NETWORK: Force legacy mode when set to "1"
    """
    # Determine engine type from environment or parameter
    if engine_type is None:
        engine_type = os.getenv("CONTEXT_ENGINE", "legacy")
    
    # Force legacy mode for offline/CI environments
    if os.getenv("NO_NETWORK") == "1":
        print("🔧 NO_NETWORK detected, forcing legacy context engine")
        engine_type = "legacy"
    
    # Create appropriate engine
    if engine_type == "lc_chroma":
        try:
            return LangChainChromaEngine(**kwargs)
        except RuntimeError as e:
            print(f"⚠️  Failed to initialize LangChain engine: {e}")
            print("🔧 Falling back to legacy context engine")
            return LegacyContextEngine()
    elif engine_type == "legacy":
        return LegacyContextEngine()
    else:
        raise ValueError(f"Unknown context engine type: {engine_type}")


# Convenience function for backward compatibility
def build_context(milestone_path: Path, prompt: str = "") -> str:
    """
    Build context using the configured context engine.
    
    This function maintains backward compatibility with the original
    context_packer interface while routing through the new factory.
    
    Args:
        milestone_path: Path to milestone directory
        prompt: Optional prompt for context enhancement
        
    Returns:
        Context string
    """
    engine = get_context_engine()
    context, _ = engine.build_context(milestone_path, prompt)
    return context