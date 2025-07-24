"""Integration tests for Vercel deployment."""

import os
import time

import pytest
import requests
from bs4 import BeautifulSoup


class TestDeployment:
    """Test suite for validating Vercel deployment."""

    @pytest.fixture
    def deployment_url(self):
        """Get deployment URL from environment."""
        url = os.environ.get("DEPLOYMENT_URL", "https://solopilot.ai")
        return url.rstrip("/")

    def test_site_accessibility(self, deployment_url):
        """Test that the site is accessible."""
        response = requests.get(deployment_url, timeout=30)
        assert response.status_code == 200, f"Site returned {response.status_code}"
        assert len(response.content) > 1000, "Response body too small"

    def test_ssl_certificate(self, deployment_url):
        """Test SSL certificate validity."""
        if not deployment_url.startswith("https://"):
            pytest.skip("Not an HTTPS URL")

        # This will raise an SSLError if certificate is invalid
        response = requests.get(deployment_url, verify=True, timeout=30)
        assert response.status_code == 200

    def test_security_headers(self, deployment_url):
        """Test that security headers are present."""
        response = requests.get(deployment_url, timeout=30)
        headers = response.headers

        # Required security headers
        required_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": ["DENY", "SAMEORIGIN"],
            "X-XSS-Protection": "1; mode=block",
        }

        for header, expected_values in required_headers.items():
            assert header in headers, f"Missing security header: {header}"

            if isinstance(expected_values, list):
                assert any(
                    headers[header] == value for value in expected_values
                ), f"Invalid {header} value: {headers[header]}"
            else:
                assert (
                    headers[header] == expected_values
                ), f"Invalid {header} value: {headers[header]}"

        # HSTS should be present for HTTPS
        if deployment_url.startswith("https://"):
            assert "Strict-Transport-Security" in headers, "Missing HSTS header"

    def test_page_performance(self, deployment_url):
        """Test basic page performance metrics."""
        start_time = time.time()
        response = requests.get(deployment_url, timeout=30)
        load_time = time.time() - start_time

        assert response.status_code == 200
        assert load_time < 5.0, f"Page load took {load_time:.2f}s (> 5s threshold)"

        # Check response size is reasonable
        content_length = len(response.content)
        assert content_length < 5_000_000, f"Page size {content_length} bytes is too large"

    def test_api_health_endpoint(self, deployment_url):
        """Test API health endpoint if it exists."""
        health_url = f"{deployment_url}/api/health"

        try:
            response = requests.get(health_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                assert data.get("status") in ["ok", "healthy"], "API not healthy"
            elif response.status_code == 404:
                pytest.skip("API health endpoint not implemented")
            else:
                pytest.fail(f"API health returned {response.status_code}")
        except requests.exceptions.RequestException:
            pytest.skip("API health endpoint not available")

    def test_static_assets(self, deployment_url):
        """Test that static assets are served correctly."""
        response = requests.get(deployment_url, timeout=30)
        soup = BeautifulSoup(response.content, "html.parser")

        # Check CSS files
        css_links = soup.find_all("link", rel="stylesheet")
        for link in css_links[:3]:  # Check first 3 CSS files
            css_url = link.get("href")
            if css_url and not css_url.startswith("data:"):
                if not css_url.startswith("http"):
                    css_url = f"{deployment_url}{css_url}"
                css_response = requests.head(css_url, timeout=10)
                assert css_response.status_code == 200, f"CSS not found: {css_url}"

        # Check JS files
        js_scripts = soup.find_all("script", src=True)
        for script in js_scripts[:3]:  # Check first 3 JS files
            js_url = script.get("src")
            if js_url and not js_url.startswith("data:"):
                if not js_url.startswith("http"):
                    js_url = f"{deployment_url}{js_url}"
                js_response = requests.head(js_url, timeout=10)
                assert js_response.status_code == 200, f"JS not found: {js_url}"

    def test_cors_headers(self, deployment_url):
        """Test CORS configuration for API endpoints."""
        api_url = f"{deployment_url}/api/health"

        # Test preflight request
        response = requests.options(
            api_url,
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
            },
            timeout=10,
        )

        if response.status_code == 204:
            # CORS is configured
            cors_headers = response.headers
            assert (
                "Access-Control-Allow-Origin" in cors_headers
                or "access-control-allow-origin" in cors_headers
            )
        elif response.status_code == 404:
            pytest.skip("API endpoint not found")

    def test_robots_txt(self, deployment_url):
        """Test robots.txt is accessible."""
        robots_url = f"{deployment_url}/robots.txt"
        response = requests.get(robots_url, timeout=10)

        if response.status_code == 200:
            content = response.text.lower()
            assert "user-agent" in content or "sitemap" in content
        else:
            pytest.skip("robots.txt not configured")

    def test_error_pages(self, deployment_url):
        """Test error page handling."""
        # Test 404 page
        not_found_url = f"{deployment_url}/this-page-definitely-does-not-exist-404"
        response = requests.get(not_found_url, timeout=10)

        assert response.status_code == 404, "Should return 404 for non-existent page"

        # Should return proper HTML error page, not raw error
        assert "html" in response.headers.get("Content-Type", "").lower()
        assert len(response.content) > 500, "404 page should have content"

    @pytest.mark.parametrize(
        "path",
        [
            "/",
            "/api",
            "/docs",
            "/about",
        ],
    )
    def test_common_routes(self, deployment_url, path):
        """Test common routes are accessible."""
        url = f"{deployment_url}{path}"
        response = requests.get(url, timeout=10, allow_redirects=True)

        # Allow 200, 301, 302, or 404 (not configured)
        assert response.status_code in [
            200,
            404,
        ], f"Route {path} returned unexpected status: {response.status_code}"

    def test_compression(self, deployment_url):
        """Test that responses are compressed."""
        response = requests.get(
            deployment_url,
            headers={"Accept-Encoding": "gzip, deflate"},
            timeout=30,
        )

        encoding = response.headers.get("Content-Encoding", "").lower()
        # Vercel should compress responses
        if len(response.content) > 1000:  # Only check for larger responses
            assert encoding in ["gzip", "br", "deflate"], "Response not compressed"

    def test_caching_headers(self, deployment_url):
        """Test that appropriate caching headers are set."""
        # Test static asset caching
        response = requests.get(deployment_url, timeout=30)
        soup = BeautifulSoup(response.content, "html.parser")

        # Find a static asset
        static_asset = None
        for link in soup.find_all("link", rel="stylesheet"):
            href = link.get("href", "")
            if "/_next/static/" in href:
                static_asset = href
                break

        if static_asset:
            if not static_asset.startswith("http"):
                static_asset = f"{deployment_url}{static_asset}"

            asset_response = requests.head(static_asset, timeout=10)
            cache_control = asset_response.headers.get("Cache-Control", "")

            # Static assets should have long cache
            assert "max-age" in cache_control, "Static assets should have cache headers"
            assert "immutable" in cache_control or "public" in cache_control

    def test_deployment_metadata(self, deployment_url):
        """Test deployment metadata in HTML."""
        response = requests.get(deployment_url, timeout=30)
        soup = BeautifulSoup(response.content, "html.parser")

        # Check for basic metadata
        assert soup.find("title") is not None, "Page should have a title"
        assert (
            soup.find("meta", {"name": "description"}) is not None
        ), "Page should have meta description"

        # Check for viewport meta for mobile
        viewport = soup.find("meta", {"name": "viewport"})
        assert viewport is not None, "Page should have viewport meta tag"
