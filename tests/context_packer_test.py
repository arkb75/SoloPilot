#!/usr/bin/env python3
"""
Unit tests for SoloPilot Context Packer.
Tests context assembly functionality for dev agent.
"""

import json
import shutil

# Add project root to path for imports
import sys
import tempfile
from pathlib import Path

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.agents.dev.context_packer import ContextPathError, build_context, get_context_summary


class TestContextPacker:
    """Test cases for context packer functionality."""

    @pytest.fixture
    def temp_milestone_dir(self):
        """Create a temporary milestone directory for testing."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def temp_guidelines_dir(self):
        """Create a temporary design guidelines directory for testing."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_build_context_empty_directory(self, temp_milestone_dir):
        """Test context building with empty milestone directory."""
        context = build_context(temp_milestone_dir)

        # Should return empty string when no context is available
        assert context == ""

    def test_build_context_with_milestone_json(self, temp_milestone_dir):
        """Test context building with milestone.json file."""
        # Create milestone.json
        milestone_data = {
            "name": "Test Milestone",
            "description": "A test milestone",
            "tasks": [
                {"name": "Task 1", "description": "First task"},
                {"name": "Task 2", "description": "Second task"},
            ],
        }

        milestone_json = temp_milestone_dir / "milestone.json"
        with open(milestone_json, "w") as f:
            json.dump(milestone_data, f, indent=2)

        context = build_context(temp_milestone_dir)

        # Should contain milestone context
        assert "## Milestone Context" in context
        assert "Test Milestone" in context
        assert "```json" in context
        assert "tasks" in context
        assert "---\n" in context

    def test_build_context_with_package_manifests(self, temp_milestone_dir):
        """Test context building with package manifest files."""
        # Create package.json
        package_json = {
            "name": "test-project",
            "version": "1.0.0",
            "dependencies": {"express": "^4.18.0", "react": "^18.2.0"},
        }

        package_file = temp_milestone_dir / "package.json"
        with open(package_file, "w") as f:
            json.dump(package_json, f, indent=2)

        # Create requirements.txt
        requirements_file = temp_milestone_dir / "requirements.txt"
        with open(requirements_file, "w") as f:
            f.write("flask==2.3.0\nrequests==2.28.0\npytesseract==0.3.10")

        context = build_context(temp_milestone_dir)

        # Should contain package manifests
        assert "## Package Manifests" in context
        assert "### package.json" in context
        assert "### requirements.txt" in context
        assert "express" in context
        assert "flask==2.3.0" in context
        assert "```" in context
        assert "---\n" in context

    def test_build_context_with_design_guidelines(self, temp_milestone_dir):
        """Test context building with design guidelines."""
        # Create design_guidelines directory
        guidelines_dir = Path("design_guidelines")
        guidelines_dir.mkdir(exist_ok=True)

        try:
            # Create some guideline files
            coding_standards = guidelines_dir / "coding_standards.md"
            with open(coding_standards, "w") as f:
                f.write(
                    "# Coding Standards\n\n- Use TypeScript\n- Follow ESLint rules\n- Write unit tests"
                )

            api_design = guidelines_dir / "api_design.md"
            with open(api_design, "w") as f:
                f.write("# API Design\n\n- RESTful endpoints\n- JSON responses\n- Error handling")

            context = build_context(temp_milestone_dir)

            # Should contain design guidelines
            assert "## Design Guidelines" in context
            assert "### Coding Standards" in context
            assert "### Api Design" in context
            assert "TypeScript" in context
            assert "RESTful endpoints" in context
            assert "---\n" in context

        finally:
            # Clean up
            shutil.rmtree(guidelines_dir, ignore_errors=True)

    def test_build_context_with_project_structure(self, temp_milestone_dir):
        """Test context building with project structure file."""
        # Create README.md with project structure
        readme_file = temp_milestone_dir / "README.md"
        with open(readme_file, "w") as f:
            f.write(
                """# Project Structure

```
src/
  components/
  pages/
  utils/
tests/
  unit/
  integration/
package.json
```
"""
            )

        context = build_context(temp_milestone_dir)

        # Should contain project structure
        assert "## Project Structure" in context
        assert "src/" in context
        assert "components/" in context
        assert "```markdown" in context
        assert "---\n" in context

    def test_build_context_comprehensive(self, temp_milestone_dir):
        """Test context building with all components."""
        # Create design_guidelines directory
        guidelines_dir = Path("design_guidelines")
        guidelines_dir.mkdir(exist_ok=True)

        try:
            # Create milestone.json
            milestone_data = {"name": "Full Test", "description": "Complete test"}
            milestone_json = temp_milestone_dir / "milestone.json"
            with open(milestone_json, "w") as f:
                json.dump(milestone_data, f)

            # Create package.json
            package_json = {"name": "full-test", "version": "1.0.0"}
            package_file = temp_milestone_dir / "package.json"
            with open(package_file, "w") as f:
                json.dump(package_json, f)

            # Create design guideline
            guideline_file = guidelines_dir / "style_guide.md"
            with open(guideline_file, "w") as f:
                f.write("# Style Guide\nUse camelCase for variables")

            # Create README
            readme_file = temp_milestone_dir / "README.md"
            with open(readme_file, "w") as f:
                f.write("# Project\nThis is a test project")

            context = build_context(temp_milestone_dir)

            # Should contain all sections
            assert "## Milestone Context" in context
            assert "## Design Guidelines" in context
            assert "## Package Manifests" in context
            assert "## Project Structure" in context
            assert "Full Test" in context
            assert "Style Guide" in context
            assert "full-test" in context
            assert "This is a test project" in context
            assert context.endswith("---\n")

        finally:
            # Clean up
            shutil.rmtree(guidelines_dir, ignore_errors=True)

    def test_build_context_invalid_json(self, temp_milestone_dir):
        """Test context building with invalid milestone.json."""
        # Create invalid JSON file
        milestone_json = temp_milestone_dir / "milestone.json"
        with open(milestone_json, "w") as f:
            f.write("{ invalid json }")

        context = build_context(temp_milestone_dir)

        # Should handle error gracefully
        assert "## Milestone Context" in context
        assert "Failed to load milestone.json" in context
        assert "---\n" in context

    def test_build_context_large_readme(self, temp_milestone_dir):
        """Test context building with oversized README (should be skipped)."""
        # Create very large README
        readme_file = temp_milestone_dir / "README.md"
        with open(readme_file, "w") as f:
            f.write("# Large Project\n" + "x" * 6000)  # Over 5000 char limit

        context = build_context(temp_milestone_dir)

        # Should not include the oversized README
        assert "## Project Structure" not in context
        assert "Large Project" not in context

    def test_get_context_summary(self, temp_milestone_dir):
        """Test context summary generation."""
        # Create a context with multiple components
        milestone_data = {"name": "Summary Test"}
        milestone_json = temp_milestone_dir / "milestone.json"
        with open(milestone_json, "w") as f:
            json.dump(milestone_data, f)

        package_file = temp_milestone_dir / "package.json"
        with open(package_file, "w") as f:
            json.dump({"name": "test"}, f)

        context = build_context(temp_milestone_dir)
        summary = get_context_summary(context)

        assert summary["milestone_json"] == 1
        assert summary["design_guidelines"] == 0
        assert summary["package_manifests"] >= 1
        assert summary["project_structure"] == 0
        assert summary["total_chars"] > 0

    def test_build_context_nonexistent_path(self):
        """Test context building with non-existent path."""
        nonexistent_path = Path("/nonexistent/path/milestone")
        context = build_context(nonexistent_path)

        # Should return empty string for non-existent path
        assert context == ""

    def test_build_context_missing_design_guidelines(self, temp_milestone_dir):
        """Test context building when design_guidelines directory doesn't exist."""
        # Ensure design_guidelines doesn't exist
        guidelines_dir = Path("design_guidelines")
        if guidelines_dir.exists():
            # Temporarily rename it
            temp_name = guidelines_dir.with_suffix(".temp")
            guidelines_dir.rename(temp_name)
            try:
                context = build_context(temp_milestone_dir)
                # Should not contain design guidelines section
                assert "## Design Guidelines" not in context
            finally:
                # Restore it
                temp_name.rename(guidelines_dir)
        else:
            context = build_context(temp_milestone_dir)
            # Should not contain design guidelines section
            assert "## Design Guidelines" not in context

    def test_build_context_empty_files(self, temp_milestone_dir):
        """Test context building with empty files."""
        # Create empty files
        empty_json = temp_milestone_dir / "milestone.json"
        empty_json.touch()

        empty_package = temp_milestone_dir / "package.json"
        empty_package.touch()

        context = build_context(temp_milestone_dir)

        # Should handle empty files gracefully
        assert "---\n" in context

    def test_build_context_valid_milestone_structure(self):
        """Test context building with proper milestone directory structure."""
        # Create a dummy milestone directory with proper structure
        base_dir = Path("output/dev/20250615_120000")
        milestone_dir = base_dir / "milestone-1"
        milestone_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Create milestone.json with some content
            milestone_data = {
                "name": "Test Milestone",
                "description": "A test milestone",
                "tasks": [{"name": "Task 1", "description": "First task"}],
            }

            milestone_json = milestone_dir / "milestone.json"
            with open(milestone_json, "w") as f:
                json.dump(milestone_data, f, indent=2)

            # Create a simple package.json for more context
            package_json = milestone_dir / "package.json"
            with open(package_json, "w") as f:
                json.dump({"name": "test-project", "version": "1.0.0"}, f)

            context = build_context(milestone_dir)

            # Assert token count > 0 (context should have content)
            assert len(context) > 0
            assert "## Milestone Context" in context
            assert "Test Milestone" in context
            assert "## Package Manifests" in context
            assert "test-project" in context

        finally:
            # Clean up
            shutil.rmtree(base_dir, ignore_errors=True)

    def test_build_context_invalid_milestone_path_structure(self):
        """Test context building with invalid milestone path structure."""
        # Create directory with wrong structure (not under output/dev/)
        wrong_dir = Path("wrong/structure/milestone-1")
        wrong_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Should raise ContextPathError for invalid structure
            with pytest.raises(ContextPathError) as exc_info:
                build_context(wrong_dir)

            assert "Invalid milestone path" in str(exc_info.value)
            assert "Expected format: output/dev/<run-stamp>/milestone-*" in str(exc_info.value)

        finally:
            # Clean up
            shutil.rmtree(Path("wrong"), ignore_errors=True)

    def test_build_context_invalid_timestamp_format(self):
        """Test context building with invalid timestamp format in path."""
        # Create directory with invalid timestamp format
        base_dir = Path("output/dev/invalid-timestamp")
        milestone_dir = base_dir / "milestone-1"
        milestone_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Should raise ContextPathError for invalid timestamp format
            with pytest.raises(ContextPathError) as exc_info:
                build_context(milestone_dir)

            assert "Invalid milestone path" in str(exc_info.value)

        finally:
            # Clean up
            shutil.rmtree(base_dir, ignore_errors=True)

    def test_build_context_invalid_milestone_name(self):
        """Test context building with invalid milestone directory name."""
        # Create directory with wrong milestone naming
        base_dir = Path("output/dev/20250615_120000")
        wrong_milestone_dir = base_dir / "wrong-name"
        wrong_milestone_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Should raise ContextPathError for invalid milestone name
            with pytest.raises(ContextPathError) as exc_info:
                build_context(wrong_milestone_dir)

            assert "Invalid milestone path" in str(exc_info.value)

        finally:
            # Clean up
            shutil.rmtree(base_dir, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
