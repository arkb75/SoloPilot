"""Main orchestrator for client simulation scenarios."""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .conversation_engine import ConversationContext, ConversationEngine, EmailMessage
from .intake_adapter import IntakeAdapter, SystemResponse
from .personas import ClientPersona
from .scenarios import Scenario, ScenarioPreset, get_all_presets, load_scenario

logger = logging.getLogger(__name__)


@dataclass
class SimulatorConfig:
    """Configuration for the client simulator."""

    # AWS settings
    aws_profile: str = "root"
    aws_region: str = "us-east-2"
    
    # Model settings
    model_id: str = "us.anthropic.claude-3-haiku-20240307-v1:0"
    
    # Simulation settings
    max_turns: int = 10
    verbose: bool = False
    dry_run: bool = False
    
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
    """Orchestrates client simulation scenarios."""

    def __init__(self, config: SimulatorConfig):
        """Initialize simulator with configuration.
        
        Args:
            config: Simulator configuration
        """
        self.config = config
        
        # Initialize conversation engine
        self.engine = ConversationEngine(
            model_id=config.model_id,
            aws_profile=config.aws_profile,
            aws_region=config.aws_region,
        )
        
        # Initialize intake adapter (unless dry run)
        if not config.dry_run:
            self.adapter = IntakeAdapter(
                aws_profile=config.aws_profile,
                aws_region=config.aws_region,
            )
        else:
            self.adapter = None

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
            # Generate initial email
            if self.config.verbose:
                logger.info(f"Starting scenario: {scenario.preset.value}")
                logger.info(f"Client: {scenario.persona.name} ({scenario.persona.company})")
            
            initial_email = self.engine.generate_initial_email(scenario)
            context.emails.append(initial_email)
            
            if self.config.verbose:
                self._print_email(initial_email, "CLIENT")
            
            if self.config.dry_run:
                # In dry run mode, just generate emails without Lambda
                return self._run_dry_scenario(context, start_time)
            
            # Send to intake system
            response = self.adapter.create_conversation(
                client_email=scenario.persona.email,
                subject=initial_email.subject,
                body=initial_email.body,
            )
            
            conversation_id = response.conversation_id
            
            if response.error:
                raise Exception(f"Intake error: {response.error}")
            
            # Multi-turn conversation loop
            while not context.concluded and context.turn_count < self.config.max_turns:
                # Get system response
                system_response = response.response_body
                
                if not system_response:
                    # Try to get from pending reply
                    pending = self.adapter.get_pending_reply(conversation_id)
                    if pending:
                        system_response = pending.get("llm_response", "")
                
                if not system_response:
                    logger.warning(f"No system response at turn {context.turn_count}")
                    break
                
                if self.config.verbose:
                    self._print_email(
                        EmailMessage(
                            sender="hello@solopilot.ai",
                            recipient=scenario.persona.email,
                            subject=response.subject,
                            body=system_response,
                            direction="inbound",
                        ),
                        "SYSTEM",
                    )
                
                # Generate client reply
                client_reply = self.engine.generate_reply(context, system_response)
                context.emails.append(client_reply)
                
                if self.config.verbose:
                    self._print_email(client_reply, "CLIENT")
                
                if context.concluded:
                    break
                
                # Send reply to intake system
                response = self.adapter.send_reply(
                    conversation_id=conversation_id,
                    client_email=scenario.persona.email,
                    body=client_reply.body,
                )
                
                if response.error:
                    raise Exception(f"Reply error: {response.error}")
            
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
            if self.config.verbose:
                logger.info(f"\n{'='*60}")
                logger.info(f"Running scenario {i+1}/{len(scenarios)}: {scenario.preset.value}")
                logger.info(f"{'='*60}")
            
            result = self.run_scenario(scenario)
            results.append(result)
            
            if result.error:
                error_count += 1
            else:
                success_count += 1
        
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
        """Run scenario in dry-run mode (no Lambda, just email generation).
        
        Args:
            context: Conversation context with initial email
            start_time: When scenario started
        
        Returns:
            ConversationResult with simulated emails only
        """
        scenario = context.scenario
        
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
            
            if self.config.verbose:
                self._print_email(
                    EmailMessage(
                        sender="hello@solopilot.ai",
                        recipient=scenario.persona.email,
                        subject=f"Re: {context.emails[0].subject}",
                        body=mock_response,
                        direction="inbound",
                    ),
                    "SYSTEM (mock)",
                )
            
            client_reply = self.engine.generate_reply(context, mock_response)
            context.emails.append(client_reply)
            
            if self.config.verbose:
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
        """Print email for verbose output."""
        print(f"\n--- {label} ---")
        print(f"From: {email.sender}")
        print(f"Subject: {email.subject}")
        print(f"---")
        print(email.body)
        print(f"---\n")

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
