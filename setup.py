"""Setup configuration for SoloPilot."""

from setuptools import find_packages, setup

setup(
    name="solopilot",
    version="0.1.0",
    packages=find_packages(include=["src", "src.*"]),
    package_dir={"": "."},
    python_requires=">=3.8",
    install_requires=[],
)