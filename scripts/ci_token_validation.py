#!/usr/bin/env python3
"""
CI Token Validation Script

Ensures that dev-agent context never exceeds 2000 tokens to prevent CI failures.
This script must pass for all commits to prevent unsustainable API costs.
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.dev.context_engine.serena_engine import SerenaContextEngine
from agents.dev.context_engine.progressive_context import ContextTier


class CITokenValidator:
    """Validates token limits for CI/CD pipeline."""
    
    # CRITICAL: CI must fail if any context exceeds this limit
    MAX_TOKENS_CI_LIMIT = 2000
    
    # Target ranges for different modes
    BALANCED_TARGET_MIN = 1000
    BALANCED_TARGET_MAX = 1500
    MINIMAL_TARGET_MAX = 800
    
    def __init__(self):
        """Initialize CI validator."""
        self.results = {
            "tests_passed": 0,
            "tests_failed": 0,
            "violations": [],
            "performance_metrics": {},
            "mode_averages": {}
        }
    
    def create_test_scenarios(self) -> List[Tuple[str, str, str]]:
        """
        Create comprehensive test scenarios covering typical dev-agent usage.
        
        Returns:
            List of (scenario_name, prompt, expected_mode) tuples
        """
        return [
            # MINIMAL mode scenarios
            ("Simple Fix", "Fix the typo in the error message", "MINIMAL"),
            ("Add Docstring", "Add a docstring to the authenticate method", "MINIMAL"),
            ("Rename Variable", "Change variable name from 'user' to 'username'", "MINIMAL"),
            ("Update Import", "Update the import statement for the new module", "MINIMAL"),
            ("Format Code", "Format the code according to PEP 8 standards", "MINIMAL"),
            
            # BALANCED mode scenarios
            ("OAuth Implementation", "Implement OAuth2 authentication", "BALANCED"),
            ("Error Handling", "Add comprehensive error handling to the API", "BALANCED"),
            ("Session Management", "Debug session management issues", "BALANCED"),
            ("Rate Limiting", "Implement rate limiting for API endpoints", "BALANCED"),
            ("Input Validation", "Add input validation to user registration", "BALANCED"),
            ("Performance Optimization", "Optimize database query performance", "BALANCED"),
            
            # COMPREHENSIVE mode scenarios (should be rare)
            ("Architecture Review", "Provide complete architecture analysis", "COMPREHENSIVE"),
            ("System Design", "Design comprehensive security system", "COMPREHENSIVE"),
        ]
    
    def create_sample_project(self) -> Path:
        """Create a realistic sample project for testing."""
        temp_dir = Path(tempfile.mkdtemp())
        
        # Create comprehensive authentication system
        auth_code = '''
import hashlib
import jwt
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

@dataclass
class User:
    id: int
    username: str
    email: str
    password_hash: str
    roles: List[str]
    created_at: datetime
    last_login: Optional[datetime] = None

class AuthenticationService:
    """
    Comprehensive authentication service supporting multiple auth methods.
    Handles OAuth2, JWT tokens, session management, and security policies.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.oauth_client = OAuthClient(config.get('oauth_settings'))
        self.session_store = SessionStore(config.get('session_config'))
        self.security_policy = SecurityPolicy(config.get('security_config'))
        self.user_repository = UserRepository(config.get('database_url'))
        self.failed_attempts = {}
    
    def authenticate_user(self, username: str, password: str, ip_address: str = None) -> Optional[Dict[str, Any]]:
        """
        Authenticate user with username and password.
        
        Args:
            username: User's username
            password: User's password  
            ip_address: Client IP address for security tracking
            
        Returns:
            Authentication result with user info and session token
        """
        try:
            # Rate limiting check
            if not self._check_rate_limit(username, ip_address):
                self.logger.warning(f"Rate limit exceeded for user: {username}")
                return None
            
            # Validate credentials
            user = self._validate_credentials(username, password)
            if not user:
                self._record_failed_attempt(username, ip_address)
                return None
            
            # Check security policies
            if not self.security_policy.validate_user_access(user, ip_address):
                self.logger.warning(f"Security policy violation for user: {username}")
                return None
            
            # Create session
            session = self._create_user_session(user, ip_address)
            self.logger.info(f"Successful authentication for user: {username}")
            
            return {
                'user': user,
                'session': session,
                'token': self._generate_jwt_token(user),
                'expires_at': session.expires_at,
                'permissions': self._get_user_permissions(user)
            }
            
        except Exception as e:
            self.logger.error(f"Authentication error for {username}: {e}")
            return None
    
    def oauth_authenticate(self, oauth_token: str, provider: str, ip_address: str = None) -> Optional[Dict[str, Any]]:
        """
        Authenticate user using OAuth2 token.
        
        Args:
            oauth_token: OAuth2 access token
            provider: OAuth provider name (google, github, etc.)
            ip_address: Client IP address
            
        Returns:
            Authentication result with user info and session
        """
        try:
            # Verify OAuth token with provider
            user_info = self.oauth_client.verify_token(oauth_token, provider)
            if not user_info:
                self.logger.warning(f"Invalid OAuth token for provider: {provider}")
                return None
            
            # Get or create user from OAuth info
            user = self._get_or_create_oauth_user(user_info, provider)
            
            # Security policy check
            if not self.security_policy.validate_user_access(user, ip_address):
                self.logger.warning(f"OAuth security policy violation for user: {user.username}")
                return None
            
            # Create session
            session = self._create_user_session(user, ip_address)
            self.logger.info(f"Successful OAuth authentication for user: {user.username}")
            
            return {
                'user': user,
                'session': session,
                'token': self._generate_jwt_token(user),
                'oauth_info': user_info,
                'provider': provider
            }
            
        except Exception as e:
            self.logger.error(f"OAuth authentication error: {e}")
            return None

class OAuthClient:
    """OAuth2 client for external authentication providers."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.providers = {
            'google': GoogleOAuthProvider(config.get('google')),
            'github': GitHubOAuthProvider(config.get('github')),
            'microsoft': MicrosoftOAuthProvider(config.get('microsoft'))
        }
    
    def verify_token(self, token: str, provider: str) -> Optional[Dict[str, Any]]:
        """Verify OAuth token with specific provider."""
        if provider not in self.providers:
            raise ValueError(f"Unsupported OAuth provider: {provider}")
        
        return self.providers[provider].verify_token(token)

class SecurityPolicy:
    """Security policy enforcement for authentication."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.max_failed_attempts = config.get('max_failed_attempts', 5)
        self.lockout_duration = config.get('lockout_duration', 900)  # 15 minutes
        
    def validate_user_access(self, user: User, ip_address: str = None) -> bool:
        """Validate user meets security access requirements."""
        # Check if user account is locked
        if self._is_account_locked(user.username):
            return False
        
        # Check IP-based restrictions
        if ip_address and not self._is_ip_allowed(ip_address):
            return False
        
        # Check user roles and permissions
        if not self._validate_user_roles(user):
            return False
        
        return True

class SessionStore:
    """Session storage and management."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.sessions = {}  # In-memory store (use Redis in production)
    
    def save(self, session: 'Session') -> bool:
        """Save session to store."""
        self.sessions[session.session_id] = session
        return True
    
    def get(self, session_id: str) -> Optional['Session']:
        """Get session by ID."""
        return self.sessions.get(session_id)
    
    def delete(self, session_id: str) -> bool:
        """Delete session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False
'''
        
        # Write files
        (temp_dir / "auth.py").write_text(auth_code)
        
        # Create additional files to make it realistic
        api_code = '''
from flask import Flask, request, jsonify
from auth import AuthenticationService

app = Flask(__name__)
auth_service = AuthenticationService({})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    result = auth_service.authenticate_user(
        data.get('username'),
        data.get('password'),
        request.remote_addr
    )
    
    if result:
        return jsonify(result)
    else:
        return jsonify({'error': 'Authentication failed'}), 401

@app.route('/api/oauth/login', methods=['POST'])
def oauth_login():
    data = request.json
    result = auth_service.oauth_authenticate(
        data.get('token'),
        data.get('provider'),
        request.remote_addr
    )
    
    if result:
        return jsonify(result)
    else:
        return jsonify({'error': 'OAuth authentication failed'}), 401
'''
        (temp_dir / "api.py").write_text(api_code)
        
        # Create milestone
        milestone_dir = temp_dir / "output" / "dev" / "auth_milestone"
        milestone_dir.mkdir(parents=True)
        
        milestone_data = {
            "components": ["AuthenticationService", "OAuthClient", "SecurityPolicy", "SessionStore"],
            "functions": ["authenticate_user", "oauth_authenticate", "verify_token", "validate_user_access"],
            "classes": ["AuthenticationService", "OAuthClient", "SecurityPolicy", "SessionStore", "User"]
        }
        (milestone_dir / "milestone.json").write_text(json.dumps(milestone_data))
        
        return temp_dir
    
    def validate_token_limits(self, project_root: Path) -> bool:
        """
        Validate that all context modes respect token limits.
        
        Args:
            project_root: Root directory of test project
            
        Returns:
            True if all validations pass
        """
        milestone_dir = project_root / "output" / "dev" / "auth_milestone"
        test_scenarios = self.create_test_scenarios()
        
        all_passed = True
        mode_tokens = {"MINIMAL": [], "BALANCED": [], "COMPREHENSIVE": []}
        
        print(f"🔍 Validating token limits across {len(test_scenarios)} scenarios...")
        
        for scenario_name, prompt, expected_mode in test_scenarios:
            # Test each scenario in its expected mode
            try:
                engine = SerenaContextEngine(project_root, context_mode=expected_mode)
                
                start_time = time.time()
                context, metadata = engine.build_context(milestone_dir, prompt)
                end_time = time.time()
                
                token_count = metadata["token_count"]
                processing_time = (end_time - start_time) * 1000  # ms
                
                # Record tokens for averaging
                mode_tokens[expected_mode].append(token_count)
                
                # Critical validation: Never exceed CI limit
                if token_count > self.MAX_TOKENS_CI_LIMIT:
                    self.results["violations"].append({
                        "scenario": scenario_name,
                        "prompt": prompt,
                        "mode": expected_mode,
                        "tokens": token_count,
                        "limit": self.MAX_TOKENS_CI_LIMIT,
                        "violation_type": "ci_limit_exceeded"
                    })
                    all_passed = False
                    print(f"❌ CRITICAL: {scenario_name} exceeded CI limit: {token_count} > {self.MAX_TOKENS_CI_LIMIT}")
                    continue
                
                # Mode-specific validations
                mode_limit = engine.max_tokens
                if token_count > mode_limit and mode_limit != float('inf'):
                    self.results["violations"].append({
                        "scenario": scenario_name,
                        "prompt": prompt,
                        "mode": expected_mode,
                        "tokens": token_count,
                        "limit": mode_limit,
                        "violation_type": "mode_limit_exceeded"
                    })
                    all_passed = False
                    print(f"❌ {scenario_name} exceeded {expected_mode} limit: {token_count} > {mode_limit}")
                else:
                    self.results["tests_passed"] += 1
                    print(f"✅ {scenario_name}: {token_count} tokens ({expected_mode} mode, {processing_time:.1f}ms)")
                
                # Record performance metrics
                self.results["performance_metrics"][scenario_name] = {
                    "tokens": token_count,
                    "processing_time_ms": processing_time,
                    "mode": expected_mode,
                    "warnings": len(metadata.get("warnings", [])),
                    "symbols_skipped": metadata.get("symbols_skipped", 0)
                }
                
            except Exception as e:
                self.results["tests_failed"] += 1
                self.results["violations"].append({
                    "scenario": scenario_name,
                    "prompt": prompt,
                    "mode": expected_mode,
                    "error": str(e),
                    "violation_type": "execution_error"
                })
                all_passed = False
                print(f"❌ {scenario_name} failed with error: {e}")
        
        # Calculate mode averages
        for mode, tokens in mode_tokens.items():
            if tokens:
                avg_tokens = sum(tokens) / len(tokens)
                self.results["mode_averages"][mode] = {
                    "average": avg_tokens,
                    "min": min(tokens),
                    "max": max(tokens),
                    "count": len(tokens)
                }
                print(f"📊 {mode} mode average: {avg_tokens:.1f} tokens (min: {min(tokens)}, max: {max(tokens)})")
        
        return all_passed
    
    def validate_balanced_mode_target(self) -> bool:
        """Validate that BALANCED mode averages in target range."""
        balanced_stats = self.results["mode_averages"].get("BALANCED")
        if not balanced_stats:
            print("⚠️ No BALANCED mode scenarios tested")
            return False
        
        avg_tokens = balanced_stats["average"]
        
        if self.BALANCED_TARGET_MIN <= avg_tokens <= self.BALANCED_TARGET_MAX:
            print(f"🎯 BALANCED mode target achieved: {avg_tokens:.1f} tokens (target: {self.BALANCED_TARGET_MIN}-{self.BALANCED_TARGET_MAX})")
            return True
        else:
            print(f"❌ BALANCED mode outside target range: {avg_tokens:.1f} tokens (target: {self.BALANCED_TARGET_MIN}-{self.BALANCED_TARGET_MAX})")
            return False
    
    def run_validation(self) -> Dict[str, Any]:
        """Run complete CI token validation."""
        print("🚀 Starting CI Token Validation")
        print("=" * 60)
        
        # Create test project
        print("📁 Creating test project...")
        project_root = self.create_sample_project()
        
        try:
            # Validate token limits
            print("\n🔒 Validating Token Limits...")
            limits_valid = self.validate_token_limits(project_root)
            
            # Validate BALANCED mode target
            print("\n🎯 Validating BALANCED Mode Target...")
            balanced_valid = self.validate_balanced_mode_target()
            
            # Generate summary
            self.print_summary()
            
            # Determine overall result
            overall_success = limits_valid and balanced_valid and len(self.results["violations"]) == 0
            
            return {
                "success": overall_success,
                "limits_valid": limits_valid,
                "balanced_target_met": balanced_valid,
                "results": self.results
            }
            
        finally:
            # Cleanup
            import shutil
            shutil.rmtree(project_root, ignore_errors=True)
    
    def print_summary(self):
        """Print validation summary."""
        print("\n" + "=" * 60)
        print("📋 CI TOKEN VALIDATION SUMMARY")
        print("=" * 60)
        
        # Test results
        total_tests = self.results["tests_passed"] + self.results["tests_failed"]
        pass_rate = (self.results["tests_passed"] / total_tests * 100) if total_tests > 0 else 0
        
        print(f"Tests: {self.results['tests_passed']}/{total_tests} passed ({pass_rate:.1f}%)")
        
        # Critical violations
        critical_violations = [
            v for v in self.results["violations"] 
            if v.get("violation_type") == "ci_limit_exceeded"
        ]
        
        if critical_violations:
            print(f"❌ CRITICAL: {len(critical_violations)} scenarios exceeded {self.MAX_TOKENS_CI_LIMIT} token CI limit")
            for violation in critical_violations:
                print(f"   - {violation['scenario']}: {violation['tokens']} tokens")
        else:
            print(f"✅ All scenarios within {self.MAX_TOKENS_CI_LIMIT} token CI limit")
        
        # Mode averages
        print(f"\n📊 Mode Performance:")
        for mode, stats in self.results["mode_averages"].items():
            print(f"  {mode}: {stats['average']:.1f} avg tokens (range: {stats['min']}-{stats['max']})")
        
        # BALANCED mode target
        balanced_stats = self.results["mode_averages"].get("BALANCED")
        if balanced_stats:
            avg = balanced_stats["average"]
            if self.BALANCED_TARGET_MIN <= avg <= self.BALANCED_TARGET_MAX:
                print(f"🎯 BALANCED mode target achieved: {avg:.1f} tokens")
            else:
                print(f"❌ BALANCED mode target missed: {avg:.1f} tokens (target: {self.BALANCED_TARGET_MIN}-{self.BALANCED_TARGET_MAX})")
        
        # Performance metrics
        avg_processing_time = sum(
            metrics["processing_time_ms"] 
            for metrics in self.results["performance_metrics"].values()
        ) / len(self.results["performance_metrics"]) if self.results["performance_metrics"] else 0
        
        print(f"\n⚡ Performance: {avg_processing_time:.1f}ms average processing time")
        
        # Warnings and truncations
        total_warnings = sum(
            metrics["warnings"] 
            for metrics in self.results["performance_metrics"].values()
        )
        total_skipped = sum(
            metrics["symbols_skipped"] 
            for metrics in self.results["performance_metrics"].values()
        )
        
        if total_warnings > 0 or total_skipped > 0:
            print(f"⚠️ Budget Management: {total_warnings} warnings, {total_skipped} symbols skipped")
        
        print("\n" + "=" * 60)


def main():
    """Main CI validation entry point."""
    validator = CITokenValidator()
    result = validator.run_validation()
    
    # Save results for CI artifacts
    results_file = Path("ci_token_validation_results.json")
    with open(results_file, 'w') as f:
        # Convert any non-serializable objects to strings
        serializable_results = json.loads(json.dumps(result, default=str))
        json.dump(serializable_results, f, indent=2)
    
    print(f"📄 Results saved to: {results_file}")
    
    # Exit with appropriate code
    if result["success"]:
        print("🎉 CI Token Validation PASSED")
        sys.exit(0)
    else:
        print("💥 CI Token Validation FAILED")
        
        # Print specific failure reasons
        if not result["limits_valid"]:
            print("❌ Token limits exceeded")
        if not result["balanced_target_met"]:
            print("❌ BALANCED mode target not achieved")
        
        sys.exit(1)


if __name__ == "__main__":
    main()