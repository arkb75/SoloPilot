#!/usr/bin/env python3
"""Validate all Python imports can be resolved after refactoring."""

import ast
import importlib.util
import os
import sys


def validate_imports(root_dir):
    """Validate all Python imports can be resolved."""
    errors = []
    checked = 0

    # Add project root to path
    sys.path.insert(0, root_dir)

    # Also add src to the path for direct imports
    src_path = os.path.join(root_dir, "src")
    if os.path.exists(src_path):
        sys.path.insert(0, src_path)

    for root, dirs, files in os.walk(root_dir):
        # Skip virtual environments and caches
        dirs[:] = [
            d
            for d in dirs
            if d
            not in {".venv", "venv", "__pycache__", "node_modules", ".git", "output", "analysis"}
        ]

        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                checked += 1

                try:
                    with open(filepath) as f:
                        content = f.read()

                    # Parse the AST
                    tree = ast.parse(content)

                    # Check all imports
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                module_name = alias.name
                                if not can_import(module_name):
                                    errors.append(
                                        f"{filepath}:{node.lineno} - Cannot import '{module_name}'"
                                    )

                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                # Handle relative imports
                                if node.level > 0:
                                    # Skip relative imports for now
                                    continue

                                module_name = node.module
                                if not can_import(module_name):
                                    errors.append(
                                        f"{filepath}:{node.lineno} - Cannot import from '{module_name}'"
                                    )

                except SyntaxError as e:
                    errors.append(f"{filepath} - Syntax error: {e}")
                except Exception as e:
                    errors.append(f"{filepath} - Error: {e}")

    return errors, checked


def can_import(module_name):
    """Check if a module can be imported."""
    # Skip known external modules
    external_modules = {
        "boto3",
        "botocore",
        "pytest",
        "langchain",
        "chromadb",
        "numpy",
        "pandas",
        "requests",
        "yaml",
        "json",
        "os",
        "sys",
        "datetime",
        "logging",
        "pathlib",
        "unittest",
        "subprocess",
        "re",
        "ast",
        "importlib",
        "setuptools",
        "click",
        "dotenv",
        "openai",
        "anthropic",
        "bs4",
        "PIL",
        "faiss",
        "aiohttp",
    }

    # Check if it's a standard library or known external module
    if module_name.split(".")[0] in external_modules:
        return True

    # Try to find the module spec
    try:
        spec = importlib.util.find_spec(module_name)
        return spec is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def main():
    """Run import validation."""
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print(f"Validating imports in: {root_dir}")
    print("=" * 60)

    errors, total_files = validate_imports(root_dir)

    print(f"\nChecked {total_files} Python files")

    if errors:
        print(f"\n❌ Found {len(errors)} import errors:\n")
        for error in errors[:20]:  # Show first 20 errors
            print(f"  {error}")
        if len(errors) > 20:
            print(f"\n  ... and {len(errors) - 20} more errors")
        return 1
    else:
        print("\n✅ All imports validated successfully!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
