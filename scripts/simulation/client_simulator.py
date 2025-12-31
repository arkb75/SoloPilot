"""Main orchestrator for client-only simulation scenarios.

This simulates the CLIENT side only - generating realistic client emails
that are sent via real SES. The freelancer responds manually through
the normal dashboard workflow.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .conversation_engine import ConversationContext, ConversationEngine, EmailMessage
from .intake_adapter import IntakeAdapter, SystemResponse, create_mock_response
from .personas import ClientPersona
from .scenarios import Scenario, ScenarioPreset, get_all_presets, load_scenario

logger = logging.getLogger(__name__)


@dataclass
class SimulatorConfig:
    """Configuration for the client simulator."""

    # AWS settings
    aws_profile: str = "root"
    aws_region: str = "us-east-2"
    
    # Email settings
    intake_email: str = "intake@abdulkhurram.com"
    
    # Model settings
    model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    
    # Simulation settings
    max_turns: int = 10
    verbose: bool = False
    dry_run: bool = False  # If True, don't send real emails
    
    # Output settings
    output_format: str = "text"  # text, json, markdown
    save_path: Optional[str] = None


@dataclass
class ConversationResult:
    """Result of a single conversation simulation."""

    scenario: Scenario
    conversation_id: str
    emails: List[EmailMessage]
    turns: int
    outcome: str
    duration_seconds: float
    final_phase: str
    final_requirements: Dict[str, Any]
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_preset": self.scenario.preset.value,
            "persona": {
                "name": self.scenario.persona.name,
                "company": self.scenario.persona.company,
                "email": self.scenario.persona.email,
            },
            "conversation_id": self.conversation_id,
            "turns": self.turns,
            "outcome": self.outcome,
            "duration_seconds": self.duration_seconds,
            "final_phase": self.final_phase,
            "final_requirements": self.final_requirements,
            "error": self.error,
            "emails": [
                {
                    "sender": e.sender,
                    "subject": e.subject,
                    "body": e.body,
                    "direction": e.direction,
                    "timestamp": e.timestamp,
                }
                for e in self.emails
            ],
        }


@dataclass
class BatchResult:
    """Result of running multiple scenarios."""

    results: List[ConversationResult]
    total_duration_seconds: float
    success_count: int
    error_count: int
    
    def summary(self) -> Dict[str, Any]:
        outcomes = {}
        for r in self.results:
            outcomes[r.outcome] = outcomes.get(r.outcome, 0) + 1
        
        return {
            "total_scenarios": len(self.results),
            "success_count": self.success_count,
            "error_count": self.error_count,
            "total_duration_seconds": self.total_duration_seconds,
            "avg_turns": sum(r.turns for r in self.results) / len(self.results) if self.results else 0,
            "outcomes": outcomes,
        }


class ClientSimulator:
    """Orchestrates client-only simulation scenarios.
    
    This simulator:
    1. Generates realistic AI client personas and emails
    2. Sends those emails via real SES to your intake
    3. Waits for you to respond manually through dashboard
    4. Generates next client response based on your reply
    5. Repeats until conversation concludes
    """

    def __init__(self, config: SimulatorConfig):
        """Initialize simulator with configuration.
        
        Args:
            config: Simulator configuration
        """
        self.config = config
        
        # Initialize conversation engine (for AI client generation)
        self.engine = ConversationEngine(
            model_id=config.model_id,
            aws_profile=config.aws_profile,
            aws_region=config.aws_region,
        )
        
        # Initialize intake adapter (for email sending)
        self.adapter = IntakeAdapter(
            aws_profile=config.aws_profile,
            aws_region=config.aws_region,
            intake_email=config.intake_email,
        )

    def run_scenario(self, scenario: Scenario) -> ConversationResult:
        """Run a single client scenario through multiple turns.
        
        Args:
            scenario: The scenario to simulate
        
        Returns:
            ConversationResult with full conversation history
        """
        start_time = datetime.now(timezone.utc)
        context = ConversationContext(scenario=scenario)
        conversation_id = ""
        error = None
        
        try:
            # Generate client email address
            client_email = self.adapter.generate_client_email(scenario.persona.name)
            scenario.persona.email = client_email
            
            if self.config.verbose:
                print(f"\n{'='*60}")
                print(f"Starting scenario: {scenario.preset.value}")
                print(f"Client: {scenario.persona.name} ({scenario.persona.company})")
                print(f"Client Email: {client_email}")
                print(f"{'='*60}")
            
            # Generate initial email
            initial_email = self.engine.generate_initial_email(scenario)
            context.emails.append(initial_email)
            
            self._print_email(initial_email, "CLIENT")
            
            if self.config.dry_run:
                # In dry run mode, just generate emails without real SES
                return self._run_dry_scenario(context, start_time)
            
            # Send initial email via real SES
            print(f"\n📤 Sending email to {self.config.intake_email}...")
            send_result = self.adapter.send_client_email(
                client_email=client_email,
                subject=initial_email.subject,
                body=initial_email.body,
            )
            
            if not send_result.get("success"):
                raise Exception(f"Failed to send email: {send_result.get('error')}")
            
            print(f"✅ Email sent! Message ID: {send_result.get('message_id')}")
            
            # Wait for conversation to be created
            print(f"\n⏳ Waiting for conversation to appear in system...")
            conversation_id = self.adapter.wait_for_conversation(
                client_email=client_email,
                subject=initial_email.subject,
                timeout_seconds=60,
            )
            
            if not conversation_id:
                raise Exception("Timeout waiting for conversation to be created")
            
            print(f"✅ Conversation created: {conversation_id}")
            
            # Track email count for detecting responses
            last_email_count = 1  # We sent 1 email
            
            # Multi-turn conversation loop
            while not context.concluded and context.turn_count < self.config.max_turns:
                # Wait for freelancer response (interactive)
                response = self.adapter.wait_for_response(
                    conversation_id=conversation_id,
                    last_email_count=last_email_count,
                    interactive=True,
                )
                
                if not response:
                    print("\n⚠️  No response detected. Continue anyway? (y/n): ", end="")
                    if input().lower() != 'y':
                        context.outcome = "abandoned"
                        break
                    # Try to get latest response
                    response_body = self.adapter.get_latest_response(conversation_id)
                    if not response_body:
                        print("❌ Still no response found. Ending conversation.")
                        break
                else:
                    response_body = response.get("body", "")
                
                # Display freelancer response
                freelancer_email = EmailMessage(
                    sender=self.config.intake_email,
                    recipient=client_email,
                    subject=response.get("subject", f"Re: {initial_email.subject}") if response else f"Re: {initial_email.subject}",
                    body=response_body,
                    direction="inbound",
                )
                self._print_email(freelancer_email, "FREELANCER")
                
                # Check if user wants to continue
                print("\n🔄 Generate next client response? (y/n/done): ", end="")
                user_input = input().lower()
                if user_input == 'n':
                    context.outcome = "paused"
                    break
                elif user_input == 'done':
                    context.outcome = "completed"
                    context.concluded = True
                    break
                
                # Ask for optional guidance
                print("\n💡 Guide client's response (or press Enter to skip):")
                print("   Examples: 'ask for PDF proposal', 'say budget is too high', 'wrap up and accept'")
                print("   > ", end="")
                guidance = input().strip() or None
                
                # Generate client reply with optional guidance
                client_reply = self.engine.generate_reply(context, response_body, guidance=guidance)
                context.emails.append(client_reply)
                
                self._print_email(client_reply, "CLIENT")
                
                if context.concluded:
                    break
                
                # Send the reply
                print(f"\n📤 Sending reply...")
                
                # Get conversation state for threading info
                conv_state = self.adapter.get_conversation_state(conversation_id)
                thread_refs = conv_state.get("thread_references", []) if conv_state else []
                
                send_result = self.adapter.send_client_email(
                    client_email=client_email,
                    subject=client_reply.subject,
                    body=client_reply.body,
                    references=thread_refs,
                )
                
                if not send_result.get("success"):
                    raise Exception(f"Failed to send reply: {send_result.get('error')}")
                
                print(f"✅ Reply sent!")
                last_email_count = len(context.emails)
            
            # Get final state
            final_conversation = self.adapter.get_conversation_state(conversation_id) or {}
            
        except Exception as e:
            logger.error(f"Scenario failed: {e}")
            error = str(e)
            final_conversation = {}
        
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        return ConversationResult(
            scenario=scenario,
            conversation_id=conversation_id,
            emails=context.emails,
            turns=context.turn_count,
            outcome=context.outcome or "incomplete",
            duration_seconds=duration,
            final_phase=final_conversation.get("phase", context.phase),
            final_requirements=final_conversation.get("requirements", {}),
            error=error,
        )

    def run_batch(
        self,
        presets: Optional[List[ScenarioPreset]] = None,
        count: int = 1,
        randomize: bool = False,
    ) -> BatchResult:
        """Run multiple scenarios in sequence.
        
        Args:
            presets: List of preset types to run (runs all once if None)
            count: Number of times to run each preset
            randomize: If True, randomize preset order
        
        Returns:
            BatchResult with all conversation results
        """
        import random
        
        start_time = datetime.now(timezone.utc)
        
        # Determine which presets to run
        if presets is None:
            presets = get_all_presets()
        
        # Build scenario list
        scenarios = []
        for _ in range(count):
            for preset in presets:
                scenarios.append(load_scenario(preset))
        
        if randomize:
            random.shuffle(scenarios)
        
        results = []
        success_count = 0
        error_count = 0
        
        for i, scenario in enumerate(scenarios):
            print(f"\n{'='*60}")
            print(f"Running scenario {i+1}/{len(scenarios)}: {scenario.preset.value}")
            print(f"{'='*60}")
            
            result = self.run_scenario(scenario)
            results.append(result)
            
            if result.error:
                error_count += 1
            else:
                success_count += 1
            
            # Ask if user wants to continue to next scenario
            if i < len(scenarios) - 1:
                print("\n📋 Continue to next scenario? (y/n): ", end="")
                if input().lower() != 'y':
                    break
        
        end_time = datetime.now(timezone.utc)
        total_duration = (end_time - start_time).total_seconds()
        
        return BatchResult(
            results=results,
            total_duration_seconds=total_duration,
            success_count=success_count,
            error_count=error_count,
        )

    def _run_dry_scenario(
        self,
        context: ConversationContext,
        start_time: datetime,
    ) -> ConversationResult:
        """Run scenario in dry-run mode (no real SES, just email generation).
        
        Args:
            context: Conversation context with initial email
            start_time: When scenario started
        
        Returns:
            ConversationResult with simulated emails only
        """
        scenario = context.scenario
        
        print("\n🔸 DRY RUN MODE - No real emails sent")
        
        # Simulate a few turns with mock responses
        mock_responses = [
            "Thank you for reaching out! I'd love to learn more about your project. Could you tell me more about your timeline and budget expectations?",
            "That sounds great! Based on what you've described, I think we can definitely help. Let me put together a proposal for you.",
            "I've prepared a proposal based on our discussion. The total would be around ${} with a timeline of {}. Would you like to proceed?".format(
                (scenario.budget_min + scenario.budget_max) // 2,
                scenario.timeline,
            ),
        ]
        
        for i, mock_response in enumerate(mock_responses):
            if context.turn_count >= self.config.max_turns:
                break
            
            self._print_email(
                EmailMessage(
                    sender=self.config.intake_email,
                    recipient=scenario.persona.email,
                    subject=f"Re: {context.emails[0].subject}",
                    body=mock_response,
                    direction="inbound",
                ),
                "FREELANCER (mock)",
            )
            
            # Check if user wants to continue
            print("\n🔄 Generate next client response? (y/n): ", end="")
            if input().lower() != 'y':
                break
            
            # Ask for optional guidance
            print("\n💡 Guide client's response (or press Enter to skip):")
            print("   Examples: 'ask for PDF proposal', 'say budget is too high', 'wrap up and accept'")
            print("   > ", end="")
            guidance = input().strip() or None
            
            client_reply = self.engine.generate_reply(context, mock_response, guidance=guidance)
            context.emails.append(client_reply)
            
            self._print_email(client_reply, "CLIENT")
            
            if context.concluded:
                break
        
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        return ConversationResult(
            scenario=scenario,
            conversation_id="dry-run",
            emails=context.emails,
            turns=context.turn_count,
            outcome=context.outcome or "dry_run",
            duration_seconds=duration,
            final_phase=context.phase,
            final_requirements={},
            error=None,
        )

    def _print_email(self, email: EmailMessage, label: str) -> None:
        """Print email for output."""
        print(f"\n{'─'*60}")
        print(f"📧 {label}")
        print(f"{'─'*60}")
        print(f"From: {email.sender}")
        print(f"To: {email.recipient}")
        print(f"Subject: {email.subject}")
        print(f"{'─'*60}")
        print(email.body)
        print(f"{'─'*60}")

    def save_results(self, result: ConversationResult, path: Optional[str] = None) -> str:
        """Save conversation result to file.
        
        Args:
            result: Conversation result to save
            path: Output directory (uses config.save_path if not provided)
        
        Returns:
            Path to saved file
        """
        save_dir = Path(path or self.config.save_path or "output/simulations")
        save_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{result.scenario.preset.value}_{timestamp}.json"
        filepath = save_dir / filename
        
        with open(filepath, "w") as f:
            json.dump(result.to_dict(), f, indent=2, default=str)
        
        logger.info(f"Saved result to: {filepath}")
        return str(filepath)
