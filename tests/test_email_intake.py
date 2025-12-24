"""Tests for email intake agent."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.agents.email_intake import ConversationStateManager, EmailParser, RequirementExtractor


class TestEmailParser:
    """Test email parsing functionality."""

    def test_parse_simple_email(self):
        """Test parsing a simple email."""
        raw_email = """From: john@example.com
To: hello@solopilot.ai
Subject: Need a website for my bakery
Date: Mon, 1 Jan 2024 10:00:00 +0000
Message-ID: <abc123@example.com>

Hi,

I need a website for my bakery business. We sell fresh bread and pastries.

Thanks,
John
"""
        parser = EmailParser()
        result = parser.parse(raw_email)

        assert result["from"] == "john@example.com"
        assert result["subject"] == "Need a website for my bakery"
        assert "bakery business" in result["body"]
        assert result["thread_id"]  # Should generate thread ID
        assert not result["is_reply"]

    def test_parse_apollo_reply(self):
        """Test parsing an Apollo.io style reply."""
        raw_email = """From: "Sarah Johnson" <sarah@techstartup.com>
To: sales@solopilot.ai
Subject: Re: Transform Your Development Process
Date: Wed, 15 Jan 2024 14:30:00 +0000
Message-ID: <reply123@techstartup.com>
In-Reply-To: <original123@solopilot.ai>
References: <original123@solopilot.ai>

Hi there,

Thanks for reaching out! Yes, we're actually looking for help with our new SaaS platform.

We need:
- User authentication and profiles
- Subscription management with Stripe
- Analytics dashboard
- API for third-party integrations

Our timeline is 3 months and budget is around $15-20k.

Can you help with this?

Best,
Sarah Johnson
CEO, TechStartup Inc.

--
Sent from my iPhone
"""
        parser = EmailParser()
        result = parser.parse(raw_email)

        assert result["from"] == "sarah@techstartup.com"
        assert result["subject"] == "Transform Your Development Process"
        assert result["is_reply"] is True
        assert "SaaS platform" in result["body"]
        assert "Sent from my iPhone" not in result["body"]  # Signature removed


class TestRequirementExtractor:
    """Test requirement extraction from emails."""

    @patch("src.agents.email_intake.requirement_extractor.get_provider")
    def test_extract_requirements(self, mock_get_provider):
        """Test extracting requirements from email conversation."""
        # Mock provider response
        mock_provider = MagicMock()
        mock_provider.generate_code.return_value = json.dumps(
            {
                "title": "TechStartup SaaS Platform",
                "summary": "SaaS platform with user management and analytics",
                "project_type": "web_app",
                "business_description": "Tech startup building a SaaS platform",
                "features": [
                    {"name": "User Authentication", "desc": "User login and profiles"},
                    {"name": "Subscription Management", "desc": "Stripe integration for payments"},
                    {"name": "Analytics Dashboard", "desc": "Usage analytics and reporting"},
                    {"name": "API Integration", "desc": "Third-party API access"},
                ],
                "tech_stack": ["Stripe", "API"],
                "timeline": "3 months",
                "budget": "$15,000 - $20,000",
            }
        )
        mock_get_provider.return_value = mock_provider

        extractor = RequirementExtractor()

        email_history = [
            {
                "from": "sarah@techstartup.com",
                "body": "We need a SaaS platform with user auth, Stripe subscriptions, analytics dashboard, and API. Timeline: 3 months, budget: $15-20k",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        ]

        requirements = extractor.extract(email_history, {})

        assert requirements["title"] == "TechStartup SaaS Platform"
        assert requirements["project_type"] == "web_app"
        assert len(requirements["features"]) == 4
        assert requirements["budget"] == "$15,000 - $20,000"

    def test_is_complete(self):
        """Test requirement completeness check."""
        extractor = RequirementExtractor()

        # Incomplete requirements
        incomplete = {
            "title": "My Project",
            "features": [{"name": "Feature 1", "desc": "Description"}],
        }
        assert extractor.is_complete(incomplete) is False

        # Complete requirements
        complete = {
            "title": "My Project",
            "project_type": "website",
            "business_description": "A bakery business",
            "features": [
                {"name": "Feature 1", "desc": "Desc 1"},
                {"name": "Feature 2", "desc": "Desc 2"},
                {"name": "Feature 3", "desc": "Desc 3"},
            ],
        }
        assert extractor.is_complete(complete) is True

    def test_generate_questions(self):
        """Test follow-up question generation."""
        extractor = RequirementExtractor()

        # Missing multiple fields
        requirements = {
            "title": "My Project",
            "features": [{"name": "Feature 1", "desc": "Description"}],
        }

        questions = extractor.generate_questions(requirements)

        assert "type of project" in questions  # Missing project_type
        assert "describe your business" in questions  # Missing business_description
        assert "2 more key features" in questions  # Only 1 feature


class TestConversationStateManager:
    """Test DynamoDB conversation state management."""

    @patch("src.agents.email_intake.conversation_state.boto3.resource")
    def test_get_or_create_conversation(self, mock_boto):
        """Test getting or creating conversation."""
        # Mock DynamoDB table
        mock_table = MagicMock()
        mock_boto.return_value.Table.return_value = mock_table

        # Mock get_item returns empty (new conversation)
        mock_table.get_item.return_value = {}

        manager = ConversationStateManager()
        result = manager.get_or_create("test-thread-123")

        # Should create new conversation
        mock_table.put_item.assert_called_once()
        assert result["conversation_id"] == "test-thread-123"
        assert result["status"] == "active"

    @patch("src.agents.email_intake.conversation_state.boto3.resource")
    def test_add_email(self, mock_boto):
        """Test adding email to conversation."""
        mock_table = MagicMock()
        mock_boto.return_value.Table.return_value = mock_table

        # Mock update response
        mock_table.update_item.return_value = {
            "Attributes": {
                "conversation_id": "test-123",
                "email_history": [{"from": "test@example.com"}],
            }
        }

        manager = ConversationStateManager()
        email = {"from": "test@example.com", "body": "Test email"}

        result = manager.add_email("test-123", email)

        mock_table.update_item.assert_called_once()
        assert result["email_history"][0]["from"] == "test@example.com"
