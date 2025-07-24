#!/usr/bin/env python3
"""Vercel project management for dynamic client deployments."""

import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import click
import requests

logger = logging.getLogger(__name__)

# Vercel API configuration
VERCEL_API_BASE = "https://api.vercel.com"
VERCEL_API_VERSION = "v10"  # Using v10 for project management


class VercelProjectManager:
    """Manages Vercel projects for client deployments."""

    def __init__(self, token: Optional[str] = None):
        """Initialize with Vercel API token.

        Args:
            token: Vercel API token, defaults to VERCEL_TOKEN env var
        """
        self.token = token or os.environ.get("VERCEL_TOKEN", "")
        if not self.token:
            raise ValueError("Vercel API token is required")

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

        # No org_id for personal accounts
        self.api_params = {}

    def create_project(
        self,
        client_name: str,
        project_type: str = "site",
        framework: Optional[str] = None,
        environment_variables: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, str]:
        """Create a new Vercel project for a client.

        Args:
            client_name: Client business name
            project_type: Type of project (site, app, api)
            framework: Framework to use (nextjs, react, etc)
            environment_variables: Initial env vars to set

        Returns:
            Tuple of (project_id, project_name)
        """
        # Generate unique project name
        project_name = self._generate_project_name(client_name, project_type)

        logger.info(f"Creating Vercel project: {project_name}")

        # Check if project already exists
        existing = self._get_project_by_name(project_name)
        if existing:
            logger.info(f"Project already exists: {existing['id']}")
            return existing["id"], project_name

        # Create project
        url = f"{VERCEL_API_BASE}/{VERCEL_API_VERSION}/projects"

        project_config = {
            "name": project_name,
            "framework": framework,
            "publicSource": False,
            "installCommand": self._get_install_command(framework),
            "buildCommand": self._get_build_command(framework),
            "outputDirectory": self._get_output_directory(framework),
        }

        # Add environment variables if provided
        if environment_variables:
            project_config["environmentVariables"] = [
                {
                    "key": key,
                    "value": value,
                    "target": ["production", "preview", "development"],
                    "type": "encrypted",
                }
                for key, value in environment_variables.items()
            ]

        try:
            response = requests.post(
                url, headers=self.headers, json=project_config, params=self.api_params
            )

            if response.status_code == 200:
                project = response.json()
                logger.info(f"Successfully created project: {project['id']}")
                return project["id"], project["name"]
            else:
                error_msg = f"Failed to create project: {response.status_code} - {response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)

        except requests.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            raise

    def get_or_create_project(
        self, client_name: str, project_type: str = "site", **kwargs
    ) -> Tuple[str, str]:
        """Get existing project or create new one.

        Args:
            client_name: Client business name
            project_type: Type of project
            **kwargs: Additional arguments for create_project

        Returns:
            Tuple of (project_id, project_name)
        """
        # Check for existing project first
        project_name = self._generate_project_name(client_name, project_type)
        existing = self._get_project_by_name(project_name)

        if existing:
            logger.info(f"Found existing project: {existing['id']}")
            return existing["id"], project_name

        # Create new project
        return self.create_project(client_name, project_type, **kwargs)

    def list_client_projects(self, filter_prefix: str = "client-") -> List[Dict[str, Any]]:
        """List all client projects.

        Args:
            filter_prefix: Prefix to filter projects

        Returns:
            List of project dictionaries
        """
        url = f"{VERCEL_API_BASE}/{VERCEL_API_VERSION}/projects"

        try:
            response = requests.get(
                url, headers=self.headers, params={**self.api_params, "limit": 100}
            )

            if response.status_code == 200:
                projects = response.json().get("projects", [])
                # Filter client projects
                client_projects = [p for p in projects if p["name"].startswith(filter_prefix)]
                logger.info(f"Found {len(client_projects)} client projects")
                return client_projects
            else:
                logger.error(f"Failed to list projects: {response.status_code}")
                return []

        except requests.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            return []

    def delete_project(self, project_id: str) -> bool:
        """Delete a Vercel project.

        Args:
            project_id: Project ID to delete

        Returns:
            True if successful
        """
        url = f"{VERCEL_API_BASE}/{VERCEL_API_VERSION}/projects/{project_id}"

        try:
            response = requests.delete(url, headers=self.headers, params=self.api_params)

            if response.status_code == 204:
                logger.info(f"Successfully deleted project: {project_id}")
                return True
            else:
                logger.error(f"Failed to delete project: {response.status_code}")
                return False

        except requests.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            return False

    def update_project_env_vars(
        self, project_id: str, env_vars: Dict[str, str], target: List[str] = None
    ) -> bool:
        """Update project environment variables.

        Args:
            project_id: Project ID
            env_vars: Dictionary of environment variables
            target: Environments to target (production, preview, development)

        Returns:
            True if successful
        """
        if target is None:
            target = ["production", "preview", "development"]

        url = f"{VERCEL_API_BASE}/{VERCEL_API_VERSION}/projects/{project_id}/env"

        success = True
        for key, value in env_vars.items():
            try:
                # First, try to update existing var
                env_id = self._get_env_var_id(project_id, key)

                if env_id:
                    # Update existing
                    update_url = f"{url}/{env_id}"
                    response = requests.patch(
                        update_url,
                        headers=self.headers,
                        json={"value": value},
                        params=self.api_params,
                    )
                else:
                    # Create new
                    response = requests.post(
                        url,
                        headers=self.headers,
                        json={
                            "key": key,
                            "value": value,
                            "target": target,
                            "type": "encrypted",
                        },
                        params=self.api_params,
                    )

                if response.status_code not in [200, 201]:
                    logger.error(f"Failed to set env var {key}: {response.status_code}")
                    success = False

            except requests.RequestException as e:
                logger.error(f"Failed to set env var {key}: {str(e)}")
                success = False

        return success

    def _generate_project_name(self, client_name: str, project_type: str) -> str:
        """Generate unique project name with timestamp.

        Args:
            client_name: Client business name
            project_type: Type of project

        Returns:
            Sanitized project name
        """
        # Sanitize client name
        sanitized = re.sub(r"[^a-z0-9-]", "-", client_name.lower())
        sanitized = re.sub(r"-+", "-", sanitized).strip("-")

        # Add timestamp for uniqueness
        timestamp = datetime.now().strftime("%Y%m%d")

        # Construct project name
        project_name = f"client-{sanitized}-{project_type}-{timestamp}"

        # Ensure it meets Vercel requirements (max 100 chars)
        if len(project_name) > 100:
            # Truncate client name part if needed
            max_client_len = 100 - len(f"client--{project_type}-{timestamp}")
            sanitized = sanitized[:max_client_len]
            project_name = f"client-{sanitized}-{project_type}-{timestamp}"

        return project_name

    def _get_project_by_name(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Get project by name.

        Args:
            project_name: Project name to search

        Returns:
            Project dict if found, None otherwise
        """
        projects = self.list_client_projects()
        for project in projects:
            if project["name"] == project_name:
                return project
        return None

    def _get_env_var_id(self, project_id: str, key: str) -> Optional[str]:
        """Get environment variable ID by key.

        Args:
            project_id: Project ID
            key: Environment variable key

        Returns:
            Env var ID if found
        """
        url = f"{VERCEL_API_BASE}/{VERCEL_API_VERSION}/projects/{project_id}/env"

        try:
            response = requests.get(url, headers=self.headers, params=self.api_params)

            if response.status_code == 200:
                env_vars = response.json().get("envs", [])
                for env_var in env_vars:
                    if env_var["key"] == key:
                        return env_var["id"]

        except requests.RequestException:
            pass

        return None

    def _get_install_command(self, framework: Optional[str]) -> str:
        """Get install command for framework."""
        commands = {
            "nextjs": "npm install",
            "react": "npm install",
            "vue": "npm install",
            "python": "pip install -r requirements.txt",
        }
        return commands.get(framework, "npm install")

    def _get_build_command(self, framework: Optional[str]) -> str:
        """Get build command for framework."""
        commands = {
            "nextjs": "npm run build",
            "react": "npm run build",
            "vue": "npm run build",
            "python": "",  # No build for Python
        }
        return commands.get(framework, "npm run build")

    def _get_output_directory(self, framework: Optional[str]) -> str:
        """Get output directory for framework."""
        directories = {
            "nextjs": ".next",
            "react": "build",
            "vue": "dist",
            "python": ".",
        }
        return directories.get(framework, ".")


# CLI commands
@click.group()
def cli():
    """Vercel project management CLI."""
    pass


@cli.command()
@click.option("--client-name", required=True, help="Client business name")
@click.option("--project-type", default="site", help="Project type (site, app, api)")
@click.option("--framework", help="Framework (nextjs, react, vue, python)")
def create(client_name: str, project_type: str, framework: Optional[str]):
    """Create a new client project."""
    manager = VercelProjectManager()

    try:
        project_id, project_name = manager.create_project(client_name, project_type, framework)
        click.echo(f"✅ Created project: {project_name}")
        click.echo(f"   ID: {project_id}")
    except Exception as e:
        click.echo(f"❌ Failed to create project: {str(e)}")
        raise


@cli.command()
@click.option("--prefix", default="client-", help="Project name prefix filter")
def list(prefix: str):
    """List all client projects."""
    manager = VercelProjectManager()

    projects = manager.list_client_projects(prefix)

    if not projects:
        click.echo("No client projects found")
        return

    click.echo(f"Found {len(projects)} client projects:\n")
    for project in projects:
        click.echo(f"• {project['name']}")
        click.echo(f"  ID: {project['id']}")
        click.echo(f"  Created: {project.get('createdAt', 'N/A')}")
        click.echo(f"  Framework: {project.get('framework', 'None')}")
        click.echo()


@cli.command()
@click.option("--project-id", required=True, help="Project ID to delete")
@click.confirmation_option(prompt="Are you sure you want to delete this project?")
def delete(project_id: str):
    """Delete a client project."""
    manager = VercelProjectManager()

    if manager.delete_project(project_id):
        click.echo(f"✅ Deleted project: {project_id}")
    else:
        click.echo(f"❌ Failed to delete project: {project_id}")


if __name__ == "__main__":
    cli()
