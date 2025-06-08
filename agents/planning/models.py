"""
Pydantic models for planning agent data validation.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class Task(BaseModel):
    """Individual task within a milestone."""
    name: str = Field(..., description="Task name")
    description: str = Field(..., description="Detailed task description")
    estimated_hours: Optional[int] = Field(None, description="Estimated hours to complete")
    dependencies: List[str] = Field(default_factory=list, description="Task dependencies")


class Milestone(BaseModel):
    """Project milestone containing multiple tasks."""
    name: str = Field(..., description="Milestone name")
    description: str = Field(..., description="Milestone description")
    estimated_duration: Optional[str] = Field(None, description="Estimated duration (e.g., '2 weeks')")
    tasks: List[Task] = Field(..., description="List of tasks in this milestone")


class PlanningOutput(BaseModel):
    """Complete planning output schema."""
    project_title: str = Field(..., description="Project title")
    project_summary: str = Field(..., description="Brief project summary")
    milestones: List[Milestone] = Field(..., description="Project milestones (≤5)", max_length=5)
    tech_stack: List[str] = Field(..., description="Recommended technology stack")
    open_questions: List[str] = Field(default_factory=list, description="Questions needing clarification")
    estimated_total_duration: Optional[str] = Field(None, description="Total project duration estimate")
    
    class Config:
        json_schema_extra = {
            "example": {
                "project_title": "E-Commerce Platform",
                "project_summary": "Modern e-commerce platform with user management and secure payments",
                "milestones": [
                    {
                        "name": "Foundation Setup",
                        "description": "Basic project setup and authentication",
                        "estimated_duration": "2 weeks",
                        "tasks": [
                            {
                                "name": "Project scaffolding",
                                "description": "Initialize Next.js project with TypeScript",
                                "estimated_hours": 8,
                                "dependencies": []
                            }
                        ]
                    }
                ],
                "tech_stack": ["Next.js", "TypeScript", "Supabase", "Stripe"],
                "open_questions": ["What payment methods should be supported?"],
                "estimated_total_duration": "8-10 weeks"
            }
        }