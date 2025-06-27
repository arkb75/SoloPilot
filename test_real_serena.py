#!/usr/bin/env python3
"""
Test script for real Serena LSP integration.
"""

import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from agents.dev.context_engine.serena_engine import SerenaContextEngine


def test_real_serena():
    """Test real Serena integration."""
    print("🧪 Testing Real Serena LSP Integration")
    print("=" * 50)

    # Initialize engine
    print("1. Initializing Serena context engine...")
    engine = SerenaContextEngine(project_root=Path.cwd())

    # Wait for initialization
    time.sleep(3)

    # Test engine info
    print("\n2. Getting engine info...")
    info = engine.get_engine_info()
    print(f"   Engine: {info['engine']}")
    print(f"   Serena Available: {info['serena_available']}")

    # Test symbol finding
    print("\n3. Testing symbol finding...")
    symbol = engine.find_symbol("SerenaContextEngine")
    if symbol:
        print(f"   ✅ Found symbol: {symbol['name']}")
        print(f"   Source: {symbol.get('source', 'unknown')}")
    else:
        print("   ❌ Symbol not found")

    # Test getting file symbols
    print("\n4. Testing file symbol overview...")
    test_file = Path(__file__)
    symbols = engine.get_symbols_overview(test_file)
    print(f"   Found {len(symbols)} symbols in {test_file.name}")
    for sym in symbols:
        print(f"   - {sym['type']}: {sym['name']}")

    # Test context building
    print("\n5. Testing context building...")
    milestone_dir = Path("analysis/output").glob("20*")
    milestone_paths = list(milestone_dir)

    if milestone_paths:
        latest_milestone = sorted(milestone_paths)[-1]
        context, metadata = engine.build_context(latest_milestone, "Test context building")
        print(f"   Context length: {len(context)} chars")
        print(f"   Engine: {metadata['engine']}")
        print(f"   Symbols found: {metadata.get('symbols_found', 0)}")
        print(f"   Tokens estimated: {metadata.get('tokens_estimated', 0)}")
    else:
        print("   ⚠️ No milestone directory found for testing")

    print("\n✅ Test completed!")


if __name__ == "__main__":
    test_real_serena()
