#!/usr/bin/env python3
"""
Client Simulation Testing Utility

A Bedrock-powered tool that simulates realistic client interactions with
the email intake system for end-to-end testing.

Usage:
    # Run single scenario
    python scripts/run_client_simulation.py --scenario simple --verbose

    # Run multiple scenarios
    python scripts/run_client_simulation.py --scenarios simple,complex,budget_conscious

    # Run with custom settings
    python scripts/run_client_simulation.py --count 3 --max-turns 5 --output json

    # Dry run (no Lambda, just test email generation)
    python scripts/run_client_simulation.py --scenario simple --dry-run --verbose
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.simulation import (
    ClientSimulator,
    ScenarioPreset,
    SimulatorConfig,
    load_scenario,
    get_all_presets,
    get_preset_description,
)
from scripts.simulation.scenarios import get_all_presets, get_preset_description

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Client Simulation Testing Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run a simple scenario with verbose output
  python scripts/run_client_simulation.py --scenario simple --verbose

  # Run multiple specific scenarios
  python scripts/run_client_simulation.py --scenarios simple,complex,rush

  # Run 3 random scenarios
  python scripts/run_client_simulation.py --count 3 --random

  # Dry run to test email generation without Lambda
  python scripts/run_client_simulation.py --scenario budget_conscious --dry-run

  # Save results to file
  python scripts/run_client_simulation.py --scenario enterprise --save ./output

Available Scenarios:
""" + "\n".join(f"  {p.value}: {get_preset_description(p)}" for p in get_all_presets())
    )
    
    # Scenario selection
    scenario_group = parser.add_mutually_exclusive_group()
    scenario_group.add_argument(
        "--scenario", "-s",
        type=str,
        choices=[p.value for p in ScenarioPreset],
        help="Single scenario preset to run",
    )
    scenario_group.add_argument(
        "--scenarios",
        type=str,
        help="Comma-separated list of scenario presets",
    )
    scenario_group.add_argument(
        "--all",
        action="store_true",
        help="Run all scenario presets",
    )
    
    # Scenario settings
    parser.add_argument(
        "--count", "-n",
        type=int,
        default=1,
        help="Number of times to run each scenario (default: 1)",
    )
    parser.add_argument(
        "--random",
        action="store_true",
        help="Randomize scenario order",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=10,
        help="Maximum conversation turns (default: 10)",
    )
    
    # Budget/timeline overrides
    parser.add_argument(
        "--budget-range",
        type=str,
        help="Override budget range, e.g., '5000-15000'",
    )
    parser.add_argument(
        "--timeline",
        type=str,
        help="Override timeline, e.g., '2 months'",
    )
    
    # AWS settings
    parser.add_argument(
        "--profile",
        type=str,
        default="root",
        help="AWS profile to use (default: root)",
    )
    parser.add_argument(
        "--region",
        type=str,
        default="us-east-2",
        help="AWS region (default: us-east-2)",
    )
    
    # Model settings
    parser.add_argument(
        "--model",
        type=str,
        default="us.anthropic.claude-3-haiku-20240307-v1:0",
        help="Bedrock model/inference profile ID for client simulation",
    )
    
    # Output settings
    parser.add_argument(
        "--output", "-o",
        type=str,
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--save",
        type=str,
        help="Directory to save full conversation results",
    )
    
    # Execution settings
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed output including all emails",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate client emails without invoking Lambda",
    )
    parser.add_argument(
        "--list-scenarios",
        action="store_true",
        help="List available scenarios and exit",
    )
    
    return parser.parse_args()


def parse_budget_range(budget_str: str) -> tuple:
    """Parse budget range string like '5000-15000' to tuple."""
    try:
        parts = budget_str.replace("$", "").replace(",", "").split("-")
        return (int(parts[0]), int(parts[1]))
    except (ValueError, IndexError):
        raise ValueError(f"Invalid budget range format: {budget_str}. Use format: 5000-15000")


def get_presets_from_args(args: argparse.Namespace) -> List[ScenarioPreset]:
    """Determine which presets to run based on arguments."""
    if args.all:
        return list(ScenarioPreset)
    elif args.scenarios:
        preset_names = [s.strip() for s in args.scenarios.split(",")]
        presets = []
        for name in preset_names:
            try:
                presets.append(ScenarioPreset(name))
            except ValueError:
                logger.error(f"Unknown scenario preset: {name}")
                logger.info(f"Available presets: {[p.value for p in ScenarioPreset]}")
                sys.exit(1)
        return presets
    elif args.scenario:
        return [ScenarioPreset(args.scenario)]
    else:
        # Default to simple scenario
        return [ScenarioPreset.SIMPLE]


def format_result_text(result) -> str:
    """Format result as text."""
    lines = [
        f"\n{'='*60}",
        f"Scenario: {result.scenario.preset.value}",
        f"{'='*60}",
        f"Client: {result.scenario.persona.name} ({result.scenario.persona.company})",
        f"Conversation ID: {result.conversation_id}",
        f"Turns: {result.turns}",
        f"Outcome: {result.outcome}",
        f"Duration: {result.duration_seconds:.1f}s",
        f"Final Phase: {result.final_phase}",
    ]
    
    if result.error:
        lines.append(f"Error: {result.error}")
    
    if result.final_requirements:
        lines.append(f"\nExtracted Requirements:")
        for key, value in result.final_requirements.items():
            if isinstance(value, (list, dict)):
                lines.append(f"  {key}: {json.dumps(value, default=str)[:100]}...")
            else:
                lines.append(f"  {key}: {value}")
    
    lines.append("=" * 60)
    return "\n".join(lines)


def format_result_markdown(result) -> str:
    """Format result as markdown."""
    md = f"""
## {result.scenario.preset.value.replace("_", " ").title()} Scenario

| Field | Value |
|-------|-------|
| Client | {result.scenario.persona.name} ({result.scenario.persona.company}) |
| Conversation ID | `{result.conversation_id}` |
| Turns | {result.turns} |
| Outcome | **{result.outcome}** |
| Duration | {result.duration_seconds:.1f}s |
| Phase | {result.final_phase} |

"""
    if result.error:
        md += f"\n> ⚠️ **Error**: {result.error}\n"
    
    return md


def format_batch_summary(batch_result) -> str:
    """Format batch summary."""
    summary = batch_result.summary()
    
    lines = [
        f"\n{'='*60}",
        "BATCH SUMMARY",
        f"{'='*60}",
        f"Total Scenarios: {summary['total_scenarios']}",
        f"Successful: {summary['success_count']}",
        f"Errors: {summary['error_count']}",
        f"Total Duration: {summary['total_duration_seconds']:.1f}s",
        f"Average Turns: {summary['avg_turns']:.1f}",
        f"\nOutcome Distribution:",
    ]
    
    for outcome, count in summary["outcomes"].items():
        lines.append(f"  {outcome}: {count}")
    
    lines.append("=" * 60)
    return "\n".join(lines)


def main():
    """Main entry point."""
    args = parse_args()
    
    # List scenarios and exit
    if args.list_scenarios:
        print("\nAvailable Scenario Presets:\n")
        for preset in get_all_presets():
            print(f"  {preset.value:20} - {get_preset_description(preset)}")
        print()
        return
    
    # Configure logging
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Build configuration
    config = SimulatorConfig(
        aws_profile=args.profile,
        aws_region=args.region,
        model_id=args.model,
        max_turns=args.max_turns,
        verbose=args.verbose,
        dry_run=args.dry_run,
        output_format=args.output,
        save_path=args.save,
    )
    
    # Get presets to run
    presets = get_presets_from_args(args)
    
    logger.info(f"Starting client simulation")
    logger.info(f"  AWS Profile: {config.aws_profile}")
    logger.info(f"  Region: {config.aws_region}")
    logger.info(f"  Scenarios: {[p.value for p in presets]}")
    logger.info(f"  Max Turns: {config.max_turns}")
    if args.dry_run:
        logger.info("  Mode: DRY RUN (no Lambda invocation)")
    
    # Initialize simulator
    simulator = ClientSimulator(config)
    
    # Parse budget override if provided
    budget_override = None
    if args.budget_range:
        budget_override = parse_budget_range(args.budget_range)
    
    # Run scenarios
    if len(presets) == 1 and args.count == 1:
        # Single scenario
        scenario = load_scenario(
            presets[0],
            budget_override=budget_override,
            timeline_override=args.timeline,
        )
        
        result = simulator.run_scenario(scenario)
        
        # Format output
        if args.output == "json":
            print(json.dumps(result.to_dict(), indent=2, default=str))
        elif args.output == "markdown":
            print(format_result_markdown(result))
        else:
            print(format_result_text(result))
        
        # Save if requested
        if args.save:
            simulator.save_results(result)
    
    else:
        # Batch run
        batch_result = simulator.run_batch(
            presets=presets,
            count=args.count,
            randomize=args.random,
        )
        
        # Format output
        if args.output == "json":
            output = {
                "summary": batch_result.summary(),
                "results": [r.to_dict() for r in batch_result.results],
            }
            print(json.dumps(output, indent=2, default=str))
        else:
            for result in batch_result.results:
                if args.output == "markdown":
                    print(format_result_markdown(result))
                else:
                    print(format_result_text(result))
            
            print(format_batch_summary(batch_result))
        
        # Save if requested
        if args.save:
            for result in batch_result.results:
                simulator.save_results(result)
    
    logger.info("Simulation complete")


if __name__ == "__main__":
    main()
