#!/usr/bin/env python3
"""Quick smoke test for deployment validation."""

import sys
import time

import click
import requests


@click.command()
@click.option(
    "--url",
    default="https://solopilot.ai",
    help="Deployment URL to test",
)
@click.option(
    "--timeout",
    default=30,
    help="Request timeout in seconds",
)
def smoke_test(url: str, timeout: int) -> None:
    """Run basic smoke tests against deployment."""
    click.echo(f"🔍 Running smoke tests for: {url}")

    tests_passed = 0
    tests_failed = 0

    # Test 1: Basic accessibility
    click.echo("\n1. Testing site accessibility...")
    try:
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200:
            click.echo("   ✅ Site is accessible")
            tests_passed += 1
        else:
            click.echo(f"   ❌ Site returned status: {response.status_code}")
            tests_failed += 1
    except Exception as e:
        click.echo(f"   ❌ Failed to access site: {e}")
        tests_failed += 1

    # Test 2: SSL Certificate
    if url.startswith("https://"):
        click.echo("\n2. Testing SSL certificate...")
        try:
            response = requests.get(url, verify=True, timeout=timeout)
            click.echo("   ✅ SSL certificate is valid")
            tests_passed += 1
        except requests.exceptions.SSLError:
            click.echo("   ❌ SSL certificate validation failed")
            tests_failed += 1

    # Test 3: Response time
    click.echo("\n3. Testing response time...")
    try:
        start_time = time.time()
        response = requests.get(url, timeout=timeout)
        load_time = time.time() - start_time

        if load_time < 3.0:
            click.echo(f"   ✅ Response time: {load_time:.2f}s")
            tests_passed += 1
        else:
            click.echo(f"   ⚠️  Slow response time: {load_time:.2f}s")
            tests_failed += 1
    except Exception as e:
        click.echo(f"   ❌ Failed to measure response time: {e}")
        tests_failed += 1

    # Test 4: Security headers
    click.echo("\n4. Testing security headers...")
    try:
        response = requests.get(url, timeout=timeout)
        headers = response.headers

        security_headers = [
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
        ]

        missing_headers = []
        for header in security_headers:
            if header not in headers:
                missing_headers.append(header)

        if not missing_headers:
            click.echo("   ✅ All security headers present")
            tests_passed += 1
        else:
            click.echo(f"   ⚠️  Missing headers: {', '.join(missing_headers)}")
            tests_failed += 1
    except Exception as e:
        click.echo(f"   ❌ Failed to check headers: {e}")
        tests_failed += 1

    # Test 5: API health check
    click.echo("\n5. Testing API health endpoint...")
    api_url = f"{url.rstrip('/')}/api/health"
    try:
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            click.echo("   ✅ API health check passed")
            tests_passed += 1
        elif response.status_code == 404:
            click.echo("   ℹ️  API health endpoint not configured")
        else:
            click.echo(f"   ⚠️  API returned status: {response.status_code}")
            tests_failed += 1
    except Exception:
        click.echo("   ℹ️  API health endpoint not available")

    # Summary
    click.echo("\n" + "=" * 50)
    click.echo(f"✅ Tests passed: {tests_passed}")
    click.echo(f"❌ Tests failed: {tests_failed}")

    if tests_failed == 0:
        click.echo("\n🎉 All smoke tests passed!")
        sys.exit(0)
    else:
        click.echo("\n⚠️  Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    smoke_test()
