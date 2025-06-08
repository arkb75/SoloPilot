#!/usr/bin/env python3
"""
Context7 Bridge for SoloPilot Dev Agent
MCP adapter for enhanced development insights using Context7.
"""

import os
import subprocess
import json
from pathlib import Path
from typing import Optional, Dict, Any, List

class Context7Bridge:
    """Bridge to Context7 for enhanced development insights."""
    
    def __init__(self):
        """Initialize Context7 bridge."""
        self.context7_available = self._check_context7_available()
        self.enabled = os.getenv('C7_SCOUT', '0') == '1' and self.context7_available
    
    def _check_context7_available(self) -> bool:
        """Check if Context7 is available globally."""
        try:
            result = subprocess.run(
                ['context7', '--version'], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError):
            return False
    
    def is_enabled(self) -> bool:
        """Check if Context7 scouting is enabled."""
        return self.enabled
    
    def scout_milestone_pitfalls(self, milestone_name: str, description: str, tech_stack: List[str]) -> Optional[str]:
        """
        Use Context7 to scout for common pitfalls when building a specific milestone.
        
        Args:
            milestone_name: Name of the milestone
            description: Description of what the milestone involves
            tech_stack: List of technologies being used
            
        Returns:
            String with insights about common pitfalls, or None if scouting fails
        """
        if not self.enabled:
            return None
        
        question = self._build_pitfall_question(milestone_name, description, tech_stack)
        return self._query_context7(question)
    
    def scout_implementation_patterns(self, milestone_name: str, tech_stack: List[str]) -> Optional[str]:
        """
        Scout for implementation patterns and best practices.
        
        Args:
            milestone_name: Name of the milestone
            tech_stack: List of technologies being used
            
        Returns:
            String with implementation guidance, or None if scouting fails
        """
        if not self.enabled:
            return None
        
        question = f"What are the best implementation patterns and practices when building {milestone_name} using {', '.join(tech_stack)}? Focus on architecture and code organization."
        return self._query_context7(question)
    
    def scout_testing_strategies(self, milestone_name: str, tech_stack: List[str]) -> Optional[str]:
        """
        Scout for testing strategies specific to the milestone.
        
        Args:
            milestone_name: Name of the milestone
            tech_stack: List of technologies being used
            
        Returns:
            String with testing recommendations, or None if scouting fails
        """
        if not self.enabled:
            return None
        
        question = f"What are the most effective testing strategies for {milestone_name} in a {', '.join(tech_stack)} stack? Include unit, integration, and end-to-end testing approaches."
        return self._query_context7(question)
    
    def _build_pitfall_question(self, milestone_name: str, description: str, tech_stack: List[str]) -> str:
        """Build a focused question about pitfalls for the milestone."""
        return f"""Give me the 5 most common pitfalls when building {milestone_name}.

Context:
- Description: {description}
- Tech Stack: {', '.join(tech_stack)}

Focus on practical implementation issues, performance problems, security concerns, and architectural mistakes developers commonly make."""
    
    def _query_context7(self, question: str, search_path: Optional[str] = None) -> Optional[str]:
        """
        Query Context7 with a specific question.
        
        Args:
            question: The question to ask Context7
            search_path: Optional path to search in (defaults to current directory)
            
        Returns:
            Context7 response or None if query fails
        """
        if not self.enabled:
            return None
        
        try:
            cmd = ['context7', 'ask', question]
            if search_path:
                cmd.extend(['--path', str(search_path)])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,  # 30 second timeout
                cwd=search_path or '.'
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                print(f"Context7 query failed: {result.stderr}")
                return None
                
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"Context7 bridge error: {e}")
            return None
    
    def generate_milestone_insights(self, milestone: Dict[str, Any], tech_stack: List[str]) -> Dict[str, Optional[str]]:
        """
        Generate comprehensive insights for a milestone using Context7.
        
        Args:
            milestone: Milestone data with name, description, tasks
            tech_stack: Project tech stack
            
        Returns:
            Dictionary with different types of insights
        """
        if not self.enabled:
            return {
                "pitfalls": None,
                "patterns": None,
                "testing": None,
                "enabled": False
            }
        
        milestone_name = milestone.get('name', 'Unknown Milestone')
        description = milestone.get('description', '')
        
        return {
            "pitfalls": self.scout_milestone_pitfalls(milestone_name, description, tech_stack),
            "patterns": self.scout_implementation_patterns(milestone_name, tech_stack),
            "testing": self.scout_testing_strategies(milestone_name, tech_stack),
            "enabled": True
        }
    
    def format_insights_for_readme(self, insights: Dict[str, Optional[str]]) -> str:
        """
        Format Context7 insights for inclusion in milestone README files.
        
        Args:
            insights: Dictionary of insights from generate_milestone_insights
            
        Returns:
            Formatted markdown content
        """
        if not insights.get("enabled") or not any(insights.values()):
            return ""
        
        sections = []
        
        if insights.get("pitfalls"):
            sections.append(f"""## ⚠️ Common Pitfalls (Context7 Insights)

{insights["pitfalls"]}""")
        
        if insights.get("patterns"):
            sections.append(f"""## 🏗️ Implementation Patterns (Context7 Insights)

{insights["patterns"]}""")
        
        if insights.get("testing"):
            sections.append(f"""## 🧪 Testing Strategies (Context7 Insights)

{insights["testing"]}""")
        
        if sections:
            return "\n\n" + "\n\n".join(sections) + "\n\n---\n*Insights powered by Context7*"
        
        return ""
    
    def install_context7(self) -> bool:
        """
        Attempt to install Context7 globally via npm.
        
        Returns:
            True if installation succeeded, False otherwise
        """
        try:
            print("Installing Context7 globally via npm...")
            result = subprocess.run(
                ['npm', 'install', '-g', 'context7'],
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout for installation
            )
            
            if result.returncode == 0:
                print("✅ Context7 installed successfully")
                self.context7_available = True
                # Re-check if we should enable it
                self.enabled = os.getenv('C7_SCOUT', '0') == '1' and self.context7_available
                return True
            else:
                print(f"❌ Context7 installation failed: {result.stderr}")
                return False
                
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"❌ Context7 installation error: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get status information about the Context7 bridge."""
        return {
            "context7_available": self.context7_available,
            "enabled": self.enabled,
            "env_var_set": os.getenv('C7_SCOUT', '0') == '1',
            "install_command": "npm install -g context7"
        }