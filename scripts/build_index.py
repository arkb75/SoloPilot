#!/usr/bin/env python3
"""
Build Index Script for SoloPilot Context Engine

Builds/updates the Chroma vector store by indexing:
- Existing dev agent outputs
- Sample milestones and planning outputs
- Project documentation and examples

This script is called by `make index` and automatically by `make dev` 
when using CONTEXT_ENGINE=lc_chroma and no index exists.
"""

import os
import sys
from pathlib import Path
from typing import List

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agents.dev.context_engine import get_context_engine


def find_milestone_directories() -> List[Path]:
    """Find all milestone directories to index."""
    milestone_dirs = []

    # Check for dev agent outputs
    dev_output_dir = project_root / "output" / "dev"
    if dev_output_dir.exists():
        for date_dir in dev_output_dir.iterdir():
            if date_dir.is_dir() and date_dir.name.startswith("20"):
                for milestone_dir in date_dir.iterdir():
                    if milestone_dir.is_dir() and (milestone_dir / "milestone.json").exists():
                        milestone_dirs.append(milestone_dir)

    # Check for planning outputs
    planning_output_dir = project_root / "analysis" / "planning"
    if planning_output_dir.exists():
        for date_dir in planning_output_dir.iterdir():
            if date_dir.is_dir() and date_dir.name.startswith("20"):
                # Planning outputs contain milestone structure
                if (date_dir / "development_plan.json").exists():
                    milestone_dirs.append(date_dir)

    # Check for sample milestones (if any exist)
    samples_dir = project_root / "sample_milestones"
    if samples_dir.exists():
        for milestone_dir in samples_dir.iterdir():
            if milestone_dir.is_dir() and (milestone_dir / "milestone.json").exists():
                milestone_dirs.append(milestone_dir)

    return milestone_dirs


def build_index():
    """Build the context engine index."""
    print("🗂️  Building context engine vector store...")

    # Check if we should use ChromaDB
    if os.getenv("NO_NETWORK") == "1":
        print("⚠️  NO_NETWORK=1 detected, skipping index build (would use legacy engine)")
        return

    if os.getenv("CONTEXT_ENGINE", "legacy") != "lc_chroma":
        print("ℹ️  CONTEXT_ENGINE not set to 'lc_chroma', skipping index build")
        return

    try:
        # Get LangChain + Chroma engine
        engine = get_context_engine("lc_chroma", persist_directory="./vector_store")

        # Find milestone directories to index
        milestone_dirs = find_milestone_directories()

        if not milestone_dirs:
            print("📂 No milestone directories found to index")
            print("💡 Tip: Run the dev agent to generate some milestones first")
            return

        print(f"📂 Found {len(milestone_dirs)} milestone directories to index:")
        for milestone_dir in milestone_dirs:
            print(f"   • {milestone_dir}")

        # Index each milestone
        indexed_count = 0
        for milestone_dir in milestone_dirs:
            try:
                print(f"🔍 Indexing {milestone_dir.name}...")
                # Build context to trigger indexing
                context, metadata = engine.build_context(milestone_dir, "")
                print(
                    f"   ✅ Indexed: {metadata.get('context_sections', [])} sections, "
                    f"{metadata.get('token_count', 0)} tokens"
                )
                indexed_count += 1
            except Exception as e:
                print(f"   ⚠️  Failed to index {milestone_dir}: {e}")

        # Get final stats
        engine_info = engine.get_engine_info()
        stats = engine_info.get("stats", {})

        print("\n✅ Index build complete!")
        print(f"   • Processed: {indexed_count}/{len(milestone_dirs)} milestone directories")
        print(f"   • Total documents: {stats.get('total_documents', 'unknown')}")
        print(f"   • Engine: {stats.get('engine', 'unknown')}")
        print(f"   • Storage: {stats.get('persist_directory', 'unknown')}")

    except Exception as e:
        print(f"❌ Index build failed: {e}")
        print("💡 Try: pip install chromadb")
        sys.exit(1)


if __name__ == "__main__":
    build_index()
