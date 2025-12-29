"""Multi-turn conversation engine for client simulation."""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3

from .personas import ClientPersona
from .scenarios import Scenario, ScenarioPreset

logger = logging.getLogger(__name__)

# Load system prompt template
PROMPT_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "client_persona.txt"


@dataclass
class EmailMessage:
    """Represents an email in the conversation."""

    sender: str
    recipient: str
    subject: str
    body: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    direction: str = "outbound"  # "outbound" = client -> freelancer, "inbound" = freelancer -> client
    message_id: str = ""


@dataclass
class ConversationContext:
    """Tracks the state of a simulated conversation."""

    scenario: Scenario
    emails: List[EmailMessage] = field(default_factory=list)
    turn_count: int = 0
    phase: str = "initial"  # initial, clarification, proposal, negotiation, decision
    concluded: bool = False
    outcome: Optional[str] = None  # accepted, declined, ghosted, needs_time
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def last_email(self) -> Optional[EmailMessage]:
        return self.emails[-1] if self.emails else None

    @property
    def conversation_history(self) -> str:
        """Format conversation history for prompt context."""
        if not self.emails:
            return "No previous emails."
        
        history = []
        for email in self.emails:
            direction = "CLIENT" if email.direction == "outbound" else "FREELANCER"
            history.append(f"--- {direction} ({email.timestamp}) ---\n{email.body}")
        
        return "\n\n".join(history)


class ConversationEngine:
    """Manages multi-turn conversation simulation using Bedrock."""

    def __init__(
        self,
        model_id: str = "us.anthropic.claude-3-haiku-20240307-v1:0",
        aws_profile: str = "root",
        aws_region: str = "us-east-2",
    ):
        """Initialize conversation engine with Bedrock client.
        
        Args:
            model_id: Bedrock model ID to use for client simulation
            aws_profile: AWS profile to use
            aws_region: AWS region
        """
        self.model_id = model_id
        self.aws_profile = aws_profile
        self.aws_region = aws_region
        
        # Initialize Bedrock client
        session = boto3.Session(profile_name=aws_profile, region_name=aws_region)
        self.bedrock = session.client("bedrock-runtime")
        
        # Load prompt template
        if PROMPT_TEMPLATE_PATH.exists():
            self.prompt_template = PROMPT_TEMPLATE_PATH.read_text()
        else:
            self.prompt_template = self._get_default_prompt_template()

    def generate_initial_email(self, scenario: Scenario) -> EmailMessage:
        """Generate the first client email based on scenario.
        
        Args:
            scenario: The scenario configuration
        
        Returns:
            Generated EmailMessage from the client
        """
        persona = scenario.persona
        
        # Build the system prompt
        system_prompt = self._build_system_prompt(scenario)
        
        # Build the user prompt for initial email
        user_prompt = f"""Generate the FIRST email from {persona.name} to a freelance developer.

This is your initial outreach. You're reaching out because you need help with a project.

Remember:
- This is the FIRST email, so introduce yourself and your company
- Explain what you need at a high level
- Your communication style is: {persona.communication_style}
- Your technical level is: {persona.technical_level}

Write the email now:"""

        # Call Bedrock
        response = self._call_bedrock(system_prompt, user_prompt)
        
        return EmailMessage(
            sender=persona.email,
            recipient="hello@solopilot.ai",
            subject=self._generate_subject(scenario),
            body=response,
            direction="outbound",
        )

    def generate_reply(
        self,
        context: ConversationContext,
        system_response: str,
    ) -> EmailMessage:
        """Generate client reply based on conversation history and system response.
        
        Args:
            context: Current conversation context
            system_response: The freelancer's response to reply to
        
        Returns:
            Generated EmailMessage from the client
        """
        scenario = context.scenario
        persona = scenario.persona
        
        # Add system response to context
        context.emails.append(EmailMessage(
            sender="hello@solopilot.ai",
            recipient=persona.email,
            subject=f"Re: {context.emails[0].subject if context.emails else 'Project Inquiry'}",
            body=system_response,
            direction="inbound",
        ))
        context.turn_count += 1
        
        # Check if we should conclude
        if self.should_conclude(context):
            return self._generate_conclusion_email(context)
        
        # Build prompts
        system_prompt = self._build_system_prompt(scenario)
        user_prompt = self._build_reply_prompt(context, system_response)
        
        # Call Bedrock
        response = self._call_bedrock(system_prompt, user_prompt)
        
        return EmailMessage(
            sender=persona.email,
            recipient="hello@solopilot.ai",
            subject=f"Re: {context.emails[0].subject}",
            body=response,
            direction="outbound",
        )

    def should_conclude(self, context: ConversationContext) -> bool:
        """Determine if conversation should reach a conclusion.
        
        Args:
            context: Current conversation context
        
        Returns:
            True if conversation should conclude
        """
        # Always conclude if we've exceeded expected turns
        if context.turn_count >= context.scenario.expected_turns:
            return True
        
        # Check for natural conclusion points
        if context.phase == "decision":
            return True
        
        # Don't conclude too early
        if context.turn_count < 2:
            return False
        
        # Check behavior modifiers for early conclusion
        modifiers = context.scenario.behavior_modifiers
        if modifiers.get("responsiveness") == "immediate" and context.turn_count >= 3:
            # Rush scenarios conclude faster
            return True
        
        return False

    def determine_phase(self, context: ConversationContext) -> str:
        """Determine current conversation phase based on history.
        
        Args:
            context: Current conversation context
        
        Returns:
            Phase string: initial, clarification, proposal, negotiation, decision
        """
        turn = context.turn_count
        modifiers = context.scenario.behavior_modifiers
        
        if turn == 0:
            return "initial"
        elif turn <= 2:
            return "clarification"
        elif turn <= 4:
            return "proposal"
        elif turn <= 6:
            return "negotiation"
        else:
            return "decision"

    def _build_system_prompt(self, scenario: Scenario) -> str:
        """Build system prompt from template and scenario."""
        persona = scenario.persona
        modifiers = scenario.behavior_modifiers
        
        # Build behavior instructions
        behavior_instructions = self._build_behavior_instructions(modifiers)
        
        return self.prompt_template.format(
            persona_name=persona.name,
            persona_company=persona.company,
            persona_role=persona.role,
            persona_industry=persona.industry,
            persona_communication_style=persona.communication_style,
            persona_technical_level=persona.technical_level,
            project_type=scenario.project_type,
            project_description=scenario.project_description,
            budget_range=scenario.budget_range_str,
            timeline=scenario.timeline,
            features=", ".join(scenario.features),
            behavior_instructions=behavior_instructions,
        )

    def _build_behavior_instructions(self, modifiers: Dict[str, Any]) -> str:
        """Build behavior instructions from modifiers."""
        instructions = []
        
        if modifiers.get("clarity") == "low":
            instructions.append("- Be vague about requirements. Don't give specific details unless pressed.")
        elif modifiers.get("clarity") == "high":
            instructions.append("- Be clear and specific about what you need.")
        
        if modifiers.get("objections") == "price_focused":
            instructions.append("- Express concern about pricing. Ask about discounts or phased approaches.")
        elif modifiers.get("objections") == "timeline_focused":
            instructions.append("- Be very focused on timeline. Express urgency.")
        elif modifiers.get("objections") == "comparison":
            instructions.append("- Mention you're getting other quotes. Compare offerings.")
        
        if modifiers.get("adds_features"):
            instructions.append("- In each reply, casually mention 1-2 additional features you'd like.")
        
        if modifiers.get("formal_tone"):
            instructions.append("- Use formal, professional language. Mention compliance requirements.")
        
        if modifiers.get("vague_responses"):
            instructions.append("- Give incomplete answers. Say 'I'll have to check' or 'not sure yet'.")
        
        if modifiers.get("mentions_competitors"):
            instructions.append("- Occasionally mention other developers or agencies you're considering.")
        
        if modifiers.get("willing_to_pay_premium"):
            instructions.append("- Show willingness to pay more for faster delivery.")
        
        if not instructions:
            instructions.append("- Behave as a typical client would.")
        
        return "\n".join(instructions)

    def _build_reply_prompt(self, context: ConversationContext, system_response: str) -> str:
        """Build prompt for generating a reply."""
        scenario = context.scenario
        phase = self.determine_phase(context)
        context.phase = phase
        
        phase_instructions = {
            "initial": "Continue providing information about your needs.",
            "clarification": "Answer their questions. You can ask clarifying questions too.",
            "proposal": "React to their proposal or pricing information. Express any concerns.",
            "negotiation": "Discuss terms, timeline, or scope adjustments.",
            "decision": "Move toward a decision - accept, decline, or ask for more time.",
        }
        
        return f"""The freelancer has responded to your email:

---
{system_response}
---

Conversation history so far:
{context.conversation_history}

Current phase: {phase}
Turn: {context.turn_count} of ~{scenario.expected_turns}

Instructions for this reply:
{phase_instructions.get(phase, "Continue the conversation naturally.")}

Write your reply email now:"""

    def _generate_conclusion_email(self, context: ConversationContext) -> EmailMessage:
        """Generate final email that concludes the conversation."""
        scenario = context.scenario
        persona = scenario.persona
        modifiers = scenario.behavior_modifiers
        
        # Determine outcome based on scenario and modifiers
        if modifiers.get("may_reduce_scope"):
            outcome = "accepted_reduced"
        elif modifiers.get("procurement_process"):
            outcome = "needs_time"
        elif modifiers.get("price_comparison"):
            outcome = "declined"  # 50% chance in real implementation
        else:
            outcome = "accepted"
        
        context.concluded = True
        context.outcome = outcome
        
        system_prompt = self._build_system_prompt(scenario)
        user_prompt = f"""This is the FINAL email in the conversation. You need to conclude with a decision.

Your decision: {outcome}

Conversation history:
{context.conversation_history}

Write your final email based on your decision:
- If accepting: Confirm you want to proceed and ask about next steps
- If declining: Politely decline and give a brief reason
- If need more time: Ask for more time to discuss with stakeholders

Write the email now:"""
        
        response = self._call_bedrock(system_prompt, user_prompt)
        
        return EmailMessage(
            sender=persona.email,
            recipient="hello@solopilot.ai",
            subject=f"Re: {context.emails[0].subject if context.emails else 'Project'}",
            body=response,
            direction="outbound",
        )

    def _generate_subject(self, scenario: Scenario) -> str:
        """Generate email subject based on scenario."""
        project_type = scenario.project_type.replace("_", " ").title()
        
        subjects = [
            f"Need help with {project_type}",
            f"{project_type} Development Project",
            f"Inquiry: {project_type} for {scenario.persona.company}",
            f"Looking for developer for {project_type}",
            f"{scenario.persona.company} - {project_type} Project",
        ]
        
        import random
        return random.choice(subjects)

    def _call_bedrock(self, system_prompt: str, user_prompt: str) -> str:
        """Call Bedrock Claude model using invoke_model API."""
        import json as json_module
        
        try:
            # Use Claude Messages API format (same as project's conversational_responder)
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
                "temperature": 0.8,  # Higher temp for more natural variation
            }
            
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json_module.dumps(request_body),
                contentType="application/json",
            )
            
            response_body = json_module.loads(response["body"].read())
            content = response_body["content"][0]["text"]
            return content.strip()
            
        except Exception as e:
            logger.error(f"Bedrock call failed: {e}")
            raise

    def _get_default_prompt_template(self) -> str:
        """Return default prompt template if file not found."""
        return """You are simulating a potential client reaching out to a freelance developer.

## Your Character
- Name: {persona_name}
- Company: {persona_company}
- Role: {persona_role}
- Communication Style: {persona_communication_style}

## Project Context
- Project Type: {project_type}
- Budget Range: {budget_range}
- Timeline: {timeline}
- Features: {features}

## Behavior
{behavior_instructions}

Write natural, realistic emails as this client would. Stay in character."""
