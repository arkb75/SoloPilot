"""
SoloPilot Planning Agent Module

This module provides the core functionality for converting requirement specifications
into structured project plans with milestones, tech stack recommendations, and
open questions for clarification.
"""

from .planner import ProjectPlanner, PlanningOutput

__version__ = "0.1.0"
__all__ = ["ProjectPlanner", "PlanningOutput"]