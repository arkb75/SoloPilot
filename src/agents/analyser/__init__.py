"""
SoloPilot Requirement Analyser Module

This module provides the core functionality for parsing and analyzing
client requirements from text and image inputs, converting them into
structured JSON specifications for downstream planning and development agents.
"""

from .parser import ImageParser, SpecBuilder, TextParser

__version__ = "0.1.0"
__all__ = ["TextParser", "ImageParser", "SpecBuilder"]
