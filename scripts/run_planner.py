#!/usr/bin/env python3
"""
SoloPilot Project Planner CLI

Command-line interface for converting requirement specifications into project plans.
Supports specification.json files from the analyser and generates structured planning output.

Usage:
    python scripts/run_planner.py --spec ./analysis/output/20250607_183600/specification.json
    python scripts/run_planner.py --spec ./path/to/spec.json --output ./custom_planning
    python scripts/run_planner.py --spec specification.json --config ./config/model_config.yaml
"""

import argparse
import sys
import os
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.planning.planner import ProjectPlanner


def find_latest_specification(base_dir: str = "analysis/output") -> str:
    """Find the most recent specification.json file."""
    output_dir = Path(base_dir)
    
    if not output_dir.exists():
        raise FileNotFoundError(f"Output directory not found: {output_dir}")
    
    # Find all specification.json files
    spec_files = list(output_dir.glob("*/specification.json"))
    
    if not spec_files:
        raise FileNotFoundError(f"No specification.json files found in {output_dir}")
    
    # Sort by modification time and return the latest
    latest_spec = max(spec_files, key=lambda f: f.stat().st_mtime)
    return str(latest_spec)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SoloPilot Project Planner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --spec ./analysis/output/20250607_183600/specification.json
  %(prog)s --spec ./custom_spec.json --output ./planning_results
  %(prog)s --latest  # Use most recent specification
  %(prog)s --spec spec.json --config ./config/model_config.yaml
        """
    )
    
    # Input arguments
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        '--spec', 
        help='Path to specification.json file from analyser'
    )
    input_group.add_argument(
        '--latest',
        action='store_true',
        help='Use the most recent specification.json from analysis/output'
    )
    
    # Configuration arguments
    parser.add_argument(
        '--config',
        help='Path to model configuration YAML file',
        default=None
    )
    parser.add_argument(
        '--output',
        help='Output directory for planning results',
        default='analysis/planning'
    )
    
    # Parse arguments
    args = parser.parse_args()
    
    try:
        print("🔧 SoloPilot Project Planner")
        print("=" * 50)
        
        # Determine specification file
        if args.latest:
            spec_path = find_latest_specification()
            print(f"📖 Using latest specification: {spec_path}")
        else:
            spec_path = args.spec
            if not Path(spec_path).exists():
                raise FileNotFoundError(f"Specification file not found: {spec_path}")
        
        # Initialize planner
        planner = ProjectPlanner(
            config_path=args.config,
            output_dir=args.output
        )
        
        # Run planning
        session_dir = planner.plan_project(spec_path)
        
        print("\n" + "=" * 50)
        print(f"📂 Planning Results: {session_dir}")
        print("🎉 Ready for development!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()