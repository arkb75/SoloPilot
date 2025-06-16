#!/usr/bin/env python3
"""
SonarCloud Integration for SoloPilot

Fetches quality metrics and findings from SonarCloud API to enhance AI code reviews.
"""

import json
import os
import subprocess
import time
from typing import Any, Dict, List, Optional

import requests


class SonarCloudClient:
    """Client for SonarCloud API integration."""

    def __init__(self, project_key: str = "solopilot_ai_automation", organization: str = "solopilot"):
        """
        Initialize SonarCloud client.
        
        Args:
            project_key: SonarCloud project key
            organization: SonarCloud organization key
        """
        self.project_key = project_key
        self.organization = organization
        self.base_url = "https://sonarcloud.io/api"
        self.token = os.getenv("SONAR_TOKEN")
        self.no_network = os.getenv("NO_NETWORK") == "1"
        
    def is_available(self) -> bool:
        """Check if SonarCloud integration is available."""
        return not self.no_network and bool(self.token)
    
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
    client = SonarCloudClient()
    
    print("SonarCloud Integration Test")
    print(f"Available: {client.is_available()}")
    
    if client.is_available():
        summary = client.generate_review_summary()
        print(f"Quality Analysis: {json.dumps(summary, indent=2)}")
    else:
        print("SonarCloud integration not available (offline mode or missing token)")


if __name__ == "__main__":
    main()