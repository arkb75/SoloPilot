#!/usr/bin/env python3
"""
Demo script for SonarCloud integration with live tokens.

Shows how the enhanced reviewer incorporates SonarCloud findings.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.sonarcloud_integration import SonarCloudClient


def main():
    """Demo SonarCloud integration capabilities."""
    print("🎯 SoloPilot SonarCloud Integration Demo")
    print("=" * 50)
    
    # Initialize client
    client = SonarCloudClient()
    
    print(f"📊 Project Key: {client.project_key}")
    print(f"🏢 Organization: {client.organization}")
    print(f"🌐 Base URL: {client.base_url}")
    print(f"🔧 Token Available: {bool(client.token)}")
    print(f"📴 Offline Mode: {client.no_network}")
    print(f"✅ Integration Available: {client.is_available()}")
    print()
    
    if client.is_available():
        print("🔍 Fetching SonarCloud Data...")
        print("-" * 30)
        
        # Get project metrics
        print("📈 Fetching quality metrics...")
        metrics = client.get_project_metrics()
        if metrics:
            print(f"  ✅ Metrics retrieved:")
            print(f"     - Bugs: {metrics.get('bugs', 0)}")
            print(f"     - Vulnerabilities: {metrics.get('vulnerabilities', 0)}")
            print(f"     - Code Smells: {metrics.get('code_smells', 0)}")
            print(f"     - Coverage: {metrics.get('coverage', 0):.1f}%")
        else:
            print("  ❌ No metrics available (project may not exist yet)")
        print()
        
        # Get project issues
        print("🚨 Fetching project issues...")
        issues = client.get_project_issues()
        print(f"  📊 Found {len(issues)} issues")
        for i, issue in enumerate(issues[:3]):  # Show first 3
            print(f"     {i+1}. {issue.get('severity')} - {issue.get('message', 'No message')[:50]}")
        if len(issues) > 3:
            print(f"     ... and {len(issues) - 3} more issues")
        print()
        
        # Get quality gate status
        print("🚦 Fetching quality gate status...")
        quality_gate = client.get_quality_gate_status()
        if quality_gate:
            status = quality_gate.get('status', 'UNKNOWN')
            print(f"  🎯 Quality Gate: {status}")
        else:
            print("  ❌ No quality gate status available")
        print()
        
        # Generate comprehensive summary
        print("📋 Generating comprehensive review summary...")
        summary = client.generate_review_summary()
        if summary.get('available'):
            analysis = summary.get('analysis', {})
            print(f"  🎯 Overall Rating: {analysis.get('overall_rating', 'unknown').upper()}")
            print(f"  🚨 Critical Issues: {analysis.get('critical_issues', 0)}")
            
            if analysis.get('recommendations'):
                print("  💡 Recommendations:")
                for rec in analysis['recommendations'][:3]:
                    print(f"     - {rec}")
            
            if analysis.get('blockers'):
                print("  🚫 Blocking Issues:")
                for blocker in analysis['blockers']:
                    print(f"     - {blocker}")
        
    else:
        reason = "offline mode" if client.no_network else "missing token"
        print(f"⚠️  SonarCloud integration not available: {reason}")
        print()
        print("🎯 To enable live integration:")
        print("   1. Set SONAR_TOKEN environment variable")
        print("   2. Ensure project exists on SonarCloud")
        print("   3. Remove NO_NETWORK=1 if set")
    
    print()
    print("🎉 Demo complete!")
    print()
    print("📝 Integration Features:")
    print("   ✅ Live SonarCloud API integration")
    print("   ✅ Quality metrics and issue detection")
    print("   ✅ Blocking issue identification")
    print("   ✅ Graceful offline degradation") 
    print("   ✅ Enhanced AI review with SonarCloud findings")


if __name__ == "__main__":
    main()