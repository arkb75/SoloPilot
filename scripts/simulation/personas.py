"""Client persona definitions for simulation."""

import random
from dataclasses import dataclass, field
from typing import Literal, Optional


@dataclass
class ClientPersona:
    """Represents a simulated client's characteristics."""

    name: str
    company: str
    role: str
    industry: str
    communication_style: Literal["formal", "casual", "terse", "verbose"]
    technical_level: Literal["non-technical", "somewhat-technical", "technical"]
    decision_speed: Literal["fast", "medium", "slow"]
    budget_flexibility: Literal["rigid", "flexible", "open"]
    email: str = field(default="")

    def __post_init__(self):
        if not self.email:
            # Generate email from name and company
            first_name = self.name.split()[0].lower()
            company_domain = self.company.lower().replace(" ", "").replace(",", "")[:15]
            self.email = f"{first_name}@{company_domain}.com"


# Pre-defined persona templates
PERSONA_TEMPLATES = {
    "startup_founder": {
        "roles": ["CEO", "Founder", "Co-Founder", "CTO"],
        "industries": ["SaaS", "Fintech", "E-commerce", "HealthTech", "EdTech"],
        "communication_style": "casual",
        "technical_level": "somewhat-technical",
        "decision_speed": "fast",
        "budget_flexibility": "flexible",
    },
    "enterprise_manager": {
        "roles": ["IT Director", "Product Manager", "VP of Engineering", "Program Manager"],
        "industries": ["Finance", "Healthcare", "Manufacturing", "Retail", "Insurance"],
        "communication_style": "formal",
        "technical_level": "somewhat-technical",
        "decision_speed": "slow",
        "budget_flexibility": "rigid",
    },
    "small_business_owner": {
        "roles": ["Owner", "Founder", "Managing Director"],
        "industries": ["Restaurant", "Bakery", "Consulting", "Real Estate", "Fitness"],
        "communication_style": "casual",
        "technical_level": "non-technical",
        "decision_speed": "medium",
        "budget_flexibility": "rigid",
    },
    "agency_client": {
        "roles": ["Marketing Director", "Creative Director", "Brand Manager"],
        "industries": ["Marketing Agency", "Design Studio", "Media Company"],
        "communication_style": "verbose",
        "technical_level": "non-technical",
        "decision_speed": "medium",
        "budget_flexibility": "flexible",
    },
    "technical_lead": {
        "roles": ["Tech Lead", "Senior Developer", "Architect", "Engineering Manager"],
        "industries": ["Software", "Technology", "Cloud Services", "DevOps"],
        "communication_style": "terse",
        "technical_level": "technical",
        "decision_speed": "fast",
        "budget_flexibility": "open",
    },
}

# Name pools
FIRST_NAMES = [
    "Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Quinn", "Avery",
    "Jamie", "Drew", "Cameron", "Reese", "Parker", "Sage", "Blake", "Hayden",
    "Sarah", "Michael", "Jennifer", "David", "Emily", "James", "Jessica", "Robert",
    "Amanda", "John", "Ashley", "William", "Stephanie", "Christopher",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Anderson", "Taylor", "Thomas", "Moore", "Jackson",
    "White", "Harris", "Martin", "Thompson", "Young", "Chen", "Patel", "Kim",
    "Nguyen", "Singh", "Kumar", "Shah", "Lee", "Park", "Wong",
]

COMPANY_TEMPLATES = {
    "SaaS": ["{name}Labs", "{name}Cloud", "{name}HQ", "{name}io", "Smart{name}"],
    "Fintech": ["{name}Pay", "{name}Wallet", "{name}Finance", "{name}Capital"],
    "E-commerce": ["{name}Shop", "{name}Market", "Buy{name}", "{name}Store"],
    "HealthTech": ["{name}Health", "{name}Med", "Heal{name}", "{name}Care"],
    "EdTech": ["{name}Learn", "{name}Academy", "Edu{name}", "{name}School"],
    "Restaurant": ["{name}'s Kitchen", "The {name} Grill", "{name} Bistro", "Cafe {name}"],
    "Bakery": ["{name}'s Bakery", "Sweet {name}", "{name} Bakes", "The {name} Patisserie"],
    "Consulting": ["{name} Consulting", "{name} & Associates", "{name} Advisory"],
    "Real Estate": ["{name} Realty", "{name} Properties", "{name} Homes"],
    "default": ["{name} Inc", "{name} Co", "{name} Group", "{name} Solutions"],
}

COMPANY_NAME_WORDS = [
    "Nova", "Apex", "Prime", "Stellar", "Quantum", "Vertex", "Nexus", "Atlas",
    "Zenith", "Summit", "Horizon", "Pulse", "Spark", "Swift", "Bold", "Clear",
]


def generate_persona(
    template: Optional[str] = None,
    name: Optional[str] = None,
    company: Optional[str] = None,
    **overrides,
) -> ClientPersona:
    """Generate a client persona, optionally based on a template.
    
    Args:
        template: Persona template name (startup_founder, enterprise_manager, etc.)
        name: Override the generated name
        company: Override the generated company name
        **overrides: Any other persona attributes to override
    
    Returns:
        Generated ClientPersona
    """
    # Select template
    if template and template in PERSONA_TEMPLATES:
        base = PERSONA_TEMPLATES[template]
    else:
        base = random.choice(list(PERSONA_TEMPLATES.values()))

    # Generate name if not provided
    if not name:
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

    # Select industry and role
    industry = overrides.pop("industry", random.choice(base["industries"]))
    role = overrides.pop("role", random.choice(base["roles"]))

    # Generate company name if not provided
    if not company:
        templates = COMPANY_TEMPLATES.get(industry, COMPANY_TEMPLATES["default"])
        company_word = random.choice(COMPANY_NAME_WORDS)
        company = random.choice(templates).format(name=company_word)

    return ClientPersona(
        name=name,
        company=company,
        role=role,
        industry=industry,
        communication_style=overrides.pop("communication_style", base["communication_style"]),
        technical_level=overrides.pop("technical_level", base["technical_level"]),
        decision_speed=overrides.pop("decision_speed", base["decision_speed"]),
        budget_flexibility=overrides.pop("budget_flexibility", base["budget_flexibility"]),
        **overrides,
    )
