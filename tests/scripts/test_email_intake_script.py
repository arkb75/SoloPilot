"""Test script for email intake agent."""

import json
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.email_intake import EmailParser, RequirementExtractor

# Mock Apollo.io reply email
MOCK_APOLLO_EMAIL = """From: "Michael Chen" <michael@ecommerce-solutions.com>
To: sales@solopilot.ai
Subject: Re: Automate Your Development Pipeline
Date: Mon, 15 Jan 2024 10:30:00 +0000
Message-ID: <apollo123@ecommerce-solutions.com>
In-Reply-To: <outreach123@solopilot.ai>
References: <outreach123@solopilot.ai>

Hi there,

Your email caught my attention. We're a growing e-commerce company and we're looking to build a new marketplace platform.

Here's what we need:

1. Multi-vendor marketplace where sellers can list products
2. Customer accounts with order history
3. Payment processing (considering Stripe or PayPal)
4. Admin dashboard for managing vendors and orders
5. Mobile-responsive design

We're hoping to launch by Q2 2024 (about 4 months from now). Our budget is flexible but ideally under $30k.

We also need the platform to integrate with our existing inventory system (REST API).

Let me know if you can help with this project.

Best regards,
Michael Chen
CTO, E-Commerce Solutions Ltd.

--
This email was sent from my mobile device
"""


def test_email_parser():
    """Test parsing the mock email."""
    print("Testing Email Parser...")
    print("-" * 50)

    parser = EmailParser()
    result = parser.parse(MOCK_APOLLO_EMAIL)

    print(f"From: {result['from']}")
    print(f"Subject: {result['subject']}")
    print(f"Thread ID: {result['thread_id']}")
    print(f"Is Reply: {result['is_reply']}")
    print("\nBody Preview (first 200 chars):")
    print(result["body"][:200] + "...")
    print()


def test_requirement_extraction():
    """Test extracting requirements from the email."""
    print("Testing Requirement Extraction...")
    print("-" * 50)

    # Set fake provider for testing
    os.environ["AI_PROVIDER"] = "fake"

    parser = EmailParser()
    parsed_email = parser.parse(MOCK_APOLLO_EMAIL)

    extractor = RequirementExtractor()

    # Create email history
    email_history = [
        {
            "from": parsed_email["from"],
            "subject": parsed_email["subject"],
            "body": parsed_email["body"],
            "timestamp": parsed_email["timestamp"],
        }
    ]

    # Extract requirements
    requirements = extractor.extract(email_history, {})

    print("Extracted Requirements:")
    print(json.dumps(requirements, indent=2))
    print()

    # Check completeness
    is_complete = extractor.is_complete(requirements)
    print(f"Requirements Complete: {is_complete}")

    if not is_complete:
        print("\nFollow-up Questions:")
        questions = extractor.generate_questions(requirements)
        print(questions)


def test_conversation_flow():
    """Test a multi-email conversation flow."""
    print("\nTesting Multi-Email Conversation...")
    print("-" * 50)

    # Initial vague email
    initial_email = """From: startup@example.com
To: hello@solopilot.ai
Subject: Need development help
Message-ID: <initial123>

Hi, we need help building something for our startup. Can you help?
"""

    # Follow-up with more details
    followup_email = """From: startup@example.com
To: hello@solopilot.ai
Subject: Re: Need development help
Message-ID: <followup123>
In-Reply-To: <reply123>

Thanks for the quick response! To answer your questions:

1. We need a mobile app (iOS and Android)
2. It's a fitness tracking app for our gym members
3. Features needed:
   - User registration and profiles
   - Workout logging
   - Progress tracking with charts
   - Social features to share workouts
   - Integration with wearables (Fitbit, Apple Watch)

4. Timeline: 6 months
5. Budget: $40-50k

Let me know if you need anything else!
"""

    os.environ["AI_PROVIDER"] = "fake"

    parser = EmailParser()
    extractor = RequirementExtractor()

    # Parse both emails
    email1 = parser.parse(initial_email)
    email2 = parser.parse(followup_email)

    # Build conversation history
    email_history = [
        {"from": email1["from"], "body": email1["body"], "timestamp": email1["timestamp"]},
        {"from": email2["from"], "body": email2["body"], "timestamp": email2["timestamp"]},
    ]

    # Extract requirements from full conversation
    requirements = extractor.extract(email_history, {})

    print("Requirements after full conversation:")
    print(json.dumps(requirements, indent=2))

    is_complete = extractor.is_complete(requirements)
    print(f"\nRequirements Complete: {is_complete}")


if __name__ == "__main__":
    test_email_parser()
    test_requirement_extraction()
    test_conversation_flow()
