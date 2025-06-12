#!/usr/bin/env python3
"""
Context Packer for SoloPilot Dev Agent.
Assembles rich prompts with milestone data, design guidelines, and package manifests.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional


def build_context(milestone_path: Path) -> str:
    """
    Assemble a rich prompt for Claude containing:
    • the milestone JSON
    • any design_guidelines/*.md snippets
    • package manifests in the milestone folder (package.json, requirements.txt ...)
    Returns **one** large string ready to prepend to the main prompt.
    """
    context_parts = []

    # 1. Load milestone JSON if it exists
    milestone_json_path = milestone_path / "milestone.json"
    if milestone_json_path.exists():
        try:
            with open(milestone_json_path, "r") as f:
                milestone_data = json.load(f)
            context_parts.append(
                f"## Milestone Context\n```json\n{json.dumps(milestone_data, indent=2)}\n```\n"
            )
        except (json.JSONDecodeError, OSError) as e:
            context_parts.append(f"## Milestone Context\n(Failed to load milestone.json: {e})\n")

    # 2. Look for design guidelines in design_guidelines/ directory
    design_guidelines_dir = Path("design_guidelines")
    if design_guidelines_dir.exists() and design_guidelines_dir.is_dir():
        guidelines = _collect_design_guidelines(design_guidelines_dir)
        if guidelines:
            context_parts.append("## Design Guidelines\n")
            context_parts.extend(guidelines)
            context_parts.append("")  # Empty line after guidelines

    # 3. Collect package manifests from the milestone folder
    package_manifests = _collect_package_manifests(milestone_path)
    if package_manifests:
        context_parts.append("## Package Manifests\n")
        context_parts.extend(package_manifests)
        context_parts.append("")  # Empty line after manifests

    # 4. Add project structure context if available
    project_structure = _collect_project_structure(milestone_path)
    if project_structure:
        context_parts.append("## Project Structure\n")
        context_parts.append(project_structure)
        context_parts.append("")

    # Join all parts and add separator
    if context_parts:
        context_parts.append("---\n")  # Separator before main prompt

    return "\n".join(context_parts)


def _collect_design_guidelines(guidelines_dir: Path) -> List[str]:
    """Collect all .md files from design_guidelines directory."""
    guidelines = []

    try:
        for md_file in sorted(guidelines_dir.glob("*.md")):
            try:
                with open(md_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    guidelines.append(f"### {md_file.stem.replace('_', ' ').title()}\n{content}\n")
            except OSError as e:
                guidelines.append(f"### {md_file.name}\n(Failed to read: {e})\n")
    except OSError:
        # Directory not accessible
        pass

    return guidelines


def _collect_package_manifests(milestone_path: Path) -> List[str]:
    """Collect package manifest files from the milestone directory."""
    manifests = []

    # Common package manifest files to look for
    manifest_files = [
        "package.json",  # Node.js
        "requirements.txt",  # Python
        "Pipfile",  # Python (pipenv)
        "pyproject.toml",  # Python (modern)
        "pom.xml",  # Java (Maven)
        "build.gradle",  # Java/Kotlin (Gradle)
        "Cargo.toml",  # Rust
        "go.mod",  # Go
        "composer.json",  # PHP
        "Gemfile",  # Ruby
    ]

    for manifest_name in manifest_files:
        manifest_path = milestone_path / manifest_name
        if manifest_path.exists() and manifest_path.is_file():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content:
                    manifests.append(f"### {manifest_name}\n```\n{content}\n```\n")
            except OSError as e:
                manifests.append(f"### {manifest_name}\n(Failed to read: {e})\n")

    return manifests


def _collect_project_structure(milestone_path: Path) -> Optional[str]:
    """Collect project structure information from README or structure files."""
    structure_files = ["README.md", "STRUCTURE.md", "PROJECT.md"]

    for structure_file in structure_files:
        structure_path = milestone_path / structure_file
        if structure_path.exists() and structure_path.is_file():
            try:
                with open(structure_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content and len(content) < 5000:  # Limit size to avoid overwhelming prompt
                    return f"```markdown\n{content}\n```\n"
            except OSError:
                continue

    return None


def get_context_summary(context: str) -> Dict[str, int]:
    """Get a summary of what was included in the context."""
    summary = {
        "milestone_json": 1 if "## Milestone Context" in context else 0,
        "design_guidelines": context.count("### ") if "## Design Guidelines" in context else 0,
        "package_manifests": (
            context.count("```") - 1 if "## Package Manifests" in context else 0
        ),  # -1 for structure
        "project_structure": 1 if "## Project Structure" in context else 0,
        "total_chars": len(context),
    }
    return summary
