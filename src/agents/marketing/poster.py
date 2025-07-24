#!/usr/bin/env python3
"""
Marketing Poster Agent for SoloPilot

Generates tweet-length marketing announcements for milestone releases.
Simple implementation focusing on milestone information formatting.
"""

import json
import time
from pathlib import Path
from typing import Any, Dict, List


class MarketingPoster:
    """Simple marketing poster agent for milestone announcements."""

    def __init__(self):
        """Initialize the MarketingPoster."""
        self.max_length = 280  # Twitter character limit
        self.templates = self._load_templates()

    def _load_templates(self) -> Dict[str, str]:
        """Load announcement templates."""
        return {
            "milestone_release": "🚀 New milestone released: {title}! {summary} {hashtags}",
            "feature_update": "✨ Feature update: {features}! {hashtags}",
            "tech_stack": "⚙️ Built with {tech_stack}. {summary} {hashtags}",
            "simple": "🎉 {title} - {summary} {hashtags}",
            "progress": "📈 Progress update: {summary} Total features: {feature_count} {hashtags}",
        }

    def announce(self, milestone_dir: Path) -> Dict[str, Any]:
        """
        Generate marketing announcement for milestone.

        Args:
            milestone_dir: Path to milestone directory

        Returns:
            Dictionary with announcement content and metadata
        """
        if not milestone_dir.exists():
            return {
                "success": False,
                "error": f"Milestone directory not found: {milestone_dir}",
                "announcement": "",
                "metadata": {},
            }

        print(f"📢 Generating announcement for {milestone_dir}")

        # Extract milestone information
        milestone_info = self._extract_milestone_info(milestone_dir)

        # Generate announcement variants
        announcements = self._generate_announcements(milestone_info)

        # Select best announcement
        best_announcement = self._select_best_announcement(announcements)

        # Create result
        result = {
            "success": True,
            "announcement": best_announcement["text"],
            "variants": announcements,
            "metadata": {
                "length": len(best_announcement["text"]),
                "template": best_announcement["template"],
                "milestone_dir": str(milestone_dir),
                "timestamp": time.time(),
                "hashtags": self._generate_hashtags(milestone_info),
                "milestone_info": milestone_info,
            },
        }

        # Write announcement to file
        self._write_announcement(milestone_dir, result)

        print(f"✅ Announcement generated ({len(best_announcement['text'])} chars)")
        return result

    def _extract_milestone_info(self, milestone_dir: Path) -> Dict[str, Any]:
        """Extract information from milestone directory."""
        info = {
            "title": milestone_dir.name,
            "summary": "New milestone completed",
            "features": [],
            "tech_stack": [],
            "file_count": 0,
            "has_tests": False,
            "has_docs": False,
        }

        # Check for manifest.json (from dev agent)
        manifest_file = milestone_dir / "manifest.json"
        if manifest_file.exists():
            try:
                with open(manifest_file) as f:
                    manifest = json.load(f)

                info.update(
                    {
                        "title": manifest.get("project_title", info["title"]),
                        "summary": manifest.get("project_summary", info["summary"])[:100],
                        "tech_stack": manifest.get("tech_stack", []),
                        "features": [
                            m.get("name", "Feature") for m in manifest.get("milestones", [])
                        ],
                    }
                )

            except (OSError, json.JSONDecodeError):
                pass

        # Check for milestone.json (from planner)
        milestone_file = milestone_dir / "milestone.json"
        if milestone_file.exists():
            try:
                with open(milestone_file) as f:
                    milestone = json.load(f)

                if "name" in milestone:
                    info["title"] = milestone["name"]
                if "description" in milestone:
                    info["summary"] = milestone["description"][:100]

            except (OSError, json.JSONDecodeError):
                pass

        # Analyze directory contents
        python_files = list(milestone_dir.rglob("*.py"))
        test_files = [f for f in python_files if "test" in f.name.lower()]
        doc_files = list(milestone_dir.rglob("*.md")) + list(milestone_dir.rglob("README*"))

        info.update(
            {
                "file_count": len(python_files),
                "has_tests": len(test_files) > 0,
                "has_docs": len(doc_files) > 0,
            }
        )

        # Extract features from file structure
        if not info["features"]:
            # Infer features from directory/file names
            features = set()
            for py_file in python_files:
                if not py_file.name.startswith("__") and py_file.name != "main.py":
                    feature_name = py_file.stem.replace("_", " ").title()
                    if len(feature_name) < 30:  # Reasonable length
                        features.add(feature_name)

            info["features"] = list(features)[:3]  # Limit to 3 features

        return info

    def _generate_announcements(self, milestone_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate multiple announcement variants."""
        announcements = []
        hashtags = self._generate_hashtags(milestone_info)

        # Template 1: Simple milestone announcement
        simple_text = self.templates["simple"].format(
            title=milestone_info["title"], summary=milestone_info["summary"], hashtags=hashtags
        )
        announcements.append(
            {
                "template": "simple",
                "text": self._truncate_to_limit(simple_text),
                "score": self._score_announcement(simple_text, milestone_info),
            }
        )

        # Template 2: Feature-focused announcement
        if milestone_info["features"]:
            feature_list = ", ".join(milestone_info["features"][:2])
            feature_text = self.templates["feature_update"].format(
                features=feature_list, hashtags=hashtags
            )
            announcements.append(
                {
                    "template": "feature_update",
                    "text": self._truncate_to_limit(feature_text),
                    "score": self._score_announcement(feature_text, milestone_info),
                }
            )

        # Template 3: Tech stack announcement
        if milestone_info["tech_stack"]:
            tech_list = ", ".join(milestone_info["tech_stack"][:3])
            tech_text = self.templates["tech_stack"].format(
                tech_stack=tech_list, summary=milestone_info["summary"][:50], hashtags=hashtags
            )
            announcements.append(
                {
                    "template": "tech_stack",
                    "text": self._truncate_to_limit(tech_text),
                    "score": self._score_announcement(tech_text, milestone_info),
                }
            )

        # Template 4: Progress update
        feature_count = len(milestone_info["features"])
        if feature_count > 0:
            progress_text = self.templates["progress"].format(
                summary=milestone_info["summary"][:60],
                feature_count=feature_count,
                hashtags=hashtags,
            )
            announcements.append(
                {
                    "template": "progress",
                    "text": self._truncate_to_limit(progress_text),
                    "score": self._score_announcement(progress_text, milestone_info),
                }
            )

        return announcements

    def _generate_hashtags(self, milestone_info: Dict[str, Any]) -> str:
        """Generate relevant hashtags for the announcement."""
        hashtags = ["#SoloPilot", "#AI", "#Automation"]

        # Add tech stack hashtags
        tech_hashtags = {
            "python": "#Python",
            "javascript": "#JavaScript",
            "react": "#React",
            "node.js": "#NodeJS",
            "express": "#Express",
            "postgresql": "#PostgreSQL",
            "docker": "#Docker",
            "aws": "#AWS",
        }

        for tech in milestone_info.get("tech_stack", []):
            tech_lower = tech.lower()
            if tech_lower in tech_hashtags:
                hashtags.append(tech_hashtags[tech_lower])

        # Add feature-based hashtags
        if milestone_info.get("has_tests"):
            hashtags.append("#Testing")
        if milestone_info.get("has_docs"):
            hashtags.append("#Documentation")

        # Limit to 5 hashtags to save space
        return " ".join(hashtags[:5])

    def _score_announcement(self, text: str, milestone_info: Dict[str, Any]) -> float:
        """Score announcement based on various factors."""
        score = 0.0

        # Length scoring (prefer closer to Twitter limit but not over)
        length_ratio = len(text) / self.max_length
        if length_ratio <= 1.0:
            score += (1.0 - abs(0.85 - length_ratio)) * 30  # Prefer ~85% of limit
        else:
            score -= 50  # Penalty for being over limit

        # Content richness
        if milestone_info["title"].lower() in text.lower():
            score += 20
        if milestone_info["features"]:
            score += 15
        if milestone_info["tech_stack"]:
            score += 10
        if milestone_info["has_tests"]:
            score += 5
        if milestone_info["has_docs"]:
            score += 5

        # Engagement factors
        emoji_count = sum(1 for char in text if ord(char) > 0x1F000)
        score += min(emoji_count * 3, 15)  # Max 15 points for emojis

        hashtag_count = text.count("#")
        score += min(hashtag_count * 2, 10)  # Max 10 points for hashtags

        return score

    def _select_best_announcement(self, announcements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Select the best announcement based on scoring."""
        if not announcements:
            return {
                "template": "fallback",
                "text": "🚀 New milestone completed! #SoloPilot #AI",
                "score": 0.0,
            }

        return max(announcements, key=lambda x: x["score"])

    def _truncate_to_limit(self, text: str) -> str:
        """Truncate text to Twitter character limit."""
        if len(text) <= self.max_length:
            return text

        # Try to truncate at word boundary
        truncated = text[: self.max_length - 3]
        last_space = truncated.rfind(" ")

        if last_space > self.max_length * 0.7:  # If we can save significant text
            return truncated[:last_space] + "..."
        else:
            return truncated + "..."

    def _write_announcement(self, milestone_dir: Path, result: Dict[str, Any]) -> None:
        """Write announcement to milestone directory."""
        announcement_file = milestone_dir / "announcement.md"

        content_lines = [
            "# Marketing Announcement",
            "",
            f"**Generated**: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Template**: {result['metadata']['template']}",
            f"**Length**: {result['metadata']['length']}/280 characters",
            "",
            "## Final Announcement",
            "",
            "```",
            result["announcement"],
            "```",
            "",
            "## Variants",
            "",
        ]

        for i, variant in enumerate(result["variants"], 1):
            content_lines.extend(
                [
                    f"### Variant {i} ({variant['template']}) - Score: {variant['score']:.1f}",
                    "",
                    "```",
                    variant["text"],
                    "```",
                    "",
                ]
            )

        content_lines.extend(
            [
                "## Metadata",
                "",
                f"- **Hashtags**: {result['metadata']['hashtags']}",
                f"- **Milestone Features**: {len(result['metadata']['milestone_info']['features'])}",
                f"- **Tech Stack**: {', '.join(result['metadata']['milestone_info']['tech_stack']) or 'Not specified'}",
                f"- **Has Tests**: {result['metadata']['milestone_info']['has_tests']}",
                f"- **Has Docs**: {result['metadata']['milestone_info']['has_docs']}",
                "",
                "---",
                "*Generated by SoloPilot Marketing Poster Agent*",
            ]
        )

        with open(announcement_file, "w", encoding="utf-8") as f:
            f.write("\n".join(content_lines))

        print(f"📄 Announcement written to {announcement_file}")

    def get_stats(self) -> Dict[str, Any]:
        """Get marketing poster statistics."""
        return {
            "templates": len(self.templates),
            "max_length": self.max_length,
            "available_templates": list(self.templates.keys()),
        }


def main():
    """Main function for testing marketing poster."""
    import sys

    if len(sys.argv) != 2:
        print("Usage: python poster.py <milestone_dir>")
        sys.exit(1)

    milestone_dir = Path(sys.argv[1])
    poster = MarketingPoster()
    result = poster.announce(milestone_dir)

    if result["success"]:
        print(f"\n📢 Final Announcement ({result['metadata']['length']} chars):")
        print(f"'{result['announcement']}'")
        print(f"\n✅ {len(result['variants'])} variants generated")
    else:
        print(f"❌ Failed: {result['error']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
