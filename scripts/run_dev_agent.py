#!/usr/bin/env python3
"""
SoloPilot Dev Agent CLI
Command-line interface for the dev agent that generates milestone-based code structure.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agents.dev.context7_bridge import Context7Bridge
from agents.dev.dev_agent import DevAgent


def main():
    parser = argparse.ArgumentParser(
        description="SoloPilot Dev Agent - Generate milestone-based code structure from planning output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process latest planning output
  python scripts/run_dev_agent.py
  
  # Process specific planning file
  python scripts/run_dev_agent.py --planning analysis/planning/20250608_014159/planning_output.json
  
  # Enable Context7 scouting
  C7_SCOUT=1 python scripts/run_dev_agent.py
  
  # Custom output directory
  python scripts/run_dev_agent.py --output ./my_output
  
  # Custom config
  python scripts/run_dev_agent.py --config ./custom_config.yaml
        """,
    )

    parser.add_argument(
        "--planning",
        type=str,
        help="Path to planning_output.json file (default: find latest in analysis/planning/)",
    )

    parser.add_argument(
        "--output",
        type=str,
        help="Output directory for generated code (default: output/dev/<timestamp>)",
    )

    parser.add_argument(
        "--config",
        type=str,
        default="config/model_config.yaml",
        help="Path to model configuration file (default: config/model_config.yaml)",
    )

    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")

    parser.add_argument(
        "--install-context7",
        action="store_true",
        help="Attempt to install Context7 globally via npm",
    )

    parser.add_argument(
        "--scout-status", action="store_true", help="Show Context7 bridge status and exit"
    )

    args = parser.parse_args()

    try:
        # Initialize Context7 bridge
        context7_bridge = Context7Bridge()

        # Handle Context7-specific commands
        if args.scout_status:
            status = context7_bridge.get_status()
            print("🔍 Context7 Bridge Status:")
            print(f"  Context7 Available: {'✅' if status['context7_available'] else '❌'}")
            print(f"  Environment Variable (C7_SCOUT): {'✅' if status['env_var_set'] else '❌'}")
            print(f"  Bridge Enabled: {'✅' if status['enabled'] else '❌'}")
            print(f"  Install Command: {status['install_command']}")
            return 0

        if args.install_context7:
            success = context7_bridge.install_context7()
            return 0 if success else 1

        # Initialize dev agent
        if args.verbose:
            print("🚀 Initializing SoloPilot Dev Agent...")
            print(f"📁 Config: {args.config}")

        if not os.path.exists(args.config):
            print(f"❌ Error: Config file not found: {args.config}")
            return 1

        dev_agent = DevAgent(config_path=args.config)

        # Find planning file
        planning_file = args.planning
        if not planning_file:
            planning_file = dev_agent.find_latest_planning_output()
            if not planning_file:
                print("❌ Error: No planning output found in analysis/planning/")
                print("💡 Run the planner first: make plan")
                return 1
            if args.verbose:
                print(f"📋 Using latest planning output: {planning_file}")

        if not os.path.exists(planning_file):
            print(f"❌ Error: Planning file not found: {planning_file}")
            return 1

        # Show Context7 status
        if context7_bridge.is_enabled():
            print("🔍 Context7 scouting enabled - enhanced insights will be included")
        elif os.getenv("C7_SCOUT", "0") == "1":
            print("⚠️  Context7 scouting requested but Context7 not available")
            print("💡 Run: npm install -g context7")

        # Process planning output
        manifest = dev_agent.process_planning_output(planning_file, args.output)

        # Enhance with Context7 insights if enabled
        if context7_bridge.is_enabled():
            print("🔍 Generating Context7 insights...")
            with open(planning_file, "r") as f:
                planning_data = json.load(f)

            for i, milestone in enumerate(planning_data["milestones"], 1):
                insights = context7_bridge.generate_milestone_insights(
                    milestone, planning_data.get("tech_stack", [])
                )

                if any(insights.values()):
                    # Update the README with insights
                    milestone_dir = Path(manifest["output_directory"]) / f"milestone-{i}"
                    readme_file = milestone_dir / "README.md"

                    if readme_file.exists():
                        with open(readme_file, "r") as f:
                            readme_content = f.read()

                        insights_section = context7_bridge.format_insights_for_readme(insights)
                        if insights_section:
                            with open(readme_file, "w") as f:
                                f.write(readme_content + insights_section)

        # Display results
        print("\n" + "=" * 60)
        print("🎉 Dev Agent Completed Successfully!")
        print("=" * 60)
        print(f"📂 Output Directory: {manifest['output_directory']}")
        print(f"🏗️  Project: {manifest['project_title']}")
        print(f"📊 Milestones Generated: {len(manifest['milestones'])}")
        print(f"🛠️  Tech Stack: {', '.join(manifest['tech_stack'])}")

        print("\n📁 Generated Structure:")
        for milestone in manifest["milestones"]:
            print(f"  📂 {milestone['directory']}/")
            print(f"    📄 {milestone['files']['implementation']} ({milestone['language']})")
            print(f"    🧪 {milestone['files']['test']}")
            print(f"    📖 {milestone['files']['readme']}")

        print("\n🧪 Unit Tests: unit_tests/integration.test.js")
        print("📋 Manifest: manifest.json")

        if args.verbose:
            print("\n📊 Detailed Manifest:")
            print(json.dumps(manifest, indent=2))

        print("\n💡 Next Steps:")
        print("  1. Review generated skeleton code in each milestone directory")
        print("  2. Implement TODO items marked in the code")
        print("  3. Expand unit tests as needed")
        print("  4. Run tests: make test")

        return 0

    except KeyboardInterrupt:
        print("\n⏹️  Dev agent interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
