#!/usr/bin/env python3
"""
SonarCloud Integration for SoloPilot

Fetches quality metrics and findings from SonarCloud API to enhance AI code reviews.
Enhanced with robust error handling, retry logic, and comprehensive auto-provisioning.
"""

import json
import os
import re
import subprocess
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from functools import wraps

import requests


def retry_on_failure(max_retries=3, backoff_factor=1.0):
    """Decorator to retry function calls on failure with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(self, *args, **kwargs)
                except requests.exceptions.RequestException as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = backoff_factor * (2 ** attempt)
                        print(f"⚠️ SonarCloud API call failed (attempt {attempt + 1}/{max_retries}): {e}")
                        print(f"   Retrying in {wait_time:.1f} seconds...")
                        time.sleep(wait_time)
                    else:
                        print(f"❌ SonarCloud API call failed after {max_retries} attempts: {e}")
                except Exception as e:
                    # Non-retryable exceptions
                    print(f"❌ SonarCloud API call failed with non-retryable error: {e}")
                    raise
            
            raise last_exception
        return wrapper
    return decorator


class SonarCloudClient:
    """Client for SonarCloud API integration with robust error handling and retry logic."""

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
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a configured requests session with proper headers and timeouts."""
        session = requests.Session()
        session.auth = (self.token or "", "")
        session.headers.update({
            'User-Agent': 'SoloPilot-SonarCloud-Integration/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded'
        })
        return session
    
    def is_available(self) -> bool:
        """Check if SonarCloud integration is available."""
        return not self.no_network and bool(self.token)
    
    def validate_configuration(self) -> Dict[str, Any]:
        """Validate SonarCloud configuration and connectivity."""
        validation = {
            "valid": False,
            "issues": [],
            "organization_exists": False,
            "token_valid": False
        }
        
        if not self.token:
            validation["issues"].append("SONAR_TOKEN environment variable not set")
            return validation
        
        if self.no_network:
            validation["issues"].append("NO_NETWORK=1 - SonarCloud integration disabled")
            return validation
        
        try:
            # Test token validity by fetching organization info
            response = self.session.get(
                f"{self.base_url}/organizations/search",
                params={"organizations": self.organization},
                timeout=10
            )
            
            if response.status_code == 200:
                validation["token_valid"] = True
                orgs = response.json().get("organizations", [])
                validation["organization_exists"] = any(
                    org.get("key") == self.organization for org in orgs
                )
                
                if not validation["organization_exists"]:
                    validation["issues"].append(f"Organization '{self.organization}' not found or no access")
                else:
                    validation["valid"] = True
            else:
                validation["issues"].append(f"Token validation failed: HTTP {response.status_code}")
                
        except Exception as e:
            validation["issues"].append(f"Configuration validation failed: {e}")
        
        return validation
    
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
    
    def _check_project_exists(self, project_key: str) -> Optional[Dict[str, Any]]:
        """Check if a project already exists in SonarCloud."""
        try:
            response = self.session.get(
                f"{self.base_url}/projects/search",
                params={"projects": project_key, "organization": self.organization},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                projects = data.get("components", [])
                for project in projects:
                    if project.get("key") == project_key:
                        return project
            
        except Exception as e:
            print(f"⚠️ Could not check if project exists: {e}")
        
        return None
    
    def _verify_project_creation(self, project_key: str) -> bool:
        """Verify that a project was successfully created."""
        try:
            # Wait a moment for eventual consistency
            time.sleep(2)
            return self._check_project_exists(project_key) is not None
        except Exception:
            return False
    
    @retry_on_failure(max_retries=3, backoff_factor=1.5)
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
        # Validate configuration first
        config_validation = self.validate_configuration()
        if not config_validation["valid"]:
            print("❌ SonarCloud configuration invalid:")
            for issue in config_validation["issues"]:
                print(f"   - {issue}")
            return None
        
        # Auto-generate project key if not provided
        if not project_key:
            # Sanitize project name for use as key (SonarCloud requirements)
            sanitized_name = re.sub(r'[^a-zA-Z0-9._-]', '_', project_name)
            sanitized_name = re.sub(r'_+', '_', sanitized_name).strip('_')  # Remove multiple underscores
            project_key = f"{self.organization}_{sanitized_name}".lower()
            
            # Ensure project key meets SonarCloud requirements
            if len(project_key) > 400:
                project_key = project_key[:400]
            if not re.match(r'^[a-zA-Z0-9._-]+$', project_key):
                raise ValueError(f"Generated project key '{project_key}' contains invalid characters")
        
        print(f"🔨 Creating SonarCloud project: {project_key}")
        
        # Check if project already exists first
        existing_project = self._check_project_exists(project_key)
        if existing_project:
            print(f"⚠️ SonarCloud project already exists: {project_key}")
            self.project_key = project_key
            return {
                "project_key": project_key,
                "project_name": existing_project.get("name", project_name),
                "organization": self.organization,
                "visibility": existing_project.get("visibility", visibility),
                "url": f"https://sonarcloud.io/project/overview?id={project_key}",
                "existed": True
            }
        
        try:
            url = f"{self.base_url}/projects/create"
            data = {
                "name": project_name[:200],  # SonarCloud name limit
                "project": project_key,
                "organization": self.organization,
                "visibility": visibility
            }
            
            response = self.session.post(
                url,
                data=data,
                timeout=30  # Increased timeout for project creation
            )
            
            if response.status_code == 200:
                project_data = response.json()
                project_info = project_data.get("project", {})
                
                # Update current project key
                self.project_key = project_info.get("key", project_key)
                
                print(f"✅ SonarCloud project created: {self.project_key}")
                result = {
                    "project_key": self.project_key,
                    "project_name": project_info.get("name", project_name),
                    "organization": self.organization,
                    "visibility": project_info.get("visibility", visibility),
                    "url": f"https://sonarcloud.io/project/overview?id={self.project_key}"
                }
                
                # Verify project was created successfully
                if self._verify_project_creation(self.project_key):
                    print(f"✅ Project creation verified: {self.project_key}")
                    return result
                else:
                    print(f"⚠️ Project created but verification failed: {self.project_key}")
                    return result  # Return anyway, might just be eventual consistency
                    
            elif response.status_code == 400:
                # Handle various 400 error cases
                try:
                    error_data = response.json()
                    error_msg = error_data.get("errors", [{}])[0].get("msg", response.text)
                except:
                    error_msg = response.text
                
                if "already exists" in error_msg.lower() or "already exist" in error_msg.lower():
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
                elif "invalid" in error_msg.lower():
                    print(f"❌ Invalid project parameters: {error_msg}")
                    print(f"   Project key: {project_key}")
                    print(f"   Organization: {self.organization}")
                    return None
                else:
                    print(f"❌ SonarCloud project creation failed (400): {error_msg}")
                    return None
            elif response.status_code == 403:
                print(f"❌ Access denied. Check organization permissions and token scopes.")
                print(f"   Organization: {self.organization}")
                print(f"   Required permissions: Project Creation")
                return None
            elif response.status_code == 401:
                print(f"❌ Authentication failed. Check SONAR_TOKEN validity.")
                return None
            else:
                print(f"❌ SonarCloud API error: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ SonarCloud project creation failed: {e}")
            raise  # Let retry decorator handle it
    
    def setup_project_from_git_url(self, git_url: str, project_name: str = None) -> Optional[Dict[str, Any]]:
        """
        Complete setup: parse Git URL, create SonarCloud project, and configure client.
        
        Args:
            git_url: Git repository URL
            project_name: Optional custom project name (defaults to repo name)
            
        Returns:
            Dictionary with project setup results
        """
        print(f"🔧 Setting up SonarCloud project from Git URL: {git_url}")
        
        # Validate configuration first
        config_validation = self.validate_configuration()
        if not config_validation["valid"]:
            print("❌ Cannot setup project due to configuration issues:")
            for issue in config_validation["issues"]:
                print(f"   - {issue}")
            return None
        
        # Parse Git URL
        parsed = self.parse_git_url(git_url)
        if not parsed:
            print(f"❌ Failed to parse Git URL: {git_url}")
            print("   Supported formats:")
            print("   - https://github.com/owner/repo.git")
            print("   - git@github.com:owner/repo.git")
            print("   - https://gitlab.com/owner/repo.git")
            return None
        
        print(f"✅ Parsed Git URL: {parsed['owner']}/{parsed['repo']}")
        
        # Generate project name if not provided
        if not project_name:
            project_name = f"{parsed['owner']} - {parsed['repo']}"
        
        # Create SonarCloud project with robust error handling
        try:
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
                
                print(f"🎉 SonarCloud project setup complete!")
                print(f"   Project: {project_result['project_key']}")
                print(f"   URL: {project_result['url']}")
                
                # Additional setup steps
                self._configure_project_settings(project_result['project_key'])
                
                return project_result
            else:
                print(f"❌ Project creation failed for {git_url}")
                return None
                
        except Exception as e:
            print(f"❌ Failed to setup SonarCloud project: {e}")
            return None
    
    def _configure_project_settings(self, project_key: str):
        """Configure additional project settings after creation."""
        try:
            # Set quality gate (if different from default)
            self._set_quality_gate(project_key, "Sonar way")
            
            # Configure main branch
            self._configure_main_branch(project_key, "main")
            
        except Exception as e:
            print(f"⚠️ Could not configure project settings: {e}")
    
    def _set_quality_gate(self, project_key: str, gate_name: str):
        """Set quality gate for the project."""
        try:
            response = self.session.post(
                f"{self.base_url}/qualitygates/select",
                data={
                    "projectKey": project_key,
                    "gateName": gate_name
                },
                timeout=10
            )
            if response.status_code == 204:
                print(f"✅ Quality gate '{gate_name}' assigned to project")
        except Exception as e:
            print(f"⚠️ Could not set quality gate: {e}")
    
    def _configure_main_branch(self, project_key: str, branch_name: str):
        """Configure the main branch for the project."""
        try:
            response = self.session.post(
                f"{self.base_url}/project_branches/rename",
                data={
                    "project": project_key,
                    "name": branch_name
                },
                timeout=10
            )
            # 404 is expected if branch doesn't exist yet
            if response.status_code in [200, 404]:
                print(f"✅ Main branch configured: {branch_name}")
        except Exception as e:
            print(f"⚠️ Could not configure main branch: {e}")
    
    @retry_on_failure(max_retries=2, backoff_factor=1.0)
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
            
            response = self.session.get(
                url,
                params=params,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_metrics(data)
            else:
                print(f"SonarCloud API error: {response.status_code}")
                return None
                
        except Exception as e:
            print(f"SonarCloud metrics fetch failed: {e}")
            raise  # Let retry decorator handle it
    
    @retry_on_failure(max_retries=2, backoff_factor=1.0)
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
            
            response = self.session.get(
                url,
                params=params,
                timeout=15
            )
            
            if response.status_code == 200:
                data = response.json()
                return self._parse_issues(data.get("issues", []))
            else:
                print(f"SonarCloud issues API error: {response.status_code}")
                return []
                
        except Exception as e:
            print(f"SonarCloud issues fetch failed: {e}")
            raise  # Let retry decorator handle it
    
    @retry_on_failure(max_retries=2, backoff_factor=1.0)
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
            
            response = self.session.get(
                url,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("projectStatus", {})
            else:
                return None
                
        except Exception as e:
            print(f"SonarCloud quality gate fetch failed: {e}")
            raise  # Let retry decorator handle it
    
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
    
    # Test configuration validation
    print(f"\n🔧 Configuration Validation:")
    config_validation = client.validate_configuration()
    print(f"  Valid: {config_validation['valid']}")
    if config_validation['issues']:
        print("  Issues:")
        for issue in config_validation['issues']:
            print(f"    - {issue}")
    
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