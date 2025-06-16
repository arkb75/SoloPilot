#!/usr/bin/env python3
"""
SonarCloud Integration for SoloPilot

Fetches quality metrics and findings from SonarCloud API to enhance AI code reviews.
"""

import json
import os
import re
import subprocess
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests


class SonarCloudClient:
    """Client for SonarCloud API integration."""

    def __init__(self, project_key: str = None, organization: str = None):
        """
        Initialize SonarCloud client.
        
        Args:
            project_key: SonarCloud project key (auto-detected if None)
            organization: SonarCloud organization key (default: solopilot-clients)
        """
        self.project_key = project_key
        self.organization = organization or os.getenv("SONAR_ORGANIZATION", "solopilot-clients")
        self.base_url = "https://sonarcloud.io/api"
        self.token = os.getenv("SONAR_TOKEN")
        self.no_network = os.getenv("NO_NETWORK") == "1"
        
    def is_available(self) -> bool:
        """Check if SonarCloud integration is available."""
        return not self.no_network and bool(self.token)
    
    @staticmethod
    def parse_git_url(git_url: str) -> Optional[Dict[str, str]]:
        """
        Parse a Git URL to extract owner and repository name.
        
        Args:
            git_url: Git repository URL
            
        Returns:
            Dictionary with 'owner' and 'repo' keys, or None if parsing fails
        """
        if not git_url:
            return None
        
        # Handle different Git URL formats
        patterns = [
            # HTTPS: https://github.com/owner/repo.git
            r'https://(?:www\.)?github\.com/([^/]+)/([^/]+)(?:\.git)?/?$',
            # SSH: git@github.com:owner/repo.git  
            r'git@github\.com:([^/]+)/([^/]+)(?:\.git)?/?$',
            # GitLab HTTPS: https://gitlab.com/owner/repo.git
            r'https://(?:www\.)?gitlab\.com/([^/]+)/([^/]+)(?:\.git)?/?$',
            # GitLab SSH: git@gitlab.com:owner/repo.git
            r'git@gitlab\.com:([^/]+)/([^/]+)(?:\.git)?/?$',
        ]
        
        for pattern in patterns:
            match = re.match(pattern, git_url.strip())
            if match:
                owner, repo = match.groups()
                # Remove .git suffix if present
                repo = repo.replace('.git', '')
                return {
                    'owner': owner,
                    'repo': repo,
                    'project_key': f"{owner}_{repo}"  # SonarCloud project naming convention
                }
        
        return None
    
    def auto_detect_project(self, git_url: str = None) -> bool:
        """
        Auto-detect project key from Git URL or current repository.
        
        Args:
            git_url: Optional Git URL, will detect from current repo if None
            
        Returns:
            True if project was successfully detected
        """
        if not git_url:
            # Try to get Git URL from current repository
            try:
                result = subprocess.run(
                    ["git", "remote", "get-url", "origin"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    git_url = result.stdout.strip()
                else:
                    return False
            except (subprocess.TimeoutExpired, FileNotFoundError):
                return False
        
        # Parse the Git URL
        parsed = self.parse_git_url(git_url)
        if parsed:
            self.project_key = parsed['project_key']
            print(f"🔍 Auto-detected SonarCloud project: {self.project_key}")
            return True
        
        return False
    
    def create_project(self, project_name: str, project_key: str = None, visibility: str = "private") -> Optional[Dict[str, Any]]:
        """
        Create a new SonarCloud project.
        
        Args:
            project_name: Human-readable project name
            project_key: Unique project key (auto-generated if None)
            visibility: Project visibility ("public" or "private")
            
        Returns:
            Dictionary with project details or None if creation failed
        """
        if not self.is_available():
            print("❌ SonarCloud not available (offline mode or missing token)")
            return None
        
        # Auto-generate project key if not provided
        if not project_key:
            # Sanitize project name for use as key
            project_key = re.sub(r'[^a-zA-Z0-9_-]', '_', project_name.lower())
            project_key = f"{self.organization}_{project_key}"
        
        try:
            url = f"{self.base_url}/projects/create"
            data = {
                "name": project_name,
                "project": project_key,
                "organization": self.organization,
                "visibility": visibility
            }
            
            print(f"🔨 Creating SonarCloud project: {project_key}")
            
            response = requests.post(
                url,
                data=data,  # Use form data as recommended by SonarCloud
                auth=(self.token, ""),
                timeout=15
            )
            
            if response.status_code == 200:
                project_data = response.json()
                project_info = project_data.get("project", {})
                
                # Update current project key
                self.project_key = project_info.get("key", project_key)
                
                print(f"✅ SonarCloud project created: {self.project_key}")
                return {
                    "project_key": self.project_key,
                    "project_name": project_info.get("name", project_name),
                    "organization": self.organization,
                    "visibility": project_info.get("visibility", visibility),
                    "url": f"https://sonarcloud.io/project/overview?id={self.project_key}"
                }
            elif response.status_code == 400:
                # Project might already exist
                error_msg = response.text
                if "already exists" in error_msg.lower():
                    print(f"⚠️ SonarCloud project already exists: {project_key}")
                    self.project_key = project_key
                    return {
                        "project_key": project_key,
                        "project_name": project_name,
                        "organization": self.organization,
                        "visibility": visibility,
                        "url": f"https://sonarcloud.io/project/overview?id={project_key}",
                        "existed": True
                    }
                else:
                    print(f"❌ SonarCloud project creation failed: {error_msg}")
                    return None
            else:
                print(f"❌ SonarCloud API error: {response.status_code} - {response.text}")
                return None
                
        except (requests.RequestException, json.JSONDecodeError) as e:
            print(f"❌ SonarCloud project creation failed: {e}")
            return None
    
    def setup_project_from_git_url(self, git_url: str, project_name: str = None) -> Optional[Dict[str, Any]]:
        """
        Complete setup: parse Git URL, create SonarCloud project, and configure client.
        
        Args:
            git_url: Git repository URL
            project_name: Optional custom project name (defaults to repo name)
            
        Returns:
            Dictionary with project setup results
        """
        # Parse Git URL
        parsed = self.parse_git_url(git_url)
        if not parsed:
            print(f"❌ Failed to parse Git URL: {git_url}")
            return None
        
        # Generate project name if not provided
        if not project_name:
            project_name = f"{parsed['owner']} - {parsed['repo']}"
        
        # Create SonarCloud project
        project_result = self.create_project(
            project_name=project_name,
            project_key=parsed['project_key']
        )
        
        if project_result:
            project_result.update({
                "git_url": git_url,
                "git_owner": parsed['owner'],
                "git_repo": parsed['repo']
            })
        
        return project_result
    
    def get_project_metrics(self) -> Optional[Dict[str, Any]]:
        """
        Fetch project quality metrics from SonarCloud.
        
        Returns:
            Dictionary with quality metrics or None if unavailable
        """
        if not self.is_available():
            return None
        
        try:
            url = f"{self.base_url}/measures/component"
            params = {
                "component": self.project_key,
                "metricKeys": "bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density,reliability_rating,security_rating,sqale_rating"
            }
            
            response = requests.get(
                url,
                params=params,
                auth=(self.token, ""),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_metrics(data)
            else:
                print(f"SonarCloud API error: {response.status_code}")
                return None
                
        except (requests.RequestException, json.JSONDecodeError) as e:
            print(f"SonarCloud metrics fetch failed: {e}")
            return None
    
    def get_project_issues(self, severity: str = "MAJOR") -> List[Dict[str, Any]]:
        """
        Fetch project issues from SonarCloud.
        
        Args:
            severity: Minimum severity level (INFO, MINOR, MAJOR, CRITICAL, BLOCKER)
            
        Returns:
            List of issues
        """
        if not self.is_available():
            return []
        
        try:
            url = f"{self.base_url}/issues/search"
            params = {
                "componentKeys": self.project_key,
                "severities": f"{severity},CRITICAL,BLOCKER",
                "statuses": "OPEN,CONFIRMED,REOPENED",
                "ps": 100  # Page size
            }
            
            response = requests.get(
                url,
                params=params,
                auth=(self.token, ""),
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_issues(data.get("issues", []))
            else:
                print(f"SonarCloud issues API error: {response.status_code}")
                return []
                
        except (requests.RequestException, json.JSONDecodeError) as e:
            print(f"SonarCloud issues fetch failed: {e}")
            return []
    
    def get_quality_gate_status(self) -> Optional[Dict[str, Any]]:
        """
        Get quality gate status for the project.
        
        Returns:
            Quality gate status information
        """
        if not self.is_available():
            return None
        
        try:
            url = f"{self.base_url}/qualitygates/project_status"
            params = {"projectKey": self.project_key}
            
            response = requests.get(
                url,
                params=params,
                auth=(self.token, ""),
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("projectStatus", {})
            else:
                return None
                
        except (requests.RequestException, json.JSONDecodeError) as e:
            print(f"SonarCloud quality gate fetch failed: {e}")
            return None
    
    def _parse_metrics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse SonarCloud metrics response."""
        metrics = {}
        
        for measure in data.get("component", {}).get("measures", []):
            metric_key = measure.get("metric")
            value = measure.get("value", "0")
            
            # Convert numeric values
            try:
                if "." in value:
                    metrics[metric_key] = float(value)
                else:
                    metrics[metric_key] = int(value)
            except ValueError:
                metrics[metric_key] = value
        
        return {
            "bugs": metrics.get("bugs", 0),
            "vulnerabilities": metrics.get("vulnerabilities", 0),
            "code_smells": metrics.get("code_smells", 0),
            "coverage": metrics.get("coverage", 0.0),
            "duplicated_lines_density": metrics.get("duplicated_lines_density", 0.0),
            "reliability_rating": metrics.get("reliability_rating", "A"),
            "security_rating": metrics.get("security_rating", "A"),
            "maintainability_rating": metrics.get("sqale_rating", "A"),
            "timestamp": time.time()
        }
    
    def _parse_issues(self, issues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse SonarCloud issues response."""
        parsed_issues = []
        
        for issue in issues:
            parsed_issue = {
                "key": issue.get("key"),
                "rule": issue.get("rule"),
                "severity": issue.get("severity"),
                "type": issue.get("type"),
                "component": issue.get("component", "").split(":")[-1],  # Extract filename
                "line": issue.get("line", 0),
                "message": issue.get("message", ""),
                "status": issue.get("status"),
                "creation_date": issue.get("creationDate"),
                "tags": issue.get("tags", [])
            }
            parsed_issues.append(parsed_issue)
        
        return parsed_issues
    
    def generate_review_summary(self) -> Dict[str, Any]:
        """
        Generate comprehensive review summary from SonarCloud data.
        
        Returns:
            Dictionary with review summary for AI integration
        """
        if not self.is_available():
            return {
                "available": False,
                "reason": "offline_mode" if self.no_network else "no_token"
            }
        
        metrics = self.get_project_metrics()
        issues = self.get_project_issues()
        quality_gate = self.get_quality_gate_status()
        
        summary = {
            "available": True,
            "metrics": metrics or {},
            "issues": issues,
            "quality_gate": quality_gate,
            "analysis": self._analyze_quality_data(metrics, issues, quality_gate)
        }
        
        return summary
    
    def _analyze_quality_data(self, metrics: Optional[Dict], issues: List[Dict], quality_gate: Optional[Dict]) -> Dict[str, Any]:
        """Analyze quality data and provide insights."""
        analysis = {
            "overall_rating": "unknown",
            "critical_issues": 0,
            "recommendations": [],
            "blockers": []
        }
        
        if not metrics:
            return analysis
        
        # Analyze metrics
        bugs = metrics.get("bugs", 0)
        vulnerabilities = metrics.get("vulnerabilities", 0)
        code_smells = metrics.get("code_smells", 0)
        coverage = metrics.get("coverage", 0)
        
        # Overall rating logic
        if vulnerabilities > 0 or bugs > 5:
            analysis["overall_rating"] = "poor"
        elif code_smells > 20 or coverage < 50:
            analysis["overall_rating"] = "needs_improvement"
        elif coverage > 80 and code_smells < 10:
            analysis["overall_rating"] = "good"
        else:
            analysis["overall_rating"] = "fair"
        
        # Count critical issues
        critical_issues = [i for i in issues if i.get("severity") in ["CRITICAL", "BLOCKER"]]
        analysis["critical_issues"] = len(critical_issues)
        
        # Generate recommendations
        if vulnerabilities > 0:
            analysis["recommendations"].append(f"Fix {vulnerabilities} security vulnerabilities immediately")
        if bugs > 0:
            analysis["recommendations"].append(f"Address {bugs} bugs before promotion")
        if coverage < 70:
            analysis["recommendations"].append(f"Improve test coverage from {coverage:.1f}% to >70%")
        if code_smells > 15:
            analysis["recommendations"].append(f"Refactor {code_smells} code smells for maintainability")
        
        # Identify blockers
        for issue in critical_issues:
            if issue.get("type") == "VULNERABILITY":
                analysis["blockers"].append(f"Security vulnerability: {issue.get('message', 'Unknown')}")
            elif issue.get("severity") == "BLOCKER":
                analysis["blockers"].append(f"Blocker issue: {issue.get('message', 'Unknown')}")
        
        return analysis


def main():
    """Main function for testing SonarCloud integration."""
    print("🔍 SonarCloud Integration Test")
    print("=" * 50)
    
    # Test Git URL parsing
    test_urls = [
        "https://github.com/arkb75/SoloPilot.git",
        "git@github.com:client/demo-project.git",
        "https://gitlab.com/company/web-app.git"
    ]
    
    print("\n📋 Testing Git URL parsing:")
    for url in test_urls:
        parsed = SonarCloudClient.parse_git_url(url)
        if parsed:
            print(f"  ✅ {url}")
            print(f"     → Owner: {parsed['owner']}, Repo: {parsed['repo']}, Project Key: {parsed['project_key']}")
        else:
            print(f"  ❌ {url} - parsing failed")
    
    # Test SonarCloud client
    client = SonarCloudClient()
    print(f"\n🔗 SonarCloud Status:")
    print(f"  Available: {client.is_available()}")
    print(f"  Organization: {client.organization}")
    print(f"  Token configured: {'Yes' if client.token else 'No'}")
    
    # Test auto-detection from current repo
    print(f"\n🔍 Auto-detecting current repository:")
    if client.auto_detect_project():
        print(f"  ✅ Detected project: {client.project_key}")
    else:
        print(f"  ⚠️ Could not auto-detect project")
    
    # Test project creation (only if token is available)
    if client.is_available():
        print(f"\n🔨 Testing project setup (example URL):")
        test_url = "https://github.com/demo-client/sample-project.git"
        result = client.setup_project_from_git_url(test_url, "Demo Sample Project")
        if result:
            print(f"  ✅ Project setup completed:")
            for key, value in result.items():
                print(f"    {key}: {value}")
        else:
            print(f"  ❌ Project setup failed")
    else:
        print(f"\n⚠️ Skipping project creation test (SonarCloud not available)")
        print("   Set SONAR_TOKEN environment variable to test project creation")
    
    print("\n" + "=" * 50)


if __name__ == "__main__":
    main()