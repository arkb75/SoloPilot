#!/usr/bin/env python3
"""
Serena LSP Performance Benchmark Suite

Validates that Serena LSP integration solves Claude 4 timeout issues and 
achieves the target 30-50% token reduction compared to chunk-based context.
"""

import json
import os
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

from src.agents.dev.context_engine import LegacyContextEngine
from src.agents.dev.context_engine.serena_engine import SerenaContextEngine


class SerenaPerformanceBenchmark(unittest.TestCase):
    """Performance benchmarks for Serena LSP context engine."""

    @classmethod
    def setUpClass(cls):
        """Set up benchmark test environment."""
        cls.temp_dir = Path(tempfile.mkdtemp())
        cls.results = {"timestamp": time.time(), "tests": [], "summary": {}}

        # Create a complex project structure for testing
        cls._create_complex_project()
        cls._create_milestone_scenarios()

    @classmethod
    def tearDownClass(cls):
        """Clean up and save benchmark results."""
        import shutil

        # Calculate summary statistics
        cls._calculate_summary()

        # Save results
        results_file = Path("tests/performance/serena_benchmark_results.json")
        results_file.parent.mkdir(parents=True, exist_ok=True)

        with open(results_file, "w") as f:
            json.dump(cls.results, f, indent=2)

        print(f"\n📊 Benchmark results saved to {results_file}")
        cls._print_summary()

        # Cleanup
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    @classmethod
    def _create_complex_project(cls):
        """Create a complex project structure to test performance."""
        # Create multiple Python files with various complexity levels

        # Large controller file
        controller_content = '''
class UserController:
    def __init__(self):
        self.auth_service = AuthService()
        self.user_service = UserService()
        
    def authenticate(self, username: str, password: str) -> bool:
        """Authenticate user with username and password."""
        return self.auth_service.validate_credentials(username, password)
    
    def create_user(self, user_data: dict) -> User:
        """Create a new user account."""
        user = User(**user_data)
        return self.user_service.save(user)
    
    def update_user(self, user_id: int, updates: dict) -> User:
        """Update existing user account."""
        user = self.user_service.get_by_id(user_id)
        if user:
            for key, value in updates.items():
                setattr(user, key, value)
            return self.user_service.save(user)
        return None
    
    def delete_user(self, user_id: int) -> bool:
        """Delete user account."""
        return self.user_service.delete(user_id)
    
    def list_users(self, page: int = 1, limit: int = 20) -> List[User]:
        """List users with pagination."""
        return self.user_service.list_paginated(page, limit)
    
    def search_users(self, query: str) -> List[User]:
        """Search users by query."""
        return self.user_service.search(query)

class AuthService:
    def validate_credentials(self, username: str, password: str) -> bool:
        # Complex authentication logic here
        if not username or not password:
            return False
        # ... more logic
        return True

class UserService:
    def get_by_id(self, user_id: int) -> User:
        # Database lookup logic
        pass
    
    def save(self, user: "User") -> "User":
        # Database save logic
        pass
    
    def delete(self, user_id: int) -> bool:
        # Database delete logic
        pass
    
    def list_paginated(self, page: int, limit: int) -> List["User"]:
        # Paginated query logic
        pass
    
    def search(self, query: str) -> List["User"]:
        # Search logic
        pass
'''

        # Models file
        models_content = """
from typing import Optional
from datetime import datetime

class User:
    def __init__(self, username: str, email: str, password: str):
        self.id: Optional[int] = None
        self.username = username
        self.email = email
        self.password_hash = self._hash_password(password)
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.is_active = True
    
    def _hash_password(self, password: str) -> str:
        # Password hashing logic
        return f"hashed_{password}"
    
    def verify_password(self, password: str) -> bool:
        return self._hash_password(password) == self.password_hash
    
    def update_password(self, new_password: str) -> None:
        self.password_hash = self._hash_password(new_password)
        self.updated_at = datetime.now()

class Token:
    def __init__(self, user_id: int, token_type: str = "access"):
        self.user_id = user_id
        self.token_type = token_type
        self.value = self._generate_token()
        self.expires_at = self._calculate_expiry()
        self.created_at = datetime.now()
    
    def _generate_token(self) -> str:
        # Token generation logic
        import secrets
        return secrets.token_urlsafe(32)
    
    def _calculate_expiry(self) -> datetime:
        # Calculate token expiry
        from datetime import timedelta
        return datetime.now() + timedelta(hours=24)
    
    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at
"""

        # API routes file
        api_content = """
from flask import Flask, request, jsonify
from controllers import UserController

app = Flask(__name__)
user_controller = UserController()

@app.route('/api/users', methods=['GET'])
def list_users():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    users = user_controller.list_users(page, limit)
    return jsonify([user.__dict__ for user in users])

@app.route('/api/users', methods=['POST'])
def create_user():
    data = request.get_json()
    user = user_controller.create_user(data)
    return jsonify(user.__dict__), 201

@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    data = request.get_json()
    user = user_controller.update_user(user_id, data)
    if user:
        return jsonify(user.__dict__)
    return jsonify({'error': 'User not found'}), 404

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    success = user_controller.delete_user(user_id)
    if success:
        return '', 204
    return jsonify({'error': 'User not found'}), 404

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if user_controller.authenticate(username, password):
        # Generate token logic here
        return jsonify({'token': 'generated_token'})
    
    return jsonify({'error': 'Invalid credentials'}), 401
"""

        # Write files to temp directory
        (cls.temp_dir / "controllers.py").write_text(controller_content)
        (cls.temp_dir / "models.py").write_text(models_content)
        (cls.temp_dir / "api.py").write_text(api_content)

        # Create additional complexity
        for i in range(5):
            utils_content = f'''
def utility_function_{i}():
    """Utility function {i} for testing."""
    return "result_{i}"

class UtilityClass{i}:
    def method_{i}(self):
        return utility_function_{i}()
'''
            (cls.temp_dir / f"utils_{i}.py").write_text(utils_content)

    @classmethod
    def _create_milestone_scenarios(cls):
        """Create milestone scenarios for testing."""
        cls.milestones = []

        # Milestone 1: Simple authentication
        milestone1 = cls.temp_dir / "milestone_auth"
        milestone1.mkdir()

        milestone1_data = {
            "name": "Authentication System",
            "components": ["UserController", "AuthService"],
            "functions": ["authenticate", "validate_credentials"],
            "classes": ["User"],
        }

        with open(milestone1 / "milestone.json", "w") as f:
            json.dump(milestone1_data, f)

        cls.milestones.append((milestone1, "Implement user authentication"))

        # Milestone 2: Complex CRUD operations
        milestone2 = cls.temp_dir / "milestone_crud"
        milestone2.mkdir()

        milestone2_data = {
            "name": "User CRUD Operations",
            "components": ["UserController", "UserService"],
            "functions": ["create_user", "update_user", "delete_user", "list_users"],
            "classes": ["User", "Token"],
        }

        with open(milestone2 / "milestone.json", "w") as f:
            json.dump(milestone2_data, f)

        cls.milestones.append((milestone2, "Implement full CRUD operations for users"))

        # Milestone 3: API endpoints
        milestone3 = cls.temp_dir / "milestone_api"
        milestone3.mkdir()

        milestone3_data = {
            "name": "REST API Endpoints",
            "components": ["Flask", "UserController"],
            "functions": ["list_users", "create_user", "update_user", "delete_user", "login"],
            "classes": ["User"],
        }

        with open(milestone3 / "milestone.json", "w") as f:
            json.dump(milestone3_data, f)

        cls.milestones.append((milestone3, "Create REST API endpoints for user management"))

    def test_token_reduction_comparison(self):
        """Test token reduction: Serena vs Legacy context engines."""
        print("\n🔍 Testing token reduction: Serena vs Legacy")

        for milestone_path, prompt in self.milestones:
            print(f"  📁 Testing milestone: {milestone_path.name}")

            # Test with Legacy engine
            legacy_start = time.time()
            legacy_engine = LegacyContextEngine()
            legacy_context, legacy_meta = legacy_engine.build_context(milestone_path, prompt)
            legacy_time = (time.time() - legacy_start) * 1000

            # Test with Serena engine (mock available)
            serena_start = time.time()
            with unittest.mock.patch(
                "src.agents.dev.context_engine.serena_engine.subprocess.run"
            ) as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "available"

                serena_engine = SerenaContextEngine(project_root=self.temp_dir)
                serena_context, serena_meta = serena_engine.build_context(milestone_path, prompt)
            serena_time = (time.time() - serena_start) * 1000

            # Calculate metrics
            legacy_tokens = len(legacy_context) // 4  # Simple token estimation
            serena_tokens = serena_meta.get("tokens_estimated", len(serena_context) // 4)
            token_reduction = max(0, legacy_tokens - serena_tokens)
            reduction_percentage = (
                (token_reduction / legacy_tokens * 100) if legacy_tokens > 0 else 0
            )

            result = {
                "milestone": milestone_path.name,
                "prompt": prompt,
                "legacy_tokens": legacy_tokens,
                "serena_tokens": serena_tokens,
                "token_reduction": token_reduction,
                "reduction_percentage": reduction_percentage,
                "legacy_time_ms": legacy_time,
                "serena_time_ms": serena_time,
                "symbols_found": serena_meta.get("symbols_found", 0),
                "context_length_legacy": len(legacy_context),
                "context_length_serena": len(serena_context),
            }

            self.results["tests"].append(result)

            print(f"    📊 Legacy tokens: {legacy_tokens}")
            print(f"    🔍 Serena tokens: {serena_tokens}")
            print(f"    💰 Reduction: {reduction_percentage:.1f}%")

            # Assert that we achieve some token reduction
            self.assertGreater(
                reduction_percentage, 0, f"Expected token reduction for {milestone_path.name}"
            )

    def test_response_time_performance(self):
        """Test response time performance under load."""
        print("\n⏱️ Testing response time performance")

        milestone_path, prompt = self.milestones[1]  # Use complex CRUD milestone

        # Test multiple queries to measure average performance
        legacy_times = []
        serena_times = []

        for i in range(3):  # Run 3 iterations
            # Legacy engine
            start = time.time()
            legacy_engine = LegacyContextEngine()
            legacy_engine.build_context(milestone_path, prompt)
            legacy_times.append((time.time() - start) * 1000)

            # Serena engine
            start = time.time()
            with unittest.mock.patch(
                "src.agents.dev.context_engine.serena_engine.subprocess.run"
            ) as mock_run:
                mock_run.return_value.returncode = 0
                mock_run.return_value.stdout = "available"

                serena_engine = SerenaContextEngine(project_root=self.temp_dir)
                serena_engine.build_context(milestone_path, prompt)
            serena_times.append((time.time() - start) * 1000)

        avg_legacy_time = sum(legacy_times) / len(legacy_times)
        avg_serena_time = sum(serena_times) / len(serena_times)

        print(f"    📊 Average Legacy time: {avg_legacy_time:.1f}ms")
        print(f"    🔍 Average Serena time: {avg_serena_time:.1f}ms")

        # Both should complete within reasonable time (no timeouts)
        self.assertLess(avg_legacy_time, 10000, "Legacy engine should complete within 10s")
        self.assertLess(avg_serena_time, 10000, "Serena engine should complete within 10s")

        self.results["tests"].append(
            {
                "test": "response_time_performance",
                "avg_legacy_time_ms": avg_legacy_time,
                "avg_serena_time_ms": avg_serena_time,
                "iterations": len(legacy_times),
            }
        )

    def test_symbol_awareness_accuracy(self):
        """Test accuracy of symbol-aware context building."""
        print("\n🎯 Testing symbol awareness accuracy")

        milestone_path, prompt = self.milestones[0]  # Use authentication milestone

        with unittest.mock.patch(
            "src.agents.dev.context_engine.serena_engine.subprocess.run"
        ) as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "available"

            serena_engine = SerenaContextEngine(project_root=self.temp_dir)

            # Test symbol finding
            user_controller = serena_engine.find_symbol("UserController")
            auth_service = serena_engine.find_symbol("AuthService")
            authenticate_func = serena_engine.find_symbol("authenticate")

            # Verify symbols are found
            self.assertIsNotNone(user_controller, "Should find UserController class")
            self.assertIsNotNone(auth_service, "Should find AuthService class")
            self.assertIsNotNone(authenticate_func, "Should find authenticate function")

            if user_controller:
                self.assertEqual(user_controller["type"], "class")
                self.assertIn("UserController", user_controller["definition"])

            if authenticate_func:
                self.assertEqual(authenticate_func["type"], "function")
                self.assertIn("authenticate", authenticate_func["definition"])

            # Test reference finding
            auth_refs = serena_engine.find_referencing_symbols("AuthService")
            self.assertGreater(len(auth_refs), 0, "Should find references to AuthService")

            print(f"    ✅ Found UserController: {user_controller is not None}")
            print(f"    ✅ Found AuthService: {auth_service is not None}")
            print(f"    ✅ Found authenticate: {authenticate_func is not None}")
            print(f"    📄 AuthService references: {len(auth_refs)}")

        self.results["tests"].append(
            {
                "test": "symbol_awareness_accuracy",
                "symbols_found": {
                    "UserController": user_controller is not None,
                    "AuthService": auth_service is not None,
                    "authenticate": authenticate_func is not None,
                },
                "references_found": len(auth_refs),
            }
        )

    def test_complex_project_handling(self):
        """Test handling of complex projects that cause timeouts."""
        print("\n🏗️ Testing complex project handling")

        # Create an even more complex scenario
        large_milestone = self.temp_dir / "milestone_complex"
        large_milestone.mkdir()

        complex_data = {
            "name": "Complex System Integration",
            "components": [f"Component{i}" for i in range(20)],
            "functions": [f"function_{i}" for i in range(50)],
            "classes": [f"Class{i}" for i in range(30)],
        }

        with open(large_milestone / "milestone.json", "w") as f:
            json.dump(complex_data, f)

        complex_prompt = """
        Implement a complex microservices architecture with:
        - User authentication and authorization
        - Data processing pipelines
        - Real-time notifications
        - Caching layer
        - Database migrations
        - API gateway integration
        - Monitoring and logging
        - Error handling and recovery
        """

        # Test that both engines can handle this without timeout
        legacy_start = time.time()
        legacy_engine = LegacyContextEngine()
        legacy_context, _ = legacy_engine.build_context(large_milestone, complex_prompt)
        legacy_time = (time.time() - legacy_start) * 1000

        serena_start = time.time()
        with unittest.mock.patch(
            "src.agents.dev.context_engine.serena_engine.subprocess.run"
        ) as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "available"

            serena_engine = SerenaContextEngine(project_root=self.temp_dir)
            serena_context, serena_meta = serena_engine.build_context(
                large_milestone, complex_prompt
            )
        serena_time = (time.time() - serena_start) * 1000

        print(f"    ⏱️ Legacy time: {legacy_time:.1f}ms")
        print(f"    ⏱️ Serena time: {serena_time:.1f}ms")
        print(f"    📊 Legacy context length: {len(legacy_context)}")
        print(f"    📊 Serena context length: {len(serena_context)}")

        # Both should complete without timeout (< 30 seconds)
        self.assertLess(legacy_time, 30000, "Legacy should handle complex project within 30s")
        self.assertLess(serena_time, 30000, "Serena should handle complex project within 30s")

        # Serena should be more efficient
        token_reduction = len(legacy_context) - len(serena_context)
        efficiency_gain = (
            (token_reduction / len(legacy_context) * 100) if len(legacy_context) > 0 else 0
        )

        self.results["tests"].append(
            {
                "test": "complex_project_handling",
                "legacy_time_ms": legacy_time,
                "serena_time_ms": serena_time,
                "legacy_context_length": len(legacy_context),
                "serena_context_length": len(serena_context),
                "efficiency_gain_percentage": efficiency_gain,
            }
        )

    @classmethod
    def _calculate_summary(cls):
        """Calculate summary statistics from all tests."""
        token_tests = [t for t in cls.results["tests"] if "reduction_percentage" in t]

        if token_tests:
            avg_reduction = sum(t["reduction_percentage"] for t in token_tests) / len(token_tests)
            max_reduction = max(t["reduction_percentage"] for t in token_tests)
            min_reduction = min(t["reduction_percentage"] for t in token_tests)

            cls.results["summary"]["token_reduction"] = {
                "average_percentage": avg_reduction,
                "max_percentage": max_reduction,
                "min_percentage": min_reduction,
                "target_achieved": avg_reduction >= 30.0,  # Target: 30-50% reduction
            }

        # Performance summary
        time_tests = [
            t for t in cls.results["tests"] if "legacy_time_ms" in t and "serena_time_ms" in t
        ]
        if time_tests:
            avg_legacy_time = sum(t["legacy_time_ms"] for t in time_tests) / len(time_tests)
            avg_serena_time = sum(t["serena_time_ms"] for t in time_tests) / len(time_tests)

            cls.results["summary"]["performance"] = {
                "avg_legacy_time_ms": avg_legacy_time,
                "avg_serena_time_ms": avg_serena_time,
                "no_timeouts": all(
                    t["legacy_time_ms"] < 30000 and t["serena_time_ms"] < 30000 for t in time_tests
                ),
            }

    @classmethod
    def _print_summary(cls):
        """Print benchmark summary to console."""
        print("\n" + "=" * 60)
        print("🎯 SERENA LSP BENCHMARK SUMMARY")
        print("=" * 60)

        summary = cls.results["summary"]

        if "token_reduction" in summary:
            tr = summary["token_reduction"]
            status = "✅ ACHIEVED" if tr["target_achieved"] else "❌ NOT ACHIEVED"
            print(f"💰 Token Reduction (Target: 30-50%): {status}")
            print(f"   Average: {tr['average_percentage']:.1f}%")
            print(f"   Range: {tr['min_percentage']:.1f}% - {tr['max_percentage']:.1f}%")

        if "performance" in summary:
            perf = summary["performance"]
            timeout_status = "✅ NO TIMEOUTS" if perf["no_timeouts"] else "❌ TIMEOUTS DETECTED"
            print(f"⏱️ Performance: {timeout_status}")
            print(f"   Average Legacy: {perf['avg_legacy_time_ms']:.1f}ms")
            print(f"   Average Serena: {perf['avg_serena_time_ms']:.1f}ms")

        print("\n🎉 Benchmark completed! Check results file for detailed metrics.")


if __name__ == "__main__":
    # Set environment to use Serena for testing
    os.environ["CONTEXT_ENGINE"] = "serena"

    # Run benchmarks
    unittest.main(verbosity=2)
