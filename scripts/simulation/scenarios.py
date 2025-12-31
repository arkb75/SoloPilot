"""Scenario definitions for client simulation."""

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from .personas import ClientPersona, generate_persona


class ScenarioPreset(str, Enum):
    """Pre-defined scenario types."""

    SIMPLE = "simple"
    BUDGET_CONSCIOUS = "budget_conscious"
    COMPLEX = "complex"
    VAGUE = "vague"
    RUSH = "rush"
    ENTERPRISE = "enterprise"
    SCOPE_CREEP = "scope_creep"
    COMPARISON_SHOPPER = "comparison_shopper"


@dataclass
class Scenario:
    """Represents a simulation scenario."""

    preset: ScenarioPreset
    persona: ClientPersona
    project_type: str
    project_description: str
    budget_min: int
    budget_max: int
    timeline: str
    features: List[str]
    behavior_modifiers: Dict[str, Any] = field(default_factory=dict)
    expected_turns: int = 5
    success_criteria: str = "proposal_accepted"

    @property
    def budget_range_str(self) -> str:
        return f"${self.budget_min:,} - ${self.budget_max:,}"


# Scenario preset definitions
SCENARIO_CONFIGS = {
    ScenarioPreset.SIMPLE: {
        "description": "Clear requirements, reasonable budget, straightforward project",
        "persona_template": "small_business_owner",
        "project_types": ["website", "landing_page", "portfolio"],
        "budget_range": (3000, 8000),
        "timeline_options": ["4-6 weeks", "2 months", "6-8 weeks"],
        "feature_count": (2, 4),
        "expected_turns": (3, 5),
        "behavior_modifiers": {
            "clarity": "high",
            "responsiveness": "good",
            "objections": "few",
        },
    },
    ScenarioPreset.BUDGET_CONSCIOUS: {
        "description": "Price-sensitive client, may negotiate or reduce scope",
        "persona_template": "small_business_owner",
        "project_types": ["website", "e-commerce", "web_app"],
        "budget_range": (2000, 5000),
        "timeline_options": ["1-2 months", "6 weeks", "2 months"],
        "feature_count": (3, 6),
        "expected_turns": (4, 7),
        "behavior_modifiers": {
            "clarity": "medium",
            "responsiveness": "good",
            "objections": "price_focused",
            "negotiation_style": "persistent",
            "may_reduce_scope": True,
        },
    },
    ScenarioPreset.COMPLEX: {
        "description": "Enterprise-level project with many features and integrations",
        "persona_template": "enterprise_manager",
        "project_types": ["platform", "saas", "enterprise_app", "dashboard"],
        "budget_range": (25000, 75000),
        "timeline_options": ["3-4 months", "4-6 months", "6 months"],
        "feature_count": (6, 10),
        "expected_turns": (5, 10),
        "behavior_modifiers": {
            "clarity": "high",
            "responsiveness": "slow",
            "objections": "technical",
            "requires_documentation": True,
            "stakeholder_approval": True,
        },
    },
    ScenarioPreset.VAGUE: {
        "description": "Unclear requirements, needs many clarifying questions",
        "persona_template": "agency_client",
        "project_types": ["website", "app", "platform", "tool"],
        "budget_range": (5000, 20000),
        "timeline_options": ["ASAP", "soon", "a few months"],
        "feature_count": (1, 3),
        "expected_turns": (6, 10),
        "behavior_modifiers": {
            "clarity": "low",
            "responsiveness": "variable",
            "objections": "few",
            "vague_responses": True,
            "changes_mind": True,
        },
    },
    ScenarioPreset.RUSH: {
        "description": "Urgent timeline, willing to pay premium",
        "persona_template": "startup_founder",
        "project_types": ["mvp", "landing_page", "prototype", "demo"],
        "budget_range": (8000, 20000),
        "timeline_options": ["2 weeks", "3 weeks", "1 month", "ASAP"],
        "feature_count": (3, 5),
        "expected_turns": (3, 5),
        "behavior_modifiers": {
            "clarity": "medium",
            "responsiveness": "immediate",
            "objections": "timeline_focused",
            "urgency": "high",
            "willing_to_pay_premium": True,
        },
    },
    ScenarioPreset.ENTERPRISE: {
        "description": "Corporate client with formal processes and compliance needs",
        "persona_template": "enterprise_manager",
        "project_types": ["internal_tool", "portal", "dashboard", "integration"],
        "budget_range": (50000, 150000),
        "timeline_options": ["4-6 months", "6 months", "Q2", "Q3"],
        "feature_count": (5, 8),
        "expected_turns": (6, 12),
        "behavior_modifiers": {
            "clarity": "high",
            "responsiveness": "slow",
            "objections": "compliance",
            "formal_tone": True,
            "requires_sow": True,
            "procurement_process": True,
            "security_review": True,
        },
    },
    ScenarioPreset.SCOPE_CREEP: {
        "description": "Client who keeps adding features throughout conversation",
        "persona_template": "startup_founder",
        "project_types": ["web_app", "platform", "saas", "marketplace"],
        "budget_range": (10000, 30000),
        "timeline_options": ["2-3 months", "3 months", "2 months"],
        "feature_count": (4, 6),
        "expected_turns": (5, 8),
        "behavior_modifiers": {
            "clarity": "medium",
            "responsiveness": "good",
            "objections": "few",
            "adds_features": True,
            "feature_addition_rate": "each_turn",
            "initially_understates_scope": True,
        },
    },
    ScenarioPreset.COMPARISON_SHOPPER: {
        "description": "Getting quotes from multiple vendors, may mention competitors",
        "persona_template": "agency_client",
        "project_types": ["website", "e-commerce", "web_app", "redesign"],
        "budget_range": (8000, 25000),
        "timeline_options": ["2-3 months", "3 months", "flexible"],
        "feature_count": (4, 7),
        "expected_turns": (4, 7),
        "behavior_modifiers": {
            "clarity": "high",
            "responsiveness": "medium",
            "objections": "comparison",
            "mentions_competitors": True,
            "asks_for_references": True,
            "price_comparison": True,
        },
    },
}

# Feature pools by project type
FEATURE_POOLS = {
    "website": [
        "responsive design", "contact form", "blog", "portfolio gallery",
        "SEO optimization", "social media integration", "newsletter signup",
        "about page", "services page", "testimonials section",
    ],
    "landing_page": [
        "hero section", "call-to-action", "testimonials", "pricing table",
        "email capture", "video embed", "feature highlights", "FAQ section",
    ],
    "e-commerce": [
        "product catalog", "shopping cart", "checkout flow", "payment integration",
        "inventory management", "order tracking", "customer accounts", "wishlist",
        "product search", "category filtering", "reviews and ratings", "discount codes",
    ],
    "web_app": [
        "user authentication", "dashboard", "data visualization", "notifications",
        "user settings", "admin panel", "file uploads", "search functionality",
        "API integration", "export/import", "multi-tenancy", "audit logs",
    ],
    "platform": [
        "user management", "role-based access", "API", "webhooks",
        "analytics dashboard", "billing integration", "white-labeling",
        "multi-tenant architecture", "SSO integration", "audit trail",
    ],
    "saas": [
        "subscription billing", "user onboarding", "team management",
        "usage analytics", "integrations marketplace", "API access",
        "custom domains", "email notifications", "two-factor auth",
    ],
    "mvp": [
        "core feature 1", "core feature 2", "user auth", "basic dashboard",
        "data input forms", "simple reporting",
    ],
    "default": [
        "user authentication", "responsive design", "admin panel",
        "contact form", "data management", "reporting",
    ],
}


def load_scenario(
    preset: ScenarioPreset,
    persona: Optional[ClientPersona] = None,
    budget_override: Optional[tuple] = None,
    timeline_override: Optional[str] = None,
    **overrides,
) -> Scenario:
    """Load and configure a scenario from a preset.
    
    Args:
        preset: The scenario preset to use
        persona: Optional pre-configured persona (will generate one if not provided)
        budget_override: Optional (min, max) budget tuple
        timeline_override: Optional timeline string
        **overrides: Any other scenario attributes to override
    
    Returns:
        Configured Scenario instance
    """
    config = SCENARIO_CONFIGS[preset]

    # Generate or use provided persona
    if persona is None:
        persona = generate_persona(template=config["persona_template"])

    # Select project type
    project_type = overrides.pop("project_type", random.choice(config["project_types"]))

    # Generate features
    feature_pool = FEATURE_POOLS.get(project_type, FEATURE_POOLS["default"])
    feature_count = random.randint(*config["feature_count"])
    features = random.sample(feature_pool, min(feature_count, len(feature_pool)))

    # Set budget
    if budget_override:
        budget_min, budget_max = budget_override
    else:
        budget_min, budget_max = config["budget_range"]

    # Set timeline
    timeline = timeline_override or random.choice(config["timeline_options"])

    # Set expected turns
    expected_turns = random.randint(*config["expected_turns"])

    # Generate project description based on type and persona
    project_description = _generate_project_description(
        project_type, persona.industry, features[:3]
    )

    return Scenario(
        preset=preset,
        persona=persona,
        project_type=project_type,
        project_description=project_description,
        budget_min=budget_min,
        budget_max=budget_max,
        timeline=timeline,
        features=features,
        behavior_modifiers=config["behavior_modifiers"],
        expected_turns=expected_turns,
        **overrides,
    )


def _generate_project_description(
    project_type: str, industry: str, key_features: List[str]
) -> str:
    """Generate a natural project description."""
    templates = [
        f"We need a {project_type} for our {industry.lower()} business",
        f"Looking to build a {project_type} to support our {industry.lower()} operations",
        f"We're a {industry.lower()} company looking for a custom {project_type}",
        f"Need help developing a {project_type} for our {industry.lower()} startup",
    ]
    
    base = random.choice(templates)
    
    if key_features:
        features_str = ", ".join(key_features[:2])
        if len(key_features) > 2:
            features_str += f", and {key_features[2]}"
        base += f". Key features include {features_str}."
    
    return base


def get_all_presets() -> List[ScenarioPreset]:
    """Get all available scenario presets."""
    return list(ScenarioPreset)


def get_preset_description(preset: ScenarioPreset) -> str:
    """Get the description for a scenario preset."""
    return SCENARIO_CONFIGS[preset]["description"]
