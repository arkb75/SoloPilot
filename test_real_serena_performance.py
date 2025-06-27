#!/usr/bin/env python3
"""
Real Serena LSP Performance Validation

Tests actual performance improvements with real Serena MCP server.
"""

import json
import time
from pathlib import Path

from agents.dev.context_engine import LegacyContextEngine
from agents.dev.context_engine.serena_engine import SerenaContextEngine


def test_token_reduction():
    """Test real token reduction with Serena vs Legacy."""
    print("🔍 Testing Token Reduction: Serena vs Legacy")
    print("=" * 50)

    # Create test milestone
    milestone_path = Path("analysis/output").glob("20*")
    milestone_paths = list(milestone_path)

    if not milestone_paths:
        print("❌ No milestone directory found for testing")
        return

    latest_milestone = sorted(milestone_paths)[-1]
    test_prompt = "Implement user authentication system with JWT tokens and password hashing"

    # Test Legacy Engine
    print("1. Testing Legacy Context Engine...")
    legacy_start = time.time()
    legacy_engine = LegacyContextEngine()
    legacy_context, legacy_meta = legacy_engine.build_context(latest_milestone, test_prompt)
    legacy_time = (time.time() - legacy_start) * 1000
    legacy_tokens = len(legacy_context) // 4  # Simple token estimation

    print(f"   Legacy context length: {len(legacy_context):,} chars")
    print(f"   Legacy tokens estimated: {legacy_tokens:,}")
    print(f"   Legacy response time: {legacy_time:.1f}ms")

    # Test Real Serena Engine
    print("\n2. Testing Real Serena Context Engine...")
    serena_start = time.time()
    serena_engine = SerenaContextEngine(project_root=Path.cwd())

    # Wait for server to fully initialize
    time.sleep(3)

    serena_context, serena_meta = serena_engine.build_context(latest_milestone, test_prompt)
    serena_time = (time.time() - serena_start) * 1000
    serena_tokens = serena_meta.get("tokens_estimated", len(serena_context) // 4)

    print(f"   Serena context length: {len(serena_context):,} chars")
    print(f"   Serena tokens estimated: {serena_tokens:,}")
    print(f"   Serena response time: {serena_time:.1f}ms")
    print(f"   Serena symbols found: {serena_meta.get('symbols_found', 0)}")

    # Calculate improvements
    token_reduction = max(0, legacy_tokens - serena_tokens)
    reduction_percentage = (token_reduction / legacy_tokens * 100) if legacy_tokens > 0 else 0

    print("\n3. Performance Analysis")
    print(f"   Token reduction: {token_reduction:,} tokens ({reduction_percentage:.1f}%)")

    # Performance validation
    target_achieved = reduction_percentage >= 30.0
    print(
        f"   Target (30-50% reduction): {'✅ ACHIEVED' if target_achieved else '❌ NOT ACHIEVED'}"
    )

    if reduction_percentage > 0:
        print(f"   💰 Cost savings: ~{reduction_percentage:.1f}% fewer API tokens")

    # Time comparison
    time_improvement = max(0, legacy_time - serena_time)
    if time_improvement > 0:
        print(f"   ⚡ Speed improvement: {time_improvement:.1f}ms faster")

    # Save results
    results = {
        "timestamp": time.time(),
        "test": "real_token_reduction",
        "legacy": {
            "context_length": len(legacy_context),
            "tokens_estimated": legacy_tokens,
            "response_time_ms": legacy_time,
        },
        "serena": {
            "context_length": len(serena_context),
            "tokens_estimated": serena_tokens,
            "response_time_ms": serena_time,
            "symbols_found": serena_meta.get("symbols_found", 0),
            "engine": serena_meta.get("engine", "unknown"),
        },
        "performance": {
            "token_reduction": token_reduction,
            "reduction_percentage": reduction_percentage,
            "target_achieved": target_achieved,
            "time_improvement_ms": time_improvement,
        },
    }

    results_file = Path("real_serena_benchmark_results.json")
    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n📊 Results saved to {results_file}")

    # Cleanup
    if hasattr(serena_engine, "__del__"):
        serena_engine.__del__()


def test_complex_project_handling():
    """Test handling of complex project without timeouts."""
    print("\n🏗️ Testing Complex Project Handling")
    print("=" * 40)

    complex_prompt = """
    Implement a comprehensive microservices architecture with:
    - User authentication and authorization with OAuth2
    - Data processing pipelines with Redis queues
    - Real-time notifications via WebSockets
    - Multi-level caching with Redis and Memcached
    - Database migrations and connection pooling
    - API gateway with rate limiting
    - Monitoring, logging, and health checks
    - Error handling and circuit breakers
    - Automated testing and CI/CD integration
    - Docker containerization and Kubernetes deployment
    """

    # Test with Serena - should handle complex requests without timeout
    print("Testing complex project with Serena...")
    start_time = time.time()

    try:
        serena_engine = SerenaContextEngine(project_root=Path.cwd())
        time.sleep(2)  # Allow initialization

        # Create dummy milestone
        milestone_dir = Path.cwd() / "analysis" / "output"
        if not milestone_dir.exists():
            milestone_dir.mkdir(parents=True, exist_ok=True)

        # Use current project as milestone
        context, metadata = serena_engine.build_context(Path.cwd(), complex_prompt)
        response_time = (time.time() - start_time) * 1000

        print(f"   ✅ Complex request completed in {response_time:.1f}ms")
        print(f"   Context length: {len(context):,} chars")
        print(f"   Engine: {metadata.get('engine', 'unknown')}")

        # Validate no timeout (should be < 30s)
        timeout_ok = response_time < 30000
        print(f"   Timeout test: {'✅ PASSED' if timeout_ok else '❌ FAILED'}")

        return timeout_ok

    except Exception as e:
        print(f"   ❌ Complex request failed: {e}")
        return False


def main():
    """Run all performance tests."""
    print("🎯 Real Serena LSP Performance Validation")
    print("=" * 60)

    # Test 1: Token reduction
    test_token_reduction()

    # Test 2: Complex project handling
    success = test_complex_project_handling()

    print(f"\n🎉 Performance validation {'✅ PASSED' if success else '❌ FAILED'}")


if __name__ == "__main__":
    main()
