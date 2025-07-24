#!/usr/bin/env python3
"""Orchestrate client project deployment from requirements to live URL."""

import json
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import click
import requests

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from vercel_project_manager import VercelProjectManager

from src.agents.email_intake.conversation_state import ConversationStateManager
from src.agents.email_intake.deployment_tracker import DeploymentTracker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ClientDeploymentOrchestrator:
    """Orchestrates the complete client deployment process."""

    def __init__(
        self,
        github_token: Optional[str] = None,
        vercel_token: Optional[str] = None,
        conversations_table: str = "conversations",
        deployments_table: str = "client_deployments",
    ):
        """Initialize orchestrator with credentials and configurations.

        Args:
            github_token: GitHub personal access token
            vercel_token: Vercel API token
            conversations_table: DynamoDB table for conversations
            deployments_table: DynamoDB table for deployments
        """
        self.github_token = github_token or os.environ.get("GITHUB_TOKEN", "")
        self.vercel_token = vercel_token or os.environ.get("VERCEL_TOKEN", "")

        if not self.github_token:
            raise ValueError("GitHub token is required")
        if not self.vercel_token:
            raise ValueError("Vercel token is required")

        # Initialize managers
        self.conversation_manager = ConversationStateManager(conversations_table)
        self.deployment_tracker = DeploymentTracker(deployments_table)
        self.vercel_manager = VercelProjectManager(self.vercel_token)

        # GitHub configuration
        self.github_headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.github_api_base = "https://api.github.com"
        self.github_org = os.environ.get("GITHUB_ORG", "")  # Optional org

    def deploy_from_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """Deploy a client project from conversation requirements.

        Args:
            conversation_id: Conversation ID containing requirements

        Returns:
            Deployment result with live URL
        """
        logger.info(f"Starting deployment for conversation: {conversation_id}")

        # 1. Fetch conversation and requirements
        conversation = self._fetch_conversation(conversation_id)
        requirements = conversation.get("requirements", {})

        if not requirements:
            raise ValueError("No requirements found in conversation")

        # 2. Extract client information
        client_info = self._extract_client_info(conversation, requirements)
        logger.info(f"Client: {client_info['name']} ({client_info['type']})")

        # 3. Create or get deployment record
        deployment = self._ensure_deployment_record(conversation_id, client_info)

        try:
            # 4. Create GitHub repository
            repo_url = self._ensure_github_repo(client_info, deployment)

            # 5. Create Vercel project
            vercel_project_id, project_name = self._ensure_vercel_project(client_info, deployment)

            # 6. Trigger deployment
            deployment_result = self._trigger_deployment(
                client_info, repo_url, vercel_project_id, requirements
            )

            # 7. Update deployment record with results
            self._update_deployment_record(
                conversation_id, deployment_result, vercel_project_id, repo_url
            )

            return {
                "success": True,
                "deployment_url": deployment_result["url"],
                "project_id": vercel_project_id,
                "repo_url": repo_url,
                "client": client_info,
            }

        except Exception as e:
            logger.error(f"Deployment failed: {str(e)}")
            self.deployment_tracker.update_deployment_status(conversation_id, "failed", str(e))
            raise

    def deploy_from_requirements(self, requirements_json: str) -> Dict[str, Any]:
        """Deploy from raw requirements JSON.

        Args:
            requirements_json: JSON string or file path containing requirements

        Returns:
            Deployment result
        """
        # Load requirements
        if os.path.exists(requirements_json):
            with open(requirements_json) as f:
                requirements = json.load(f)
        else:
            requirements = json.loads(requirements_json)

        # Create temporary conversation ID
        client_name = requirements.get("title", "Unknown Project")
        conversation_id = f"manual-{self._sanitize_name(client_name)}"

        # Extract client info directly from requirements
        client_info = {
            "id": conversation_id,
            "name": client_name,
            "type": requirements.get("project_type", "site"),
            "email": requirements.get("client_email", ""),
        }

        # Create deployment record
        deployment = self.deployment_tracker.create_deployment_record(
            client_id=conversation_id,
            client_name=client_info["name"],
            project_type=client_info["type"],
        )

        # Continue with normal deployment flow
        return self._deploy_project(client_info, requirements, deployment)

    def _fetch_conversation(self, conversation_id: str) -> Dict[str, Any]:
        """Fetch conversation from DynamoDB."""
        conversation = self.conversation_manager.fetch_or_create_conversation(
            conversation_id,
            "",  # No original message ID needed for fetch
            {},  # No initial email needed for fetch
        )

        if not conversation:
            raise ValueError(f"Conversation not found: {conversation_id}")

        return conversation

    def _extract_client_info(
        self, conversation: Dict[str, Any], requirements: Dict[str, Any]
    ) -> Dict[str, str]:
        """Extract client information from conversation and requirements."""
        # Try to get client name from requirements
        client_name = requirements.get("title", "")

        # Fallback to business description
        if not client_name and "business_description" in requirements:
            # Extract company name from description
            desc = requirements["business_description"]
            # Look for patterns like "Smith Consulting" or "ABC Corp"
            match = re.search(r"([A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)*)", desc)
            if match:
                client_name = match.group(1)

        # Final fallback to email domain
        if not client_name:
            participants = list(conversation.get("participants", []))
            if participants:
                # Use first non-solopilot email
                for email in participants:
                    if "solopilot" not in email.lower():
                        # Extract domain name
                        domain = email.split("@")[1].split(".")[0]
                        client_name = domain.title()
                        break

        if not client_name:
            client_name = "Unknown Client"

        return {
            "id": conversation["conversation_id"],
            "name": client_name,
            "type": requirements.get("project_type", "site"),
            "email": self._get_client_email(conversation),
        }

    def _get_client_email(self, conversation: Dict[str, Any]) -> str:
        """Extract client email from conversation."""
        participants = list(conversation.get("participants", []))
        for email in participants:
            if "solopilot" not in email.lower():
                return email
        return ""

    def _ensure_deployment_record(
        self, client_id: str, client_info: Dict[str, str]
    ) -> Dict[str, Any]:
        """Ensure deployment record exists."""
        deployment = self.deployment_tracker.get_deployment(client_id)

        if not deployment:
            deployment = self.deployment_tracker.create_deployment_record(
                client_id=client_id,
                client_name=client_info["name"],
                project_type=client_info["type"],
            )

        return deployment

    def _ensure_github_repo(self, client_info: Dict[str, str], deployment: Dict[str, Any]) -> str:
        """Ensure GitHub repository exists.

        Returns:
            Repository URL
        """
        # Check if repo already exists in deployment record
        if deployment.get("github_repo_url"):
            logger.info(f"Using existing repo: {deployment['github_repo_url']}")
            return deployment["github_repo_url"]

        # Generate repo name
        repo_name = self._generate_repo_name(client_info["name"], client_info["type"])

        # Check if repo exists
        repo_url = self._check_github_repo(repo_name)

        if not repo_url:
            # Create new repository
            repo_url = self._create_github_repo(repo_name, client_info)

        # Update deployment record
        self.deployment_tracker.update_github_repo(client_info["id"], repo_url, repo_name)

        return repo_url

    def _check_github_repo(self, repo_name: str) -> Optional[str]:
        """Check if GitHub repo exists."""
        if self.github_org:
            url = f"{self.github_api_base}/repos/{self.github_org}/{repo_name}"
        else:
            url = f"{self.github_api_base}/user/repos"

        response = requests.get(url, headers=self.github_headers)

        if response.status_code == 200:
            if self.github_org:
                return response.json()["html_url"]
            else:
                # Search through user repos
                repos = response.json()
                for repo in repos:
                    if repo["name"] == repo_name:
                        return repo["html_url"]

        return None

    def _create_github_repo(self, repo_name: str, client_info: Dict[str, str]) -> str:
        """Create new GitHub repository."""
        logger.info(f"Creating GitHub repository: {repo_name}")

        repo_data = {
            "name": repo_name,
            "description": f"{client_info['name']} - {client_info['type'].title()} Project",
            "private": True,
            "auto_init": True,
            "gitignore_template": self._get_gitignore_template(client_info["type"]),
        }

        if self.github_org:
            url = f"{self.github_api_base}/orgs/{self.github_org}/repos"
        else:
            url = f"{self.github_api_base}/user/repos"

        response = requests.post(url, headers=self.github_headers, json=repo_data)

        if response.status_code in [201, 200]:
            repo = response.json()
            logger.info(f"Created repository: {repo['html_url']}")

            # Set up branch protection
            self._setup_branch_protection(repo["full_name"])

            return repo["html_url"]
        else:
            raise Exception(f"Failed to create repo: {response.status_code} - {response.text}")

    def _setup_branch_protection(self, repo_full_name: str) -> None:
        """Set up branch protection rules."""
        url = f"{self.github_api_base}/repos/{repo_full_name}/branches/main/protection"

        protection_rules = {
            "required_status_checks": {"strict": True, "contexts": []},
            "enforce_admins": False,
            "required_pull_request_reviews": {
                "dismiss_stale_reviews": True,
                "require_code_owner_reviews": False,
                "required_approving_review_count": 1,
            },
            "restrictions": None,
            "allow_force_pushes": False,
            "allow_deletions": False,
        }

        try:
            response = requests.put(url, headers=self.github_headers, json=protection_rules)
            if response.status_code in [200, 201]:
                logger.info("Branch protection enabled for main branch")
        except Exception as e:
            logger.warning(f"Could not set branch protection: {str(e)}")

    def _ensure_vercel_project(
        self, client_info: Dict[str, str], deployment: Dict[str, Any]
    ) -> Tuple[str, str]:
        """Ensure Vercel project exists.

        Returns:
            Tuple of (project_id, project_name)
        """
        # Check if project already exists in deployment record
        if deployment.get("vercel_project_id"):
            logger.info(f"Using existing Vercel project: {deployment['vercel_project_id']}")
            return deployment["vercel_project_id"], deployment.get("metadata", {}).get(
                "vercel_project_name", ""
            )

        # Create new project
        project_id, project_name = self.vercel_manager.get_or_create_project(
            client_info["name"], client_info["type"]
        )

        # Update deployment record
        self.deployment_tracker.update_vercel_project(client_info["id"], project_id, project_name)

        return project_id, project_name

    def _trigger_deployment(
        self,
        client_info: Dict[str, str],
        repo_url: str,
        vercel_project_id: str,
        requirements: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Trigger deployment via GitHub Actions or direct Vercel API."""
        logger.info("Triggering deployment...")

        # For now, use direct Vercel deployment
        # In future, this could trigger GitHub Actions workflow

        # Prepare deployment command
        deploy_cmd = [
            "python",
            "scripts/deploy_to_vercel.py",
            "--token",
            self.vercel_token,
            "--project-id",
            vercel_project_id,
            "--branch",
            "main",
            "--commit",
            "initial",
            "--environment",
            "production",
            "--skip-validation",  # Skip for initial deployment
        ]

        try:
            # Run deployment
            result = subprocess.run(
                deploy_cmd,
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent,
            )

            if result.returncode != 0:
                raise Exception(f"Deployment failed: {result.stderr}")

            # Extract deployment URL from output
            deployment_url = None
            for line in result.stdout.split("\n"):
                if "URL:" in line and "https://" in line:
                    deployment_url = line.split("https://")[1].strip()
                    break

            if not deployment_url:
                raise Exception("No deployment URL found in output")

            return {
                "url": deployment_url,
                "deployment_id": f"dpl_{vercel_project_id}",  # Placeholder
                "status": "success",
            }

        except Exception as e:
            logger.error(f"Deployment failed: {str(e)}")
            raise

    def _update_deployment_record(
        self,
        client_id: str,
        deployment_result: Dict[str, Any],
        vercel_project_id: str,
        repo_url: str,
    ) -> None:
        """Update deployment record with results."""
        # Add deployment URL
        self.deployment_tracker.add_deployment_url(
            client_id,
            deployment_result["url"],
            deployment_result["deployment_id"],
            "production",
        )

        # Update status
        self.deployment_tracker.update_deployment_status(client_id, "deployed")

        logger.info(f"Deployment complete: https://{deployment_result['url']}")

    def _deploy_project(
        self,
        client_info: Dict[str, str],
        requirements: Dict[str, Any],
        deployment: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Deploy project with given client info and requirements."""
        try:
            # Ensure GitHub repo
            repo_url = self._ensure_github_repo(client_info, deployment)

            # Ensure Vercel project
            vercel_project_id, project_name = self._ensure_vercel_project(client_info, deployment)

            # Trigger deployment
            deployment_result = self._trigger_deployment(
                client_info, repo_url, vercel_project_id, requirements
            )

            # Update records
            self._update_deployment_record(
                client_info["id"], deployment_result, vercel_project_id, repo_url
            )

            return {
                "success": True,
                "deployment_url": deployment_result["url"],
                "project_id": vercel_project_id,
                "repo_url": repo_url,
                "client": client_info,
            }

        except Exception as e:
            logger.error(f"Deployment failed: {str(e)}")
            self.deployment_tracker.update_deployment_status(client_info["id"], "failed", str(e))
            raise

    def _sanitize_name(self, name: str) -> str:
        """Sanitize name for use in IDs."""
        return re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-")

    def _generate_repo_name(self, client_name: str, project_type: str) -> str:
        """Generate GitHub repository name."""
        sanitized = self._sanitize_name(client_name)
        return f"{sanitized}-{project_type}"

    def _get_gitignore_template(self, project_type: str) -> str:
        """Get appropriate gitignore template."""
        templates = {
            "site": "Node",
            "app": "Node",
            "api": "Python",
        }
        return templates.get(project_type, "Node")


# CLI commands
@click.group()
def cli():
    """Client deployment orchestrator CLI."""
    pass


@cli.command()
@click.option("--conversation-id", required=True, help="Conversation ID with requirements")
@click.option("--github-token", help="GitHub personal access token")
@click.option("--vercel-token", help="Vercel API token")
def deploy_conversation(
    conversation_id: str, github_token: Optional[str], vercel_token: Optional[str]
):
    """Deploy client project from conversation."""
    orchestrator = ClientDeploymentOrchestrator(
        github_token=github_token, vercel_token=vercel_token
    )

    try:
        result = orchestrator.deploy_from_conversation(conversation_id)

        click.echo("\n✅ Deployment Successful!")
        click.echo(f"   Client: {result['client']['name']}")
        click.echo(f"   Project Type: {result['client']['type']}")
        click.echo(f"   Vercel Project: {result['project_id']}")
        click.echo(f"   GitHub Repo: {result['repo_url']}")
        click.echo(f"   Live URL: https://{result['deployment_url']}")

    except Exception as e:
        click.echo(f"\n❌ Deployment Failed: {str(e)}")
        sys.exit(1)


@cli.command()
@click.option("--requirements", required=True, help="Requirements JSON file or string")
@click.option("--github-token", help="GitHub personal access token")
@click.option("--vercel-token", help="Vercel API token")
def deploy_requirements(
    requirements: str, github_token: Optional[str], vercel_token: Optional[str]
):
    """Deploy client project from requirements JSON."""
    orchestrator = ClientDeploymentOrchestrator(
        github_token=github_token, vercel_token=vercel_token
    )

    try:
        result = orchestrator.deploy_from_requirements(requirements)

        click.echo("\n✅ Deployment Successful!")
        click.echo(f"   Client: {result['client']['name']}")
        click.echo(f"   Project Type: {result['client']['type']}")
        click.echo(f"   Vercel Project: {result['project_id']}")
        click.echo(f"   GitHub Repo: {result['repo_url']}")
        click.echo(f"   Live URL: https://{result['deployment_url']}")

    except Exception as e:
        click.echo(f"\n❌ Deployment Failed: {str(e)}")
        sys.exit(1)


@cli.command()
@click.option("--status", help="Filter by status")
def list_deployments(status: Optional[str]):
    """List all client deployments."""
    tracker = DeploymentTracker()

    deployments = tracker.list_client_deployments(status_filter=status)

    if not deployments:
        click.echo("No deployments found")
        return

    click.echo(f"\nFound {len(deployments)} deployments:\n")

    for dep in deployments:
        click.echo(f"• {dep['client_name']} ({dep['project_type']})")
        click.echo(f"  ID: {dep['client_id']}")
        click.echo(f"  Status: {dep['status']}")
        click.echo(f"  Vercel: {dep.get('vercel_project_id', 'Not set')}")
        click.echo(f"  GitHub: {dep.get('github_repo_url', 'Not set')}")

        if dep.get("deployment_urls"):
            latest = dep["deployment_urls"][-1]
            click.echo(f"  Latest: https://{latest['url']}")

        click.echo()


if __name__ == "__main__":
    cli()
