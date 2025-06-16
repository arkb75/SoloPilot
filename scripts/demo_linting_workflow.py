#!/usr/bin/env python3
"""
Demo script for real-time linting workflow in SoloPilot Dev Agent.

This script demonstrates:
1. Code generation with real-time linting feedback
2. Automatic error correction iterations
3. SonarCloud project auto-provisioning
"""

import json
import os
import tempfile
from pathlib import Path

from agents.dev.dev_agent import DevAgent
from utils.linter_integration import LinterManager
from utils.sonarcloud_integration import SonarCloudClient


def demo_linting_workflow():
    """Demonstrate the real-time linting workflow."""
    print("🚀 SoloPilot Linting Workflow Demo")
    print("=" * 60)
    
    # 1. Initialize components
    print("\n📦 Initializing components...")
    
    # Initialize linter manager
    linter_manager = LinterManager()
    print(f"✅ LinterManager: {linter_manager.get_available_languages()}")
    
    # Initialize SonarCloud client
    sonar_client = SonarCloudClient()
    print(f"✅ SonarCloud: Available={sonar_client.is_available()}, Org={sonar_client.organization}")
    
    # 2. Demo Git URL parsing and project creation
    print("\n🔍 Testing SonarCloud Auto-Provisioning...")
    test_git_url = "https://github.com/demo-client/ai-chatbot.git"
    parsed = SonarCloudClient.parse_git_url(test_git_url)
    if parsed:
        print(f"  📋 Parsed Git URL: {parsed['owner']}/{parsed['repo']} → {parsed['project_key']}")
        
        if sonar_client.is_available():
            print(f"  🔨 Would create SonarCloud project: {parsed['project_key']}")
            # Note: Not actually creating to avoid API calls in demo
        else:
            print(f"  ⚠️ SonarCloud unavailable (set SONAR_TOKEN to test)")
    
    # 3. Demo real-time linting on sample code
    print("\n🔍 Testing Real-Time Linting...")
    
    # Sample Python code with intentional issues
    sample_code = '''
import os
import sys
import json

def process_user_data(data):
    # Security issue: eval usage
    result = eval(data)
    
    # Type issue: inconsistent return types
    if result > 10:
        return "high"
    else:
        return 42
    
    # Unused variable
    unused_var = "will trigger warning"

# Style issue: missing type hints
def calculate_total(items):
    total = 0
    for item in items:
        total += item
    return total

# Unused import will be flagged
password = "hardcoded_secret"  # Security issue
'''
    
    if "python" in linter_manager.get_available_languages():
        print("  📝 Linting sample Python code...")
        
        results = linter_manager.lint_code(sample_code, "python", "demo.py")
        summary = linter_manager.get_summary(results)
        
        print(f"  📊 Results: {summary['total_errors']} errors, {summary['total_warnings']} warnings")
        
        for result in results:
            print(f"    {result.get_issues_summary()}")
        
        if linter_manager.has_critical_errors(results):
            print("  🔧 Would generate correction prompt for AI...")
            correction_prompt = linter_manager.generate_correction_prompt(results, sample_code)
            print(f"    Prompt length: {len(correction_prompt)} characters")
            print(f"    First 200 chars: {correction_prompt[:200]}...")
        else:
            print("  ✅ No critical errors found!")
    
    # 4. Demo Dev Agent initialization with linting
    print("\n🤖 Testing Dev Agent with Linting...")
    try:
        # Set offline mode to avoid API calls
        os.environ["NO_NETWORK"] = "1"
        
        dev_agent = DevAgent()
        if dev_agent.linter_manager:
            print("  ✅ Dev Agent initialized with linting support")
            print(f"  📋 Supported languages: {dev_agent.linter_manager.get_available_languages()}")
            
            # Test the _generate_with_linting method with a simple prompt
            test_prompt = """
Generate a simple Python function that adds two numbers.
Make sure to include proper type hints and error handling.
"""
            
            print("  🔍 Testing code generation with linting (using fake provider)...")
            
            # This will use the fake provider due to NO_NETWORK=1
            try:
                generated_code = dev_agent._generate_with_linting(test_prompt, "python", max_iterations=2)
                print(f"  ✅ Generated code ({len(generated_code)} chars)")
                print(f"  📄 Sample: {generated_code[:100]}...")
            except Exception as e:
                print(f"  ⚠️ Code generation test failed: {e}")
        else:
            print("  ⚠️ Dev Agent linting not initialized")
            
    except Exception as e:
        print(f"  ❌ Dev Agent initialization failed: {e}")
    finally:
        # Clean up
        if "NO_NETWORK" in os.environ:
            del os.environ["NO_NETWORK"]
    
    # 5. Demo end-to-end workflow simulation
    print("\n🎯 End-to-End Workflow Summary:")
    print("  1. 📨 Client requests: 'Build an AI chatbot'")
    print("  2. 🧠 Analyser → Planner → Dev Agent processes request")
    print("  3. 🔍 Dev Agent generates code with real-time linting:")
    print("     • Ruff checks style and errors")
    print("     • MyPy validates types (if available)")
    print("     • Bandit scans for security issues (if available)")
    print("     • AI self-corrects based on linter feedback")
    print("  4. 📤 Push code to client repository")
    print("  5. 🔨 Auto-create SonarCloud project: demo-client_ai-chatbot")
    print("  6. 📊 SonarCloud analyzes pushed code")
    print("  7. 🤖 AI Reviewer aggregates: Linter + SonarCloud + AI insights")
    print("  8. 💬 Post comprehensive review to GitHub PR")
    
    print("\n✨ Workflow Benefits:")
    print("  • ⚡ Real-time feedback during code generation")
    print("  • 🛡️ Security scanning with Bandit")
    print("  • 🎯 Type safety with MyPy")
    print("  • 🎨 Code style consistency with Ruff")
    print("  • 🔄 Automatic error correction (max 3 iterations)")
    print("  • 🏭 Zero-touch SonarCloud project provisioning")
    print("  • 📈 Comprehensive quality analysis")
    
    print("\n" + "=" * 60)
    print("🎉 Demo completed!")


if __name__ == "__main__":
    demo_linting_workflow()