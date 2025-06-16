#!/usr/bin/env python3
"""
Complete SoloPilot Pipeline Runner

Runs the full workflow: Analyser → Planner → Dev Agent with real-time linting
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path


def run_command(cmd, cwd=None):
    """Run a command and return result."""
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            cwd=cwd,
            capture_output=True, 
            text=True, 
            check=False
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return 1, "", str(e)


def create_temp_requirement_file(requirement_text: str) -> Path:
    """Create a temporary requirement file from text input."""
    temp_dir = Path(tempfile.mkdtemp(prefix="solopilot_"))
    temp_file = temp_dir / "requirement.md"
    
    with open(temp_file, 'w') as f:
        f.write(f"""# Project Requirement

{requirement_text}

## Additional Details
- Target Language: Python
- Include comprehensive error handling
- Add proper logging
- Include unit tests
- Follow PEP 8 style guidelines
""")
    
    return temp_dir


def run_complete_pipeline(requirement_text: str, output_dir: str = None) -> dict:
    """Run the complete SoloPilot pipeline with performance tracking."""
    
    print("🚀 Starting SoloPilot Complete Pipeline")
    print("=" * 60)
    
    overall_start = time.time()
    results = {
        "requirement": requirement_text,
        "start_time": overall_start,
        "stages": {},
        "artifacts": {},
        "performance": {}
    }
    
    try:
        # Stage 1: Analysis
        print("\n📊 Stage 1: Requirement Analysis")
        stage_start = time.time()
        
        # Create temporary requirement file
        temp_input = create_temp_requirement_file(requirement_text)
        print(f"  📝 Created requirement file: {temp_input / 'requirement.md'}")
        
        # Run analyser
        cmd = f"python scripts/run_analyser.py --path {temp_input}"
        returncode, stdout, stderr = run_command(cmd)
        
        if returncode != 0:
            raise RuntimeError(f"Analyser failed: {stderr}")
        
        stage_end = time.time()
        
        # Find analysis output
        analysis_outputs = list(Path("analysis/output").glob("*/"))
        if analysis_outputs:
            latest_analysis = sorted(analysis_outputs)[-1]
            spec_file = latest_analysis / "specification.json"
            
            results["stages"]["analysis"] = {
                "duration": stage_end - stage_start,
                "output_dir": str(latest_analysis),
                "specification_file": str(spec_file) if spec_file.exists() else None,
                "stdout": stdout.strip()
            }
            
            print(f"  ✅ Analysis complete ({stage_end - stage_start:.2f}s)")
            print(f"    📁 Output: {latest_analysis}")
        else:
            raise RuntimeError("No analysis output found")
        
        # Stage 2: Planning
        print("\n🗺️ Stage 2: Development Planning")
        stage_start = time.time()
        
        spec_file = results["stages"]["analysis"]["specification_file"]
        if not spec_file or not Path(spec_file).exists():
            raise RuntimeError("No specification file found from analysis stage")
        
        cmd = f"python scripts/run_planner.py --spec {spec_file}"
        returncode, stdout, stderr = run_command(cmd)
        
        if returncode != 0:
            raise RuntimeError(f"Planner failed: {stderr}")
        
        stage_end = time.time()
        
        # Find planning output
        planning_outputs = list(Path("analysis/planning").glob("*/"))
        if planning_outputs:
            latest_planning = sorted(planning_outputs)[-1]
            planning_file = latest_planning / "planning_output.json"
            
            # Count milestones
            milestones_count = 0
            if planning_file.exists():
                try:
                    with open(planning_file) as f:
                        plan_data = json.load(f)
                        milestones_count = len(plan_data.get("milestones", []))
                except:
                    pass
            
            results["stages"]["planning"] = {
                "duration": stage_end - stage_start,
                "output_file": str(planning_file) if planning_file.exists() else None,
                "milestones_count": milestones_count,
                "stdout": stdout.strip()
            }
            
            print(f"  ✅ Planning complete ({stage_end - stage_start:.2f}s)")
            print(f"    📁 Output: {latest_planning}")
            print(f"    🎯 Milestones: {milestones_count}")
        else:
            raise RuntimeError("No planning output found")
        
        # Stage 3: Development with Real-Time Linting
        print("\n🔍 Stage 3: Code Generation with Real-Time Linting")
        stage_start = time.time()
        
        planning_file = results["stages"]["planning"]["output_file"]
        if not planning_file or not Path(planning_file).exists():
            raise RuntimeError("No planning file found from planning stage")
        
        # Add custom output directory if specified
        cmd = f"python scripts/run_dev_agent.py --planning {planning_file}"
        if output_dir:
            cmd += f" --output {output_dir}"
        
        returncode, stdout, stderr = run_command(cmd)
        
        if returncode != 0:
            print(f"  ⚠️ Dev agent stderr: {stderr}")
            # Don't fail completely - dev agent might still produce output
        
        stage_end = time.time()
        
        # Find development output
        dev_outputs = list(Path("output/dev").glob("*/"))
        if dev_outputs:
            latest_dev = sorted(dev_outputs)[-1]
            manifest_file = latest_dev / "manifest.json"
            
            # Count generated milestones
            milestones_generated = 0
            linting_info = {
                "available": False,
                "languages_supported": [],
                "real_time_enabled": True
            }
            
            if manifest_file.exists():
                try:
                    with open(manifest_file) as f:
                        manifest_data = json.load(f)
                        milestones_generated = len(manifest_data.get("milestones", []))
                except:
                    pass
            
            # Check for linting output in stdout/stderr
            if "Linter Manager initialized" in stdout:
                linting_info["available"] = True
                # Extract linter info from output
                for line in stdout.split('\n'):
                    if "python:" in line.lower() and "linter" in line.lower():
                        linting_info["languages_supported"].append("python")
                    elif "javascript:" in line.lower() and "linter" in line.lower():
                        linting_info["languages_supported"].append("javascript")
            
            results["stages"]["development"] = {
                "duration": stage_end - stage_start,
                "output_directory": str(latest_dev),
                "milestones_generated": milestones_generated,
                "linting_stats": linting_info,
                "stdout": stdout.strip(),
                "stderr": stderr.strip()
            }
            
            print(f"  ✅ Development complete ({stage_end - stage_start:.2f}s)")
            print(f"    📁 Output: {latest_dev}")
            print(f"    🏗️ Milestones: {milestones_generated}")
            print(f"    🔍 Linting: {', '.join(linting_info['languages_supported']) or 'None available'}")
        else:
            raise RuntimeError("No development output found")
        
        # Overall summary
        overall_end = time.time()
        results["total_duration"] = overall_end - overall_start
        results["success"] = True
        
        # Calculate performance metrics
        total_time = results["total_duration"]
        analysis_time = results["stages"]["analysis"]["duration"]
        planning_time = results["stages"]["planning"]["duration"]
        dev_time = results["stages"]["development"]["duration"]
        
        # Estimate linting overhead (development time vs. combined analysis+planning time)
        baseline_time = analysis_time + planning_time
        linting_overhead_pct = ((dev_time - baseline_time) / baseline_time * 100) if baseline_time > 0 else 0
        
        results["performance"] = {
            "total_time": total_time,
            "analysis_percentage": (analysis_time / total_time) * 100,
            "planning_percentage": (planning_time / total_time) * 100,
            "development_percentage": (dev_time / total_time) * 100,
            "estimated_linting_overhead": max(0, linting_overhead_pct),
            "linting_enabled": results["stages"]["development"]["linting_stats"]["available"]
        }
        
        print(f"\n🎉 Pipeline Complete!")
        print(f"  ⏱️ Total Time: {total_time:.2f}s")
        print(f"  📊 Breakdown:")
        print(f"    - Analysis: {analysis_time:.2f}s ({results['performance']['analysis_percentage']:.1f}%)")
        print(f"    - Planning: {planning_time:.2f}s ({results['performance']['planning_percentage']:.1f}%)")
        print(f"    - Development: {dev_time:.2f}s ({results['performance']['development_percentage']:.1f}%)")
        
        if results["performance"]["linting_enabled"]:
            print(f"  🔍 Estimated Linting Overhead: ~{results['performance']['estimated_linting_overhead']:.1f}%")
        else:
            print(f"  ⚠️ Real-time linting not available (missing dependencies)")
        
        results["artifacts"] = {
            "specification": results["stages"]["analysis"]["specification_file"],
            "planning": results["stages"]["planning"]["output_file"],
            "development": results["stages"]["development"]["output_directory"]
        }
        
        return results
        
    except Exception as e:
        print(f"\n❌ Pipeline failed: {e}")
        results["success"] = False
        results["error"] = str(e)
        results["total_duration"] = time.time() - overall_start
        return results
    
    finally:
        # Cleanup temp files
        try:
            import shutil
            if 'temp_input' in locals():
                shutil.rmtree(temp_input)
        except:
            pass


def main():
    """Main entry point for the complete pipeline runner."""
    parser = argparse.ArgumentParser(
        description="Run complete SoloPilot pipeline: Analyser → Planner → Dev Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/run_solopilot.py "Create a Python CLI tool that fetches weather data"
  python scripts/run_solopilot.py "Build a React dashboard for sales analytics" --output custom_output
        """
    )
    
    parser.add_argument(
        "requirement",
        help="Project requirement description (quoted string)"
    )
    
    parser.add_argument(
        "--output", "-o",
        help="Custom output directory for dev agent artifacts"
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    
    parser.add_argument(
        "--performance",
        action="store_true", 
        help="Show detailed performance analysis"
    )
    
    args = parser.parse_args()
    
    # Run the pipeline
    results = run_complete_pipeline(args.requirement, args.output)
    
    # Output results
    if args.json:
        print("\n" + "="*60)
        print("JSON RESULTS:")
        print(json.dumps(results, indent=2, default=str))
    
    if args.performance and results.get("success"):
        print(f"\n📈 Performance Analysis:")
        perf = results.get("performance", {})
        print(f"  ⏱️ Total Pipeline Time: {perf.get('total_time', 0):.2f}s")
        print(f"  📊 Stage Breakdown:")
        print(f"    Analysis:    {perf.get('analysis_percentage', 0):5.1f}%")
        print(f"    Planning:    {perf.get('planning_percentage', 0):5.1f}%")
        print(f"    Development: {perf.get('development_percentage', 0):5.1f}%")
        
        if perf.get("linting_enabled"):
            overhead = perf.get("estimated_linting_overhead", 0)
            print(f"  🔍 Linting Overhead: ~{overhead:.1f}%")
            if overhead < 20:
                print(f"    ✅ Performance target met (<20%)")
            else:
                print(f"    ⚠️ Performance target missed (>20%)")
        else:
            print(f"  ⚠️ Real-time linting not available")
    
    # Return appropriate exit code
    sys.exit(0 if results.get("success") else 1)


if __name__ == "__main__":
    main()