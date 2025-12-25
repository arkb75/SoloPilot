"""
Proposal Data Mapper

This module maps requirement extractor output to the PDF generator input format.
Single responsibility: Transform requirements into proposal data structure.
"""

import logging
import os
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
            "executiveSummaryParagraphs": self._map_executive_summary(requirements),
            "scope": self._map_scope_items(requirements),
            "timeline": self._map_timeline_phases(requirements),
            "pricing": self._map_pricing_breakdown(requirements),
            "techStackIntro": self._map_tech_stack_intro(requirements),
            "techStack": self._map_tech_stack(requirements),
            "nextSteps": self._map_next_steps(requirements),
            "successMetrics": self._map_success_metrics(requirements),
            "freelancerName": self._get_freelancer_name(requirements),
            "validityNote": self._map_validity_note(requirements),
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
        logger.info(
            "  executiveSummaryParagraphs: %d",
            len(proposal_data["executiveSummaryParagraphs"]),
        )
        logger.info("  nextSteps: %d", len(proposal_data["nextSteps"]))
        logger.info("  successMetrics: %d", len(proposal_data["successMetrics"]))
        logger.info("=" * 80)
        
        return proposal_data

    def _coerce_string_list(self, value: Any) -> List[str]:
        """Normalize string or list inputs into a clean list of strings."""
        if isinstance(value, str):
            return [line.strip() for line in value.splitlines() if line.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return []

    def _map_executive_summary(self, requirements: Dict[str, Any]) -> List[str]:
        """Map executive summary paragraphs from requirements."""
        raw = (
            requirements.get("executive_summary")
            or requirements.get("executive_summary_paragraphs")
            or requirements.get("executiveSummary")
        )
        paragraphs = self._coerce_string_list(raw)
        if paragraphs:
            return paragraphs

        summary = str(requirements.get("summary") or "").strip()
        business_desc = str(requirements.get("business_description") or "").strip()
        derived: List[str] = []
        if summary:
            derived.append(summary)
        if business_desc and business_desc != summary:
            derived.append(business_desc)
        return derived

    def _map_next_steps(self, requirements: Dict[str, Any]) -> List[str]:
        """Map next steps from requirements or existing scope/timeline data."""
        raw = requirements.get("next_steps") or requirements.get("nextSteps")
        steps = self._coerce_string_list(raw)
        if steps:
            return steps[:6]

        scope_items = requirements.get("scope_items", []) or []
        derived = [
            str(item.get("title", "")).strip()
            for item in scope_items
            if str(item.get("title", "")).strip()
        ]
        if derived:
            return derived[:6]

        timeline_phases = requirements.get("timeline_phases", []) or []
        derived = [
            str(phase.get("phase", "")).strip()
            for phase in timeline_phases
            if str(phase.get("phase", "")).strip()
        ]
        return derived[:6]

    def _map_success_metrics(self, requirements: Dict[str, Any]) -> List[str]:
        """Map success metrics from requirements or derived feature names."""
        raw = requirements.get("success_metrics") or requirements.get("successMetrics")
        metrics = self._coerce_string_list(raw)
        if metrics:
            return metrics[:6]

        features = requirements.get("features", []) or []
        derived = [
            str(feature.get("name", "")).strip()
            for feature in features
            if str(feature.get("name", "")).strip()
        ]
        if derived:
            return derived[:6]

        constraints = requirements.get("constraints", []) or []
        derived = self._coerce_string_list(constraints)
        return derived[:6]

    def _map_tech_stack_intro(self, requirements: Dict[str, Any]) -> str:
        """Return optional tech stack intro text from requirements."""
        intro = requirements.get("tech_stack_overview") or requirements.get("tech_stack_intro")
        return str(intro).strip() if intro else ""

    def _get_freelancer_name(self, requirements: Dict[str, Any]) -> str:
        """Return freelancer display name for signature."""
        name = requirements.get("freelancer_name") or requirements.get("freelancerName")
        if name:
            return str(name).strip()
        return os.environ.get("PROPOSAL_FREELANCER_NAME", "").strip()

    def _map_validity_note(self, requirements: Dict[str, Any]) -> str:
        """Return the proposal validity note from requirements or environment."""
        note = requirements.get("validity_note") or requirements.get("validityNote")
        if note:
            return str(note).strip()
        return os.environ.get("PROPOSAL_VALIDITY_NOTE", "").strip()
    
    def _get_project_title(self, requirements: Dict[str, Any]) -> str:
        """Determine project title based on requirements."""
        title = requirements.get("title", "")
        project_type = requirements.get("project_type", "")
        
        # Use provided title verbatim when present
        if title and len(title) > 3:
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
