#!/usr/bin/env python3
"""Quick test of provider integration"""

from src.providers import get_provider
from src.agents.dev.dev_agent import DevAgent

print("=== Testing Provider Integration ===")

# Test 1: Direct provider usage
print("\n1. Testing direct provider usage:")
provider = get_provider("fake")
result = provider.generate_code("Create a simple function")
print(f"✅ Result length: {len(result)}")
print(f"✅ Contains code blocks: {'```' in result}")

# Test 2: Dev agent usage
print("\n2. Testing dev agent with provider:")
try:
    agent = DevAgent()
    test_result = agent._call_llm("Generate test code")
    print(f"✅ Dev agent result length: {len(test_result)}")
    print(f"✅ Dev agent contains code: {'```' in test_result}")
except Exception as e:
    print(f"❌ Dev agent error: {e}")

print("\n=== Integration Test Complete ===")
