#!/usr/bin/env python3
"""
SoloPilot Requirement Analyser CLI

Command-line interface for processing client requirements.
Supports individual files, directories, and ZIP archives.

Usage:
    python scripts/run_analyser.py --path ./sample_input
    python scripts/run_analyser.py --path requirements.zip --output ./custom_output
    python scripts/run_analyser.py --file requirements.md --config ./config/model_config.yaml
"""

import argparse
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.analyser import ImageParser, SpecBuilder, TextParser


def extract_zip(zip_path: str, extract_to: str) -> str:
    """Extract ZIP file and return extraction directory."""
    extract_dir = Path(extract_to) / Path(zip_path).stem
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_dir)

    return str(extract_dir)


def find_files(directory: str) -> Dict[str, List[str]]:
    """Find text and image files in directory."""
    path = Path(directory)

    text_extensions = {".md", ".txt", ".docx"}
    image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff"}

    files = {"text": [], "images": [], "other": []}

    for file_path in path.rglob("*"):
        if file_path.is_file():
            ext = file_path.suffix.lower()
            if ext in text_extensions:
                files["text"].append(str(file_path))
            elif ext in image_extensions:
                files["images"].append(str(file_path))
            else:
                files["other"].append(str(file_path))

    return files


def process_requirements(input_path: str, config_path: str = None, output_dir: str = None) -> str:
    """Process requirements from input path and generate specification."""

    # Initialize parsers
    text_parser = TextParser(config_path)
    image_parser = ImageParser()
    spec_builder = SpecBuilder(output_dir or "analysis/output")

    # Handle different input types
    input_path = Path(input_path)

    if input_path.suffix.lower() == ".zip":
        # Extract ZIP file
        temp_dir = extract_zip(str(input_path), "./temp")
        work_dir = temp_dir
        print(f"✓ Extracted ZIP to: {temp_dir}")
    elif input_path.is_file():
        # Single file
        work_dir = str(input_path.parent)
        files = {
            "text": (
                [str(input_path)] if input_path.suffix.lower() in {".md", ".txt", ".docx"} else []
            ),
            "images": (
                [str(input_path)]
                if input_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff"}
                else []
            ),
            "other": [],
        }
    elif input_path.is_dir():
        # Directory
        work_dir = str(input_path)
        files = find_files(work_dir)
    else:
        raise ValueError(f"Input path does not exist: {input_path}")

    # Find files if working with directory
    if input_path.is_dir() or input_path.suffix.lower() == ".zip":
        files = find_files(work_dir)

    print("📁 Processing files:")
    print(f"   Text files: {len(files['text'])}")
    print(f"   Image files: {len(files['images'])}")
    print(f"   Other files: {len(files['other'])}")

    # Process text files
    combined_requirements = {
        "title": "Project Requirements",
        "summary": "",
        "features": [],
        "constraints": [],
        "tech_stack": [],
        "timeline": None,
        "budget": None,
    }

    if files["text"]:
        print("\n📝 Processing text files...")
        for text_file in files["text"]:
            try:
                print(f"   Processing: {Path(text_file).name}")
                content = text_parser.parse_file(text_file)
                requirements = text_parser.extract_requirements(content)

                # Merge requirements
                combined_requirements = merge_requirements(combined_requirements, requirements)

            except Exception as e:
                print(f"   ❌ Error processing {text_file}: {e}")

    # Process images
    image_texts = {}
    if files["images"]:
        print("\n🖼️  Processing images...")
        for image_file in files["images"]:
            try:
                print(f"   Processing: {Path(image_file).name}")
                text = image_parser.parse_image(image_file)
                if text.strip():
                    image_texts[image_file] = text
                    print(f"   ✓ Extracted {len(text)} characters")
                else:
                    print("   ⚠️  No text found")
            except Exception as e:
                print(f"   ❌ Error processing {image_file}: {e}")

    # Build specification
    print("\n🔧 Building specification...")
    spec = spec_builder.build_specification(
        combined_requirements, image_texts, files["text"] + files["other"]
    )

    # Generate artifacts
    print("🎨 Generating artifacts...")
    artifacts = spec_builder.generate_artifacts(spec)

    # Save everything
    session_dir = spec_builder.save_artifacts(spec, artifacts)

    print("\n✅ Analysis complete!")
    print(f"📊 Output saved to: {session_dir}")
    print(f"🎯 Project: {spec['title']}")
    print(f"📝 Features: {len(spec['features'])}")
    print(f"🔧 Artifacts: {len(artifacts)}")

    return session_dir


def merge_requirements(base: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two requirement dictionaries."""
    merged = base.copy()

    # Update title if base is generic
    if base.get("title") == "Project Requirements" and new.get("title"):
        merged["title"] = new["title"]

    # Combine summaries
    if new.get("summary"):
        if merged.get("summary"):
            merged["summary"] += f" {new['summary']}"
        else:
            merged["summary"] = new["summary"]

    # Merge lists
    for list_field in ["features", "constraints", "tech_stack"]:
        if new.get(list_field):
            existing = merged.setdefault(list_field, [])
            for item in new[list_field]:
                if item not in existing:
                    existing.append(item)

    # Update scalar fields if not set
    for field in ["timeline", "budget"]:
        if new.get(field) and not merged.get(field):
            merged[field] = new[field]

    return merged


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="SoloPilot Requirement Analyser",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --path ./client_brief.md
  %(prog)s --path ./requirements_folder
  %(prog)s --path ./project.zip --output ./analysis
  %(prog)s --file brief.txt --config ./config/model_config.yaml
        """,
    )

    # Input arguments
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--path", help="Path to file, directory, or ZIP archive containing requirements"
    )
    input_group.add_argument("--file", help="Single file to process (alias for --path)")

    # Configuration arguments
    parser.add_argument("--config", help="Path to model configuration YAML file", default=None)
    parser.add_argument("--output", help="Output directory for analysis results", default=None)

    # Parse arguments
    args = parser.parse_args()

    # Use --file as --path if provided
    input_path = args.path or args.file

    try:
        print("🚀 SoloPilot Requirement Analyser")
        print("=" * 50)

        session_dir = process_requirements(input_path, args.config, args.output)

        print("\n" + "=" * 50)
        print(f"📂 Results: {session_dir}")
        print("🎉 Ready for planning agent!")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
