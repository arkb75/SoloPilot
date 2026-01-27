"""
Wireframe Generator for Design Phase

Generates responsive HTML/CSS wireframes from project requirements using Claude.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Check environment for AI provider
try:
    from src.providers import get_provider
    USE_AI_PROVIDER = True
except ImportError:
    import boto3
    USE_AI_PROVIDER = False

AI_PROVIDER = os.environ.get("AI_PROVIDER", "bedrock")


class WireframeGenerator:
    """Generates HTML/CSS wireframes from requirements using Claude."""

    def __init__(self):
        """Initialize the wireframe generator."""
        if USE_AI_PROVIDER:
            self.provider = get_provider(AI_PROVIDER)
        else:
            self.bedrock_client = boto3.client(
                "bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-2")
            )
            self.inference_profile_arn = (
                os.environ.get("BEDROCK_IP_ARN")
                or os.environ.get("VISION_INFERENCE_PROFILE_ARN")
            )
            self.model_id = os.environ.get(
                "BEDROCK_MODEL_ID", "anthropic.claude-sonnet-4-5-20250929-v1:0"
            )

    def generate_wireframes(
        self, conversation: Dict[str, Any]
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Generate wireframes for all identified screens.

        Args:
            conversation: Full conversation with requirements

        Returns:
            Tuple of (list of screen dicts, error message if any)
        """
        requirements = conversation.get("requirements", {})
        if not requirements:
            return [], "No requirements found in conversation"

        # Extract screens from features
        screens = self._identify_screens(requirements)
        if not screens:
            return [], "Could not identify screens from requirements"

        # Generate wireframe for each screen
        generated_screens = []
        project_context = self._build_project_context(requirements)

        for screen in screens:
            try:
                html = self._generate_single_screen(
                    screen["name"],
                    screen["description"],
                    project_context
                )
                generated_screens.append({
                    "id": screen["id"],
                    "name": screen["name"],
                    "description": screen["description"],
                    "html": html,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                })
            except Exception as e:
                logger.error(f"Error generating screen {screen['name']}: {str(e)}")
                generated_screens.append({
                    "id": screen["id"],
                    "name": screen["name"],
                    "description": screen["description"],
                    "html": self._error_placeholder(screen["name"], str(e)),
                    "error": str(e),
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                })

        return generated_screens, None

    def _identify_screens(self, requirements: Dict[str, Any]) -> List[Dict[str, str]]:
        """Identify screens from requirements features."""
        screens = []
        features = requirements.get("features", [])
        project_type = requirements.get("project_type", "web app")

        # Default screens based on project type
        default_screens = self._get_default_screens(project_type)

        # Add screens from features
        for i, feature in enumerate(features):
            feature_name = feature.get("name", f"Feature {i+1}")
            feature_desc = feature.get("desc", feature.get("description", ""))
            
            # Convert feature to screen if it implies UI
            screen_keywords = ["page", "screen", "dashboard", "view", "form", "panel", "modal"]
            if any(kw in feature_name.lower() for kw in screen_keywords):
                screens.append({
                    "id": f"screen_{i}",
                    "name": feature_name,
                    "description": feature_desc,
                })

        # If no screens identified, use defaults
        if not screens:
            screens = default_screens

        # Always ensure we have at least a home/landing screen
        has_home = any("home" in s["name"].lower() or "landing" in s["name"].lower() for s in screens)
        if not has_home and screens:
            screens.insert(0, {
                "id": "screen_home",
                "name": "Home / Landing",
                "description": f"Main entry point for the {project_type}",
            })

        return screens[:2]  # Limit to 2 screens to stay within API Gateway timeout

    def _get_default_screens(self, project_type: str) -> List[Dict[str, str]]:
        """Get default screens based on project type."""
        project_type_lower = project_type.lower()

        if "mobile" in project_type_lower or "app" in project_type_lower:
            return [
                {"id": "screen_home", "name": "Home Screen", "description": "Main app dashboard"},
                {"id": "screen_login", "name": "Login", "description": "User authentication"},
                {"id": "screen_profile", "name": "Profile", "description": "User profile and settings"},
            ]
        elif "dashboard" in project_type_lower or "admin" in project_type_lower:
            return [
                {"id": "screen_dashboard", "name": "Dashboard", "description": "Main analytics dashboard"},
                {"id": "screen_list", "name": "Data List", "description": "List view with filtering"},
                {"id": "screen_detail", "name": "Detail View", "description": "Detailed item view"},
            ]
        elif "ecommerce" in project_type_lower or "shop" in project_type_lower:
            return [
                {"id": "screen_home", "name": "Homepage", "description": "Store landing page"},
                {"id": "screen_products", "name": "Product List", "description": "Product catalog"},
                {"id": "screen_cart", "name": "Cart", "description": "Shopping cart"},
                {"id": "screen_checkout", "name": "Checkout", "description": "Checkout flow"},
            ]
        else:
            # Generic web app
            return [
                {"id": "screen_home", "name": "Landing Page", "description": "Main landing page"},
                {"id": "screen_features", "name": "Features", "description": "Features overview"},
                {"id": "screen_contact", "name": "Contact", "description": "Contact form"},
            ]

    def _build_project_context(self, requirements: Dict[str, Any]) -> Dict[str, Any]:
        """Build context for wireframe generation."""
        return {
            "title": requirements.get("title", "Project"),
            "project_type": requirements.get("project_type", "web application"),
            "features": [f.get("name", "") for f in requirements.get("features", [])],
            "style": requirements.get("style", "modern, clean"),
        }

    def _generate_single_screen(
        self, screen_name: str, description: str, project_context: Dict[str, Any]
    ) -> str:
        """Generate HTML/CSS for a single screen."""
        prompt = self._build_wireframe_prompt(screen_name, description, project_context)
        response = self._call_llm(prompt)
        
        # Extract HTML from response (may be wrapped in code blocks)
        html = self._extract_html(response)
        return html

    def _build_wireframe_prompt(
        self, screen_name: str, description: str, project_context: Dict[str, Any]
    ) -> str:
        """Build the prompt for wireframe generation."""
        return f"""Generate a high-fidelity HTML wireframe for the following screen.

PROJECT CONTEXT:
- Project: {project_context.get('title', 'Project')}
- Type: {project_context.get('project_type', 'web app')}
- Key Features: {', '.join(project_context.get('features', [])[:5])}
- Style: {project_context.get('style', 'modern, clean')}

SCREEN TO DESIGN:
- Name: {screen_name}
- Description: {description}

REQUIREMENTS:
1. Generate a complete, self-contained HTML file with embedded CSS
2. Use Tailwind CSS via CDN for styling
3. Make it responsive (mobile-first)
4. Use modern design patterns (cards, shadows, rounded corners)
5. Include placeholder content that's realistic
6. Use a professional color scheme (blues, grays, clean whites)
7. Include Font Awesome icons via CDN where appropriate
8. Add subtle hover effects and transitions
9. Make it look like a real, polished application

OUTPUT FORMAT:
Return ONLY the complete HTML code, starting with <!DOCTYPE html>.
Do not include any explanation or markdown formatting.
The code should be immediately renderable in a browser.

Generate the wireframe now:"""

    def _extract_html(self, response: str) -> str:
        """Extract HTML from LLM response."""
        # Remove markdown code blocks if present
        response = response.strip()
        
        if response.startswith("```html"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]
        
        if response.endswith("```"):
            response = response[:-3]

        response = response.strip()

        # Ensure it starts with doctype
        if not response.lower().startswith("<!doctype"):
            # Try to find the doctype
            idx = response.lower().find("<!doctype")
            if idx != -1:
                response = response[idx:]

        return response

    def _error_placeholder(self, screen_name: str, error: str) -> str:
        """Generate placeholder HTML for failed generation."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{screen_name} - Generation Error</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen flex items-center justify-center">
    <div class="bg-white p-8 rounded-lg shadow-lg max-w-md text-center">
        <div class="text-red-500 text-5xl mb-4">⚠️</div>
        <h1 class="text-xl font-bold text-gray-800 mb-2">{screen_name}</h1>
        <p class="text-gray-600 mb-4">Failed to generate wireframe</p>
        <p class="text-sm text-gray-500">{error}</p>
        <button onclick="location.reload()" 
                class="mt-4 px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">
            Retry
        </button>
    </div>
</body>
</html>"""

    def regenerate_screen(
        self, screen: Dict[str, Any], feedback: str, project_context: Dict[str, Any]
    ) -> str:
        """Regenerate a screen with user feedback."""
        prompt = f"""Improve the following wireframe based on user feedback.

CURRENT WIREFRAME:
{screen.get('html', '')}

USER FEEDBACK:
{feedback}

PROJECT CONTEXT:
- Project: {project_context.get('title', 'Project')}
- Type: {project_context.get('project_type', 'web app')}

REQUIREMENTS:
1. Keep the same overall structure unless specifically asked to change it
2. Apply the user's feedback accurately
3. Maintain the same tech stack (Tailwind CSS, Font Awesome)
4. Return a complete, self-contained HTML file

OUTPUT FORMAT:
Return ONLY the complete HTML code, starting with <!DOCTYPE html>.
Do not include any explanation.

Generate the improved wireframe:"""

        response = self._call_llm(prompt)
        return self._extract_html(response)

    def generate_combined_preview(self, screens: List[Dict[str, Any]]) -> str:
        """Generate an index.html that links to all screens."""
        screen_links = "\n".join([
            f'<a href="screens/{s["id"]}.html" class="block p-4 bg-white rounded-lg shadow hover:shadow-md transition-shadow">'
            f'<h3 class="font-semibold text-gray-800">{s["name"]}</h3>'
            f'<p class="text-sm text-gray-500">{s.get("description", "")[:50]}...</p>'
            f'</a>'
            for s in screens
        ])

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wireframe Preview</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen p-8">
    <div class="max-w-4xl mx-auto">
        <h1 class="text-3xl font-bold text-gray-800 mb-2">Wireframe Preview</h1>
        <p class="text-gray-600 mb-8">Click a screen to view the full wireframe</p>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {screen_links}
        </div>
    </div>
</body>
</html>"""

    def _call_llm(self, prompt: str) -> str:
        """Call Claude to generate wireframe."""
        try:
            if USE_AI_PROVIDER:
                response = self.provider.generate_code(prompt, [])
                return response.strip()
            else:
                request_body = {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4000,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                }
                payload = json.dumps(request_body)

                if self.inference_profile_arn:
                    response = self.bedrock_client.invoke_model(
                        modelId=self.inference_profile_arn,
                        body=payload,
                        contentType="application/json",
                    )
                else:
                    response = self.bedrock_client.invoke_model(
                        modelId=self.model_id,
                        body=payload,
                        contentType="application/json",
                    )

                response_body = json.loads(response["body"].read())
                return response_body["content"][0]["text"].strip()

        except Exception as e:
            logger.error(f"Error calling LLM for wireframe: {str(e)}", exc_info=True)
            raise
