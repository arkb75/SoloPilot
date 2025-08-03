"""
Proposal Data Mapper

This module maps requirement extractor output to the PDF generator input format.
Single responsibility: Transform requirements into proposal data structure.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any

logger = logging.getLogger(__name__)


class ProposalDataMapper:
    """Maps requirements from RequirementExtractor to PDF proposal data format."""
    
    def map_requirements_to_proposal_data(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform requirements into proposal data structure for PDF generation.
        
        Args:
            requirements: Output from RequirementExtractor with all fields
            
        Returns:
            Dict with proposal data in PDF generator format
        """
        # Start with required fields, using safe defaults
        proposal_data = {
            "clientName": requirements.get("client_name", "Client"),
            "projectTitle": self._get_project_title(requirements),
            "proposalDate": datetime.now().strftime("%B %Y"),
            "scope": self._map_scope_items(requirements),
            "timeline": self._map_timeline_phases(requirements),
            "pricing": self._map_pricing_breakdown(requirements),
            "techStack": self._map_tech_stack(requirements),
        }
        
        # Log the mapping for debugging
        logger.info("=" * 80)
        logger.info("PROPOSAL MAPPER - Mapped proposal data:")
        logger.info(f"  clientName: {proposal_data['clientName']} (from requirements.client_name)")
        logger.info(f"  projectTitle: {proposal_data['projectTitle']}")
        logger.info(f"  scope: {len(proposal_data['scope'])} items")
        logger.info(f"  timeline: {len(proposal_data['timeline'])} phases")
        logger.info(f"  pricing: {len(proposal_data['pricing'])} items")
        logger.info(f"  techStack: {len(proposal_data['techStack'])} technologies")
        logger.info("=" * 80)
        
        return proposal_data
    
    def _get_project_title(self, requirements: Dict[str, Any]) -> str:
        """Determine project title based on requirements."""
        title = requirements.get("title", "")
        project_type = requirements.get("project_type", "")
        
        # Use title if it's descriptive enough
        if title and len(title) > 3:
            # Clean up common patterns
            if "dashboard" in title.lower():
                if "shopify" in title.lower():
                    return "Shopify Dashboard"
                else:
                    return "Internal Dashboard"
            return title
        
        # Fallback to project type
        if project_type == "web_app":
            return "Web Application Project"
        elif project_type == "website":
            return "Website Development"
        elif project_type == "mobile_app":
            return "Mobile Application"
        
        return "Web Development Project"
    
    def _map_scope_items(self, requirements: Dict[str, Any]) -> List[Dict[str, str]]:
        """Map scope items from requirements or generate defaults."""
        scope_items = requirements.get("scope_items", [])
        
        # If we have scope items from requirements, use them
        if scope_items and len(scope_items) >= 2:
            return [
                {
                    "title": item.get("title", ""),
                    "description": item.get("description", "")
                }
                for item in scope_items
                if item.get("title")  # Skip empty items
            ]
        
        # Fallback: Generate scope based on features
        features = requirements.get("features", [])
        if features:
            # Convert features to scope items
            scope = []
            
            # Always start with discovery/planning
            scope.append({
                "title": "Discovery & Planning",
                "description": "Understand requirements and create technical specification"
            })
            
            # Add main feature as development scope
            if features:
                main_feature = features[0]
                scope.append({
                    "title": main_feature.get("name", "Core Development"),
                    "description": main_feature.get("desc", "Build the main functionality")
                })
            
            # Add testing/launch
            scope.append({
                "title": "Testing & Launch",
                "description": "Ensure quality and deploy to production"
            })
            
            return scope
        
        # Ultimate fallback
        return [
            {
                "title": "Discovery & Planning",
                "description": "Understand requirements and create technical specification"
            },
            {
                "title": "Development",
                "description": "Build the solution with modern web technologies"
            },
            {
                "title": "Testing & Launch",
                "description": "Ensure quality and deploy to production"
            }
        ]
    
    def _map_timeline_phases(self, requirements: Dict[str, Any]) -> List[Dict[str, str]]:
        """Map timeline phases from requirements or generate defaults."""
        timeline_phases = requirements.get("timeline_phases", [])
        
        # If we have timeline phases, use them
        if timeline_phases and len(timeline_phases) >= 3:
            return [
                {
                    "phase": phase.get("phase", ""),
                    "duration": phase.get("duration", "1 week")
                }
                for phase in timeline_phases
                if phase.get("phase")  # Skip empty phases
            ]
        
        # Generate based on timeline urgency
        timeline_str = str(requirements.get("timeline", "")).lower()
        
        if any(urgent in timeline_str for urgent in ["asap", "urgent", "days", "1 week", "10 days"]):
            # Fast timeline
            return [
                {"phase": "Discovery", "duration": "3 days"},
                {"phase": "Development", "duration": "1 week"},
                {"phase": "Testing", "duration": "2 days"},
                {"phase": "Launch", "duration": "1 day"}
            ]
        else:
            # Standard timeline
            return [
                {"phase": "Discovery", "duration": "1 week"},
                {"phase": "Design", "duration": "1 week"},
                {"phase": "Development", "duration": "3 weeks"},
                {"phase": "Testing", "duration": "1 week"},
                {"phase": "Launch", "duration": "3 days"}
            ]
    
    def _map_pricing_breakdown(self, requirements: Dict[str, Any]) -> List[Dict[str, str]]:
        """Map pricing breakdown from requirements or generate based on budget."""
        pricing_breakdown = requirements.get("pricing_breakdown", [])
        
        # If we have pricing breakdown, format it
        if pricing_breakdown and len(pricing_breakdown) >= 1:
            return [
                {
                    "item": item.get("item", ""),
                    "amount": f"${int(item.get('amount', 0)):,}"
                }
                for item in pricing_breakdown
                if item.get("item") and (item.get("amount") or 0) > 0
            ]
        
        # Generate based on budget_amount
        budget_amount = requirements.get("budget_amount", 0)
        
        # Handle None values explicitly
        if budget_amount is None:
            budget_amount = 0
            
        if budget_amount > 0:
            if budget_amount <= 1000:
                # Simple breakdown for small budgets
                return [
                    {"item": "Complete Project Package", "amount": f"${int(budget_amount):,}"}
                ]
            elif budget_amount <= 5000:
                # Medium budget breakdown
                development = int(budget_amount * 0.7)
                remainder = budget_amount - development
                return [
                    {"item": "Development & Implementation", "amount": f"${development:,}"},
                    {"item": "Testing & Deployment", "amount": f"${remainder:,}"}
                ]
            else:
                # Larger budget - more detailed breakdown
                discovery = int(budget_amount * 0.15)
                design = int(budget_amount * 0.20)
                development = int(budget_amount * 0.50)
                testing = int(budget_amount * 0.10)
                launch = budget_amount - (discovery + design + development + testing)
                
                return [
                    {"item": "Discovery & Research", "amount": f"${discovery:,}"},
                    {"item": "Design & Prototyping", "amount": f"${design:,}"},
                    {"item": "Development", "amount": f"${development:,}"},
                    {"item": "Testing & QA", "amount": f"${testing:,}"},
                    {"item": "Launch Support", "amount": f"${launch:,}"}
                ]
        
        # No budget specified - use generic pricing
        return [
            {"item": "Project Implementation", "amount": "TBD"},
            {"item": "Testing & Deployment", "amount": "TBD"}
        ]
    
    def _map_tech_stack(self, requirements: Dict[str, Any]) -> List[str]:
        """Map tech stack from requirements or use defaults."""
        tech_stack = requirements.get("tech_stack", [])
        
        if tech_stack and len(tech_stack) > 0:
            # Use provided tech stack, limit to 9 items for PDF layout
            return tech_stack[:9]
        
        # Default tech stack based on project type
        project_type = requirements.get("project_type", "")
        
        if project_type == "web_app":
            return ["Next.js", "React", "Node.js", "PostgreSQL", "AWS"]
        elif project_type == "website":
            return ["Next.js", "React", "Tailwind CSS", "Vercel"]
        elif project_type == "mobile_app":
            return ["React Native", "Node.js", "PostgreSQL", "AWS"]
        
        # Generic default
        return ["Next.js", "React", "Node.js", "PostgreSQL", "AWS"]