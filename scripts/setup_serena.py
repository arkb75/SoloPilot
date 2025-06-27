#!/usr/bin/env python3
"""
Serena LSP Integration Setup Script for SoloPilot

This script installs and configures Serena for symbol-aware context management.
Serena provides Language Server Protocol (LSP) integration for precise code analysis.
"""

import subprocess
import sys
from pathlib import Path
from typing import List, Optional


def run_command(
    cmd: List[str], cwd: Optional[Path] = None, check: bool = True
) -> subprocess.CompletedProcess:
    """Run a command with proper error handling."""
    print(f"🔧 Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)
        if result.stdout:
            print(f"✅ Output: {result.stdout.strip()}")
        return result
    except subprocess.CalledProcessError as e:
        print(f"❌ Command failed: {e}")
        if e.stderr:
            print(f"❌ Error: {e.stderr.strip()}")
        if check:
            sys.exit(1)
        return e


def check_uvx_installed() -> bool:
    """Check if uvx is installed and available."""
    try:
        result = run_command(["uvx", "--version"], check=False)
        return result.returncode == 0
    except FileNotFoundError:
        return False


def install_uvx() -> None:
    """Install uvx if not available."""
    print("📦 Installing uvx...")
    try:
        # Try pip install first
        run_command([sys.executable, "-m", "pip", "install", "uvx"])
    except subprocess.CalledProcessError:
        print("❌ Failed to install uvx via pip")
        print("🔧 Please install uvx manually: https://github.com/astral-sh/uvx")
        sys.exit(1)


def install_serena() -> None:
    """Install Serena via uvx."""
    print("🚀 Installing Serena from GitHub...")

    # Install Serena from git repository
    cmd = ["uvx", "--from", "git+https://github.com/oraios/serena", "install"]
    result = run_command(cmd, check=False)

    if result.returncode != 0:
        print("❌ Failed to install Serena via uvx")
        print("🔧 Trying alternative installation methods...")

        # Try direct git clone and pip install
        try:
            temp_dir = Path("/tmp/serena_install")
            if temp_dir.exists():
                run_command(["rm", "-rf", str(temp_dir)])

            run_command(["git", "clone", "https://github.com/oraios/serena.git", str(temp_dir)])
            run_command([sys.executable, "-m", "pip", "install", str(temp_dir)], cwd=temp_dir)

            # Cleanup
            run_command(["rm", "-rf", str(temp_dir)])

        except subprocess.CalledProcessError:
            print("❌ All installation methods failed")
            print("🔧 Please install Serena manually:")
            print("   git clone https://github.com/oraios/serena.git")
            print("   cd serena && pip install .")
            sys.exit(1)


def setup_serena_directory() -> Path:
    """Create .serena directory structure."""
    project_root = Path.cwd()
    serena_dir = project_root / ".serena"

    print(f"📁 Creating Serena directory at {serena_dir}")
    serena_dir.mkdir(exist_ok=True)

    # Create subdirectories for different language servers
    (serena_dir / "python").mkdir(exist_ok=True)
    (serena_dir / "javascript").mkdir(exist_ok=True)
    (serena_dir / "typescript").mkdir(exist_ok=True)

    return serena_dir


def create_serena_config(serena_dir: Path) -> None:
    """Create basic Serena configuration."""
    config_content = """# Serena Configuration for SoloPilot
# Language Server Protocol integration settings

[general]
log_level = "info"
timeout = 30

[python]
enabled = true
server = "pylsp"
auto_install = true

[javascript]
enabled = true
server = "typescript-language-server"
auto_install = true

[typescript]
enabled = true
server = "typescript-language-server"
auto_install = true
"""

    config_file = serena_dir / "config.toml"
    print(f"⚙️  Creating config at {config_file}")
    config_file.write_text(config_content)


def verify_installation() -> bool:
    """Verify Serena installation is working."""
    print("🔍 Verifying Serena installation...")

    try:
        # Try to import serena
        result = run_command(
            [sys.executable, "-c", "import serena; print('Serena imported successfully')"],
            check=False,
        )
        if result.returncode == 0:
            print("✅ Serena installation verified")
            return True
        else:
            print("❌ Serena import failed")
            return False

    except Exception as e:
        print(f"❌ Verification failed: {e}")
        return False


def update_gitignore() -> None:
    """Update .gitignore to exclude Serena files."""
    gitignore_path = Path(".gitignore")

    serena_entries = [
        "# Serena LSP Integration",
        ".serena/",
        "*.serena-cache",
        ".serena-workspace/",
    ]

    if gitignore_path.exists():
        existing_content = gitignore_path.read_text()
        if ".serena/" not in existing_content:
            print("📝 Updating .gitignore")
            with gitignore_path.open("a") as f:
                f.write("\n")
                f.write("\n".join(serena_entries))
                f.write("\n")
        else:
            print("✅ .gitignore already contains Serena entries")
    else:
        print("📝 Creating .gitignore with Serena entries")
        gitignore_path.write_text("\n".join(serena_entries) + "\n")


def main():
    """Main setup function."""
    print("🎯 SoloPilot Serena LSP Integration Setup")
    print("=" * 50)

    # Check if we're in the correct directory
    if not Path("agents").exists() or not Path("config").exists():
        print("❌ Please run this script from the SoloPilot root directory")
        sys.exit(1)

    # Step 1: Check/install uvx
    if not check_uvx_installed():
        install_uvx()
    else:
        print("✅ uvx is already installed")

    # Step 2: Install Serena
    install_serena()

    # Step 3: Setup directory structure
    serena_dir = setup_serena_directory()

    # Step 4: Create configuration
    create_serena_config(serena_dir)

    # Step 5: Update .gitignore
    update_gitignore()

    # Step 6: Verify installation
    if verify_installation():
        print("\n🎉 Serena setup completed successfully!")
        print("🔧 Next steps:")
        print("   1. Set CONTEXT_ENGINE=serena to enable Serena context engine")
        print("   2. Run development tasks to test the integration")
        print("   3. Monitor performance improvements in logs/llm_calls.log")
    else:
        print("\n❌ Setup completed but verification failed")
        print("🔧 Please check the installation manually")
        sys.exit(1)


if __name__ == "__main__":
    main()
