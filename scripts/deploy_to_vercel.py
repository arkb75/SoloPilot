#!/usr/bin/env python3
"""Deploy to Vercel with environment management and validation."""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import click
import requests
from dotenv import load_dotenv

# Vercel API base URL
VERCEL_API_BASE = "https://api.vercel.com"
VERCEL_API_VERSION = "v13"


class VercelDeployer:
    """Handle Vercel deployments with environment and domain management."""

    def __init__(self, token: str, org_id: str, project_id: str):
        """Initialize Vercel deployer with credentials."""
        self.token = token
        self.org_id = org_id
        self.project_id = project_id
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def create_deployment(
        self,
        environment: str,
        branch: str,
        commit: str,
        project_root: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Create a new deployment on Vercel."""
        click.echo(f"📦 Creating {environment} deployment from branch: {branch}")

        # Prepare deployment configuration
        deployment_config = self._prepare_deployment_config(
            environment, branch, commit, project_root
        )

        # Create deployment
        url = f"{VERCEL_API_BASE}/{VERCEL_API_VERSION}/deployments"
        params = {"teamId": self.org_id} if self.org_id else {}

        response = requests.post(
            url, headers=self.headers, json=deployment_config, params=params
        )

        if response.status_code != 200:
            click.echo(f"❌ Deployment failed: {response.status_code}")
            click.echo(response.text)
            sys.exit(1)

        deployment = response.json()
        deployment_id = deployment["id"]
        deployment_url = deployment["url"]

        click.echo(f"✅ Deployment created: {deployment_id}")
        click.echo(f"🔗 URL: https://{deployment_url}")

        # Wait for deployment to complete
        final_deployment = self._wait_for_deployment(deployment_id)

        return final_deployment

    def _prepare_deployment_config(
        self, environment: str, branch: str, commit: str, project_root: Optional[Path]
    ) -> Dict[str, Any]:
        """Prepare deployment configuration."""
        config: Dict[str, Any] = {
            "name": self.project_id,
            "project": self.project_id,
            "target": environment,
            "gitSource": {
                "ref": branch,
                "sha": commit,
                "type": "github",
            },
        }

        # Load environment variables
        env_vars = self._load_environment_variables(environment, project_root)
        if env_vars:
            config["env"] = env_vars

        # Set build configuration
        build_config = self._get_build_config(project_root)
        if build_config:
            config["build"] = build_config

        # Set custom domains for production
        if environment == "production":
            domains = self._get_custom_domains()
            if domains:
                config["alias"] = domains

        return config

    def _load_environment_variables(
        self, environment: str, project_root: Optional[Path]
    ) -> Dict[str, str]:
        """Load environment variables from files and secrets."""
        env_vars = {}

        # Load from .env.production or .env.preview
        if project_root:
            env_file = project_root / f".env.{environment}"
            if env_file.exists():
                load_dotenv(env_file)
                click.echo(f"📋 Loaded environment from: {env_file}")

        # Load from environment (GitHub secrets)
        env_prefix = f"VERCEL_{environment.upper()}_"
        for key, value in os.environ.items():
            if key.startswith(env_prefix):
                var_name = key.replace(env_prefix, "")
                env_vars[var_name] = value

        # Common environment variables
        common_vars = {
            "NODE_ENV": environment,
            "NEXT_PUBLIC_DEPLOYMENT_ENV": environment,
            "DEPLOYMENT_TIMESTAMP": str(int(time.time())),
        }

        env_vars.update(common_vars)
        click.echo(f"🔧 Configured {len(env_vars)} environment variables")

        return env_vars

    def _get_build_config(self, project_root: Optional[Path]) -> Optional[Dict[str, Any]]:
        """Get build configuration based on project type."""
        if not project_root:
            return None

        build_config: Dict[str, Any] = {}

        # Check for Next.js
        package_json_path = project_root / "package.json"
        if package_json_path.exists():
            with open(package_json_path) as f:
                package_data = json.load(f)
                if "next" in package_data.get("dependencies", {}):
                    build_config["buildCommand"] = "npm run build"
                    build_config["outputDirectory"] = ".next"
                    click.echo("🔨 Detected Next.js project")

        # Check for Python project
        requirements_path = project_root / "requirements.txt"
        if requirements_path.exists() and not build_config:
            build_config["buildCommand"] = "pip install -r requirements.txt"
            build_config["outputDirectory"] = "."
            click.echo("🐍 Detected Python project")

        return build_config if build_config else None

    def _get_custom_domains(self) -> list[str]:
        """Get custom domains for production deployment."""
        domains = []

        # Primary domain from environment
        primary_domain = os.environ.get("VERCEL_CUSTOM_DOMAIN")
        if primary_domain:
            domains.append(primary_domain)

        # Additional domains
        additional_domains = os.environ.get("VERCEL_ADDITIONAL_DOMAINS", "").split(",")
        domains.extend([d.strip() for d in additional_domains if d.strip()])

        if domains:
            click.echo(f"🌐 Configuring custom domains: {', '.join(domains)}")

        return domains

    def _wait_for_deployment(self, deployment_id: str, timeout: int = 600) -> Dict[str, Any]:
        """Wait for deployment to complete."""
        click.echo("⏳ Waiting for deployment to complete...")

        start_time = time.time()
        url = f"{VERCEL_API_BASE}/{VERCEL_API_VERSION}/deployments/{deployment_id}"
        params = {"teamId": self.org_id} if self.org_id else {}

        while time.time() - start_time < timeout:
            response = requests.get(url, headers=self.headers, params=params)

            if response.status_code != 200:
                click.echo(f"❌ Failed to check deployment status: {response.status_code}")
                sys.exit(1)

            deployment = response.json()
            state = deployment.get("readyState", "QUEUED")

            if state == "READY":
                click.echo("✅ Deployment completed successfully!")
                return deployment
            elif state in ["ERROR", "CANCELED"]:
                click.echo(f"❌ Deployment failed with state: {state}")
                sys.exit(1)
            else:
                click.echo(f"   Status: {state}")
                time.sleep(5)

        click.echo("❌ Deployment timed out")
        sys.exit(1)

    def configure_domains(self, deployment: Dict[str, Any], domains: list[str]) -> None:
        """Configure custom domains for the deployment."""
        if not domains:
            return

        deployment_id = deployment["id"]
        click.echo("🔗 Configuring custom domains...")

        for domain in domains:
            self._add_domain_to_project(domain)
            self._assign_domain_to_deployment(deployment_id, domain)

    def _add_domain_to_project(self, domain: str) -> None:
        """Add domain to Vercel project."""
        url = f"{VERCEL_API_BASE}/v10/projects/{self.project_id}/domains"
        params = {"teamId": self.org_id} if self.org_id else {}

        response = requests.post(
            url,
            headers=self.headers,
            json={"name": domain},
            params=params,
        )

        if response.status_code in [200, 409]:  # 409 means domain already exists
            click.echo(f"   ✅ Domain configured: {domain}")
        else:
            click.echo(f"   ⚠️  Failed to add domain {domain}: {response.status_code}")

    def _assign_domain_to_deployment(self, deployment_id: str, domain: str) -> None:
        """Assign domain to specific deployment."""
        url = f"{VERCEL_API_BASE}/v10/deployments/{deployment_id}/aliases"
        params = {"teamId": self.org_id} if self.org_id else {}

        response = requests.post(
            url,
            headers=self.headers,
            json={"alias": domain},
            params=params,
        )

        if response.status_code == 200:
            click.echo(f"   ✅ Domain assigned to deployment: {domain}")
        else:
            click.echo(f"   ⚠️  Failed to assign domain: {response.status_code}")

    def validate_deployment(self, deployment_url: str) -> bool:
        """Validate the deployment is accessible and healthy."""
        click.echo("🔍 Validating deployment...")

        # Check basic accessibility
        try:
            response = requests.get(f"https://{deployment_url}", timeout=30)
            if response.status_code == 200:
                click.echo("   ✅ Deployment is accessible")
            else:
                click.echo(f"   ❌ Deployment returned status: {response.status_code}")
                return False
        except requests.RequestException as e:
            click.echo(f"   ❌ Failed to access deployment: {e}")
            return False

        # Check SSL certificate
        try:
            response = requests.get(f"https://{deployment_url}", verify=True)
            click.echo("   ✅ SSL certificate is valid")
        except requests.exceptions.SSLError:
            click.echo("   ❌ SSL certificate validation failed")
            return False

        # Check API health endpoint if exists
        try:
            health_response = requests.get(f"https://{deployment_url}/api/health", timeout=10)
            if health_response.status_code == 200:
                click.echo("   ✅ API health check passed")
        except:
            # API endpoint might not exist, which is okay
            pass

        return True


@click.command()
@click.option("--token", required=True, help="Vercel API token")
@click.option("--org-id", help="Vercel organization ID")
@click.option("--project-id", required=True, help="Vercel project ID")
@click.option(
    "--environment",
    type=click.Choice(["production", "preview"]),
    default="production",
    help="Deployment environment",
)
@click.option("--branch", required=True, help="Git branch name")
@click.option("--commit", required=True, help="Git commit SHA")
@click.option(
    "--project-root",
    type=click.Path(exists=True, path_type=Path),
    default=".",
    help="Project root directory",
)
@click.option("--skip-validation", is_flag=True, help="Skip post-deployment validation")
def deploy(
    token: str,
    org_id: Optional[str],
    project_id: str,
    environment: str,
    branch: str,
    commit: str,
    project_root: Path,
    skip_validation: bool,
) -> None:
    """Deploy project to Vercel with environment and domain management."""
    click.echo(f"🚀 Starting Vercel deployment for {project_id}")
    click.echo(f"   Environment: {environment}")
    click.echo(f"   Branch: {branch}")
    click.echo(f"   Commit: {commit[:8]}")

    # Initialize deployer
    deployer = VercelDeployer(token, org_id, project_id)

    # Create deployment
    deployment = deployer.create_deployment(environment, branch, commit, project_root)

    # Get deployment URL
    deployment_url = deployment.get("url", "")
    if not deployment_url:
        click.echo("❌ No deployment URL returned")
        sys.exit(1)

    # Configure custom domains for production
    if environment == "production":
        custom_domains = deployer._get_custom_domains()
        if custom_domains:
            deployer.configure_domains(deployment, custom_domains)

    # Validate deployment
    if not skip_validation:
        if deployer.validate_deployment(deployment_url):
            click.echo("\n✅ Deployment successful and validated!")
        else:
            click.echo("\n❌ Deployment validation failed")
            sys.exit(1)
    else:
        click.echo("\n✅ Deployment completed (validation skipped)")

    # Output deployment URL for GitHub Actions
    print(f"::set-output name=deployment_url::https://{deployment_url}")

    # Summary
    click.echo("\n📊 Deployment Summary:")
    click.echo(f"   ID: {deployment['id']}")
    click.echo(f"   URL: https://{deployment_url}")
    click.echo(f"   Environment: {environment}")
    click.echo(f"   State: {deployment.get('readyState', 'UNKNOWN')}")


if __name__ == "__main__":
    deploy()