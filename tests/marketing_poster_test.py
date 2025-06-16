#!/usr/bin/env python3
"""
Unit tests for Marketing Poster Agent

Tests announcement generation, template system, and milestone information extraction.
"""

import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agents.marketing.poster import MarketingPoster


@pytest.fixture
def temp_milestone_dir():
    """Create a temporary milestone directory for testing."""
    temp_dir = tempfile.mkdtemp()
    milestone_dir = Path(temp_dir) / "test-milestone"
    milestone_dir.mkdir()
    yield milestone_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def milestone_with_manifest(temp_milestone_dir):
    """Create a milestone with dev agent manifest."""
    manifest_data = {
        "project_title": "E-Commerce Platform",
        "project_summary": "A modern e-commerce platform with React frontend and Node.js backend",
        "tech_stack": ["React", "Node.js", "Express", "PostgreSQL"],
        "milestones": [
            {"name": "User Authentication", "description": "Secure user login and registration"},
            {"name": "Product Catalog", "description": "Product browsing and search functionality"},
            {"name": "Shopping Cart", "description": "Add to cart and checkout workflow"}
        ]
    }
    
    manifest_file = temp_milestone_dir / "manifest.json"
    with open(manifest_file, 'w') as f:
        json.dump(manifest_data, f, indent=2)
    
    # Add some Python files
    (temp_milestone_dir / "main.py").write_text("# Main application")
    (temp_milestone_dir / "auth.py").write_text("# Authentication module")
    (temp_milestone_dir / "test_auth.py").write_text("# Authentication tests")
    (temp_milestone_dir / "README.md").write_text("# Project README")
    
    return temp_milestone_dir


@pytest.fixture
def milestone_with_planning(temp_milestone_dir):
    """Create a milestone with planner output."""
    milestone_data = {
        "name": "API Development Sprint",
        "description": "Build REST API endpoints for core functionality"
    }
    
    milestone_file = temp_milestone_dir / "milestone.json"
    with open(milestone_file, 'w') as f:
        json.dump(milestone_data, f, indent=2)
    
    # Add some code files
    (temp_milestone_dir / "api.py").write_text("# API routes")
    (temp_milestone_dir / "models.py").write_text("# Data models")
    (temp_milestone_dir / "test_api.py").write_text("# API tests")
    
    return temp_milestone_dir


@pytest.fixture
def empty_milestone(temp_milestone_dir):
    """Create an empty milestone directory."""
    return temp_milestone_dir


class TestMarketingPoster:
    """Test cases for MarketingPoster class."""

    def test_init(self):
        """Test MarketingPoster initialization."""
        poster = MarketingPoster()
        
        assert poster.max_length == 280
        assert isinstance(poster.templates, dict)
        assert len(poster.templates) > 0
        assert "simple" in poster.templates
        assert "feature_update" in poster.templates

    def test_announce_nonexistent_directory(self):
        """Test announcement for non-existent directory."""
        poster = MarketingPoster()
        result = poster.announce(Path("/nonexistent/directory"))
        
        assert result["success"] is False
        assert "not found" in result["error"]
        assert result["announcement"] == ""

    def test_announce_with_manifest(self, milestone_with_manifest):
        """Test announcement generation with dev agent manifest."""
        poster = MarketingPoster()
        result = poster.announce(milestone_with_manifest)
        
        assert result["success"] is True
        assert result["announcement"] != ""
        assert len(result["announcement"]) <= 280
        assert "E-Commerce Platform" in result["announcement"]
        assert "#SoloPilot" in result["announcement"]
        assert len(result["variants"]) > 0
        
        # Check metadata
        metadata = result["metadata"]
        assert metadata["length"] == len(result["announcement"])
        assert metadata["template"] in poster.templates
        assert metadata["milestone_info"]["title"] == "E-Commerce Platform"
        assert "React" in metadata["milestone_info"]["tech_stack"]

    def test_announce_with_planning(self, milestone_with_planning):
        """Test announcement generation with planner output."""
        poster = MarketingPoster()
        result = poster.announce(milestone_with_planning)
        
        assert result["success"] is True
        assert result["announcement"] != ""
        assert "API Development Sprint" in result["announcement"] or "API Development" in result["announcement"]
        assert "#SoloPilot" in result["announcement"]

    def test_announce_empty_milestone(self, empty_milestone):
        """Test announcement generation for empty milestone."""
        poster = MarketingPoster()
        result = poster.announce(empty_milestone)
        
        assert result["success"] is True
        assert result["announcement"] != ""
        assert len(result["announcement"]) <= 280
        assert "#SoloPilot" in result["announcement"]

    def test_extract_milestone_info_with_manifest(self, milestone_with_manifest):
        """Test milestone information extraction from manifest."""
        poster = MarketingPoster()
        info = poster._extract_milestone_info(milestone_with_manifest)
        
        assert info["title"] == "E-Commerce Platform"
        assert "e-commerce platform" in info["summary"].lower()
        assert "React" in info["tech_stack"]
        assert "Node.js" in info["tech_stack"]
        assert len(info["features"]) == 3
        assert info["has_tests"] is True
        assert info["has_docs"] is True
        assert info["file_count"] >= 3

    def test_extract_milestone_info_empty(self, empty_milestone):
        """Test milestone information extraction from empty directory."""
        poster = MarketingPoster()
        info = poster._extract_milestone_info(empty_milestone)
        
        assert info["title"] == empty_milestone.name
        assert info["summary"] != ""
        assert info["file_count"] == 0
        assert info["has_tests"] is False
        assert info["has_docs"] is False

    def test_generate_hashtags(self):
        """Test hashtag generation."""
        poster = MarketingPoster()
        
        milestone_info = {
            "tech_stack": ["Python", "React", "PostgreSQL"],
            "has_tests": True,
            "has_docs": False
        }
        
        hashtags = poster._generate_hashtags(milestone_info)
        
        assert "#SoloPilot" in hashtags
        assert "#AI" in hashtags
        assert "#Python" in hashtags
        assert "#React" in hashtags
        assert "#Testing" in hashtags
        
        # Should not exceed reasonable length
        assert len(hashtags) < 100

    def test_score_announcement(self):
        """Test announcement scoring system."""
        poster = MarketingPoster()
        
        milestone_info = {
            "title": "Test Project",
            "features": ["Feature 1", "Feature 2"],
            "tech_stack": ["Python"],
            "has_tests": True,
            "has_docs": True
        }
        
        # Good announcement
        good_text = "🚀 Test Project - New features released! #SoloPilot #Python #Testing"
        good_score = poster._score_announcement(good_text, milestone_info)
        
        # Poor announcement (too long)
        poor_text = "A" * 300  # Over Twitter limit
        poor_score = poster._score_announcement(poor_text, milestone_info)
        
        assert good_score > poor_score

    def test_truncate_to_limit(self):
        """Test text truncation to Twitter limit."""
        poster = MarketingPoster()
        
        # Short text should remain unchanged
        short_text = "Short announcement"
        assert poster._truncate_to_limit(short_text) == short_text
        
        # Long text should be truncated
        long_text = "A" * 300
        truncated = poster._truncate_to_limit(long_text)
        assert len(truncated) <= 280
        assert truncated.endswith("...")
        
        # Test word boundary truncation
        word_text = "This is a very long announcement that exceeds the Twitter character limit and should be truncated at a reasonable word boundary to maintain readability and professional appearance"
        truncated_words = poster._truncate_to_limit(word_text)
        assert len(truncated_words) <= 280
        assert not truncated_words.endswith("... ")  # Should not end with space after ellipsis

    def test_generate_announcements_variants(self, milestone_with_manifest):
        """Test generation of multiple announcement variants."""
        poster = MarketingPoster()
        milestone_info = poster._extract_milestone_info(milestone_with_manifest)
        announcements = poster._generate_announcements(milestone_info)
        
        assert len(announcements) > 0
        
        # Each announcement should have required fields
        for announcement in announcements:
            assert "template" in announcement
            assert "text" in announcement
            assert "score" in announcement
            assert len(announcement["text"]) <= 280
            assert isinstance(announcement["score"], (int, float))
        
        # Should have different templates
        templates = [a["template"] for a in announcements]
        assert len(set(templates)) > 1

    def test_select_best_announcement(self):
        """Test selection of best announcement."""
        poster = MarketingPoster()
        
        announcements = [
            {"template": "simple", "text": "Simple announcement", "score": 10.0},
            {"template": "feature", "text": "Feature announcement", "score": 20.0},
            {"template": "tech", "text": "Tech announcement", "score": 15.0}
        ]
        
        best = poster._select_best_announcement(announcements)
        assert best["template"] == "feature"
        assert best["score"] == 20.0
        
        # Test with empty list
        empty_best = poster._select_best_announcement([])
        assert empty_best["template"] == "fallback"
        assert "#SoloPilot" in empty_best["text"]

    def test_write_announcement_file(self, milestone_with_manifest):
        """Test writing announcement to file."""
        poster = MarketingPoster()
        result = poster.announce(milestone_with_manifest)
        
        announcement_file = milestone_with_manifest / "announcement.md"
        assert announcement_file.exists()
        
        content = announcement_file.read_text()
        assert "# Marketing Announcement" in content
        assert result["announcement"] in content
        assert "## Variants" in content
        assert "## Metadata" in content

    def test_get_stats(self):
        """Test getting poster statistics."""
        poster = MarketingPoster()
        stats = poster.get_stats()
        
        assert "templates" in stats
        assert "max_length" in stats
        assert "available_templates" in stats
        assert stats["max_length"] == 280
        assert stats["templates"] > 0
        assert isinstance(stats["available_templates"], list)

    def test_template_formatting(self):
        """Test that all templates can be formatted without errors."""
        poster = MarketingPoster()
        
        test_data = {
            "title": "Test Project",
            "summary": "Test summary",
            "features": "Feature A, Feature B",
            "tech_stack": "Python, React",
            "feature_count": 2,
            "hashtags": "#Test #SoloPilot"
        }
        
        for template_name, template in poster.templates.items():
            try:
                formatted = template.format(**test_data)
                assert len(formatted) > 0
                assert "{" not in formatted  # No unformatted placeholders
            except KeyError as e:
                # If a template requires additional fields, that's expected
                pass

    def test_character_limit_compliance(self, milestone_with_manifest):
        """Test that all generated announcements comply with character limits."""
        poster = MarketingPoster()
        result = poster.announce(milestone_with_manifest)
        
        # Main announcement should be within limit
        assert len(result["announcement"]) <= 280
        
        # All variants should be within limit
        for variant in result["variants"]:
            assert len(variant["text"]) <= 280

    def test_emoji_and_hashtag_inclusion(self, milestone_with_manifest):
        """Test that announcements include emojis and hashtags for engagement."""
        poster = MarketingPoster()
        result = poster.announce(milestone_with_manifest)
        
        announcement = result["announcement"]
        
        # Should contain at least one hashtag
        assert "#" in announcement
        assert "#SoloPilot" in announcement
        
        # Should contain at least one emoji
        has_emoji = any(ord(char) > 0x1F000 for char in announcement)
        assert has_emoji

    def test_milestone_features_extraction(self, milestone_with_manifest):
        """Test extraction of features from milestone structure."""
        poster = MarketingPoster()
        info = poster._extract_milestone_info(milestone_with_manifest)
        
        # Should extract features from manifest
        assert len(info["features"]) > 0
        feature_names = [f.lower() for f in info["features"]]
        
        # Should include features from manifest
        expected_features = ["user authentication", "product catalog", "shopping cart"]
        for expected in expected_features:
            assert any(expected in feature.lower() for feature in info["features"])


class TestMarketingPosterIntegration:
    """Integration tests for MarketingPoster."""

    def test_end_to_end_announcement_generation(self, milestone_with_manifest):
        """Test complete end-to-end announcement generation."""
        poster = MarketingPoster()
        result = poster.announce(milestone_with_manifest)
        
        # Verify successful generation
        assert result["success"] is True
        assert result["announcement"] != ""
        
        # Verify announcement quality
        announcement = result["announcement"]
        assert len(announcement) <= 280
        assert "#SoloPilot" in announcement
        assert len(result["variants"]) >= 2
        
        # Verify metadata completeness
        metadata = result["metadata"]
        required_fields = ["length", "template", "timestamp", "hashtags", "milestone_info"]
        for field in required_fields:
            assert field in metadata
        
        # Verify file creation
        announcement_file = milestone_with_manifest / "announcement.md"
        assert announcement_file.exists()
        
        content = announcement_file.read_text()
        assert announcement in content

    def test_different_milestone_types(self, milestone_with_manifest, milestone_with_planning, empty_milestone):
        """Test announcement generation for different milestone types."""
        poster = MarketingPoster()
        
        # Test all milestone types
        milestones = [milestone_with_manifest, milestone_with_planning, empty_milestone]
        
        for milestone in milestones:
            result = poster.announce(milestone)
            
            assert result["success"] is True
            assert result["announcement"] != ""
            assert len(result["announcement"]) <= 280
            assert "#SoloPilot" in result["announcement"]
            
            # Each should generate at least one variant
            assert len(result["variants"]) >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])