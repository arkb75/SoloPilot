#!/usr/bin/env python3
"""
Serena Live Integration Test - NO MOCKS ALLOWED

This test verifies REAL Serena LSP integration without any mocking.
It must communicate with an actual running serena-mcp-server process.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


class TestSerenaLiveIntegration:
    """Test real Serena LSP integration - no mocks permitted."""

    @classmethod
    def setup_class(cls):
        """Verify Serena server is running."""
        # Check if we should skip in offline CI
        if os.getenv("CI_OFFLINE") == "1":
            pytest.skip("Skipping live Serena tests in offline CI")

        # Try to connect to Serena server
        try:
            result = subprocess.run(
                ["pgrep", "-f", "serena-mcp-server"], capture_output=True, text=True
            )
            if result.returncode != 0:
                pytest.fail(
                    "Serena MCP server is not running. Start it with: serena-mcp-server --port 9123"
                )
        except Exception as e:
            pytest.fail(f"Cannot verify Serena server status: {e}")

    def test_no_mocks_imported(self):
        """Ensure no mock libraries are imported."""
        import sys

        mock_modules = [m for m in sys.modules if "mock" in m.lower()]
        assert len(mock_modules) == 0, f"Mock modules detected: {mock_modules}. NO MOCKS ALLOWED!"

    def test_real_serena_import(self):
        """Test that Serena can actually be imported."""
        try:
            # This should work if Serena is properly installed
            result = subprocess.run(
                [sys.executable, "-c", "from serena import find_symbol; print('SUCCESS')"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert result.returncode == 0, f"Cannot import Serena: {result.stderr}"
            assert "SUCCESS" in result.stdout
        except subprocess.TimeoutExpired:
            pytest.fail("Serena import timed out - is it properly installed?")

    def test_real_symbol_lookup(self):
        """Test real symbol lookup through Serena LSP."""
        from src.agents.dev.context_engine.serena_engine import SerenaContextEngine

        # Create engine with test project
        test_project = Path(__file__).parent.parent  # SoloPilot root
        engine = SerenaContextEngine(project_root=test_project)

        # This MUST use real Serena, not fallback
        symbol_info = engine.find_symbol("SerenaContextEngine")

        # Verify we got real results
        assert symbol_info is not None, "Symbol lookup returned None"
        assert "file" in symbol_info, "Missing file information"
        assert "line" in symbol_info, "Missing line information"
        assert symbol_info["line"] > 0, "Invalid line number"
        assert "serena_engine.py" in symbol_info["file"], "Wrong file found"

        # Verify it's not using the fallback
        # The fallback uses regex and would find the class definition
        # Real Serena should provide more detailed information
        assert "full_definition" in symbol_info, "Missing full definition (fallback indicator)"

    def test_real_json_rpc_communication(self):
        """Test actual JSON-RPC communication with Serena server."""
        from src.agents.dev.context_engine.serena_engine import SerenaContextEngine

        test_project = Path(__file__).parent.parent
        engine = SerenaContextEngine(project_root=test_project)

        # Check that the engine has a real server process
        assert hasattr(engine, "serena_process"), "No Serena process found"
        assert engine.serena_process is not None, "Serena process is None"
        assert engine.serena_process.poll() is None, "Serena process is not running"

        # Test a JSON-RPC request
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "workspace/symbol",
            "params": {"query": "BaseProvider"},
        }

        # This should go through real JSON-RPC
        response = engine._send_request(request)
        assert response is not None, "No response from Serena server"
        assert "result" in response, "Invalid JSON-RPC response"

    def test_benchmark_produces_real_metrics(self):
        """Test that benchmarks produce real, not estimated metrics."""
        from src.agents.dev.context_engine import LegacyContextEngine
        from src.agents.dev.context_engine.serena_engine import SerenaContextEngine

        test_project = Path(__file__).parent.parent
        test_milestone = test_project / "milestones" / "milestone-001"

        if not test_milestone.exists():
            test_milestone.mkdir(parents=True)
            milestone_data = {
                "name": "Test Milestone",
                "components": ["SerenaContextEngine", "BaseProvider"],
                "functions": ["find_symbol", "build_context"],
            }
            (test_milestone / "milestone.json").write_text(json.dumps(milestone_data))

        # Run both engines
        legacy = LegacyContextEngine()
        legacy_context, legacy_meta = legacy.build_context(test_milestone, "Test prompt")

        serena = SerenaContextEngine(project_root=test_project)
        serena_context, serena_meta = serena.build_context(test_milestone, "Test prompt")

        # Verify Serena provides real metrics
        assert serena_meta["engine"] == "serena_lsp", "Not using Serena engine"
        assert serena_meta["lsp_available"] is True, "LSP not available"
        assert serena_meta["symbols_found"] > 0, "No symbols found"

        # Save real benchmark results
        benchmark_dir = test_project / "benchmarks"
        benchmark_dir.mkdir(exist_ok=True)

        results = {
            "timestamp": time.time(),
            "legacy": {
                "context_length": len(legacy_context),
                "tokens_estimated": len(legacy_context) // 4,
            },
            "serena": {
                "context_length": len(serena_context),
                "tokens_estimated": serena_meta["tokens_estimated"],
                "symbols_found": serena_meta["symbols_found"],
                "response_time_ms": serena_meta["response_time_ms"],
            },
            "comparison": {
                "token_difference": len(legacy_context) // 4 - serena_meta["tokens_estimated"],
                "percentage_change": (
                    (len(serena_context) - len(legacy_context)) / len(legacy_context) * 100
                ),
            },
        }

        with open(benchmark_dir / "serena_vs_legacy.json", "w") as f:
            json.dump(results, f, indent=2)

        print("\n📊 Real Benchmark Results:")
        print(f"Legacy tokens: {results['legacy']['tokens_estimated']}")
        print(f"Serena tokens: {results['serena']['tokens_estimated']}")
        print(f"Change: {results['comparison']['percentage_change']:.1f}%")


if __name__ == "__main__":
    # Run with explicit no-mock verification
    pytest.main([__file__, "-v", "--tb=short", "--no-cov"])
