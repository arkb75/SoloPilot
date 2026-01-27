"""S3 storage for wireframe HTML files."""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

from .wireframe_version_index import WireframeVersion, WireframeVersionIndex

logger = logging.getLogger(__name__)


class S3WireframeStore:
    """Manages wireframe storage in S3 with versioning."""

    def __init__(self, bucket_name: str, table_name: str = "wireframe_versions"):
        """Initialize wireframe store.

        Args:
            bucket_name: S3 bucket name
            table_name: DynamoDB table for version tracking
        """
        self.bucket_name = bucket_name
        self.s3_client = boto3.client("s3")
        self.version_index = WireframeVersionIndex(table_name)

    def store_wireframes(
        self,
        conversation_id: str,
        screens: List[Dict[str, Any]],
        index_html: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[WireframeVersion, Optional[str]]:
        """Store wireframe screens in S3.

        Args:
            conversation_id: Conversation ID
            screens: List of screen dicts with 'id', 'name', 'html'
            index_html: Combined index.html content
            metadata: Additional metadata

        Returns:
            Tuple of (WireframeVersion, error_message)
        """
        try:
            # Allocate version
            version_num = self.version_index.allocate_next_version(conversation_id)
            s3_key_prefix = f"wireframes/{conversation_id}/v{version_num:04d}"

            # Store index.html
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=f"{s3_key_prefix}/index.html",
                Body=index_html,
                ContentType="text/html",
            )

            # Store each screen
            for screen in screens:
                screen_key = f"{s3_key_prefix}/screens/{screen['id']}.html"
                self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=screen_key,
                    Body=screen["html"],
                    ContentType="text/html",
                )

            # Store metadata
            full_metadata = {
                "version": version_num,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "screen_count": len(screens),
                "screens": [
                    {"id": s["id"], "name": s["name"], "description": s.get("description", "")}
                    for s in screens
                ],
                **(metadata or {}),
            }

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=f"{s3_key_prefix}/metadata.json",
                Body=json.dumps(full_metadata, default=str),
                ContentType="application/json",
            )

            # Record version in DynamoDB
            wireframe_version = self.version_index.record_version(
                conversation_id=conversation_id,
                version=version_num,
                s3_key=s3_key_prefix,
                screen_count=len(screens),
                metadata={
                    "screen_names": [s["name"] for s in screens],
                },
            )

            logger.info(f"Stored wireframes v{version_num} for {conversation_id}")
            return wireframe_version, None

        except Exception as e:
            logger.error(f"Error storing wireframes: {str(e)}")
            return None, str(e)

    def get_wireframe_url(
        self, conversation_id: str, version: int, screen_id: Optional[str] = None
    ) -> Optional[str]:
        """Get presigned URL for a wireframe.

        Args:
            conversation_id: Conversation ID
            version: Version number
            screen_id: Optional screen ID (defaults to index.html)

        Returns:
            Presigned URL or None
        """
        try:
            wireframe_version = self.version_index.get_version(conversation_id, version)
            if not wireframe_version:
                return None

            if screen_id:
                key = f"{wireframe_version.s3_key}/screens/{screen_id}.html"
            else:
                key = f"{wireframe_version.s3_key}/index.html"

            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=3600,
            )

            return url

        except Exception as e:
            logger.error(f"Error generating presigned URL: {str(e)}")
            return None

    def get_screen_html(
        self, conversation_id: str, version: int, screen_id: str
    ) -> Optional[str]:
        """Get HTML content for a specific screen.

        Args:
            conversation_id: Conversation ID
            version: Version number
            screen_id: Screen ID

        Returns:
            HTML content or None
        """
        try:
            wireframe_version = self.version_index.get_version(conversation_id, version)
            if not wireframe_version:
                return None

            key = f"{wireframe_version.s3_key}/screens/{screen_id}.html"

            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return response["Body"].read().decode("utf-8")

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning(f"Screen {screen_id} not found")
                return None
            raise
        except Exception as e:
            logger.error(f"Error getting screen HTML: {str(e)}")
            return None

    def update_screen(
        self,
        conversation_id: str,
        version: int,
        screen_id: str,
        new_html: str,
    ) -> bool:
        """Update HTML for a specific screen.

        Args:
            conversation_id: Conversation ID
            version: Version number
            screen_id: Screen ID
            new_html: New HTML content

        Returns:
            True if successful
        """
        try:
            wireframe_version = self.version_index.get_version(conversation_id, version)
            if not wireframe_version:
                return False

            key = f"{wireframe_version.s3_key}/screens/{screen_id}.html"

            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=new_html,
                ContentType="text/html",
            )

            logger.info(f"Updated screen {screen_id} for wireframe v{version}")
            return True

        except Exception as e:
            logger.error(f"Error updating screen: {str(e)}")
            return False

    def get_metadata(self, conversation_id: str, version: int) -> Optional[Dict[str, Any]]:
        """Get metadata for a wireframe version.

        Args:
            conversation_id: Conversation ID
            version: Version number

        Returns:
            Metadata dict or None
        """
        try:
            wireframe_version = self.version_index.get_version(conversation_id, version)
            if not wireframe_version:
                return None

            key = f"{wireframe_version.s3_key}/metadata.json"

            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            return json.loads(response["Body"].read().decode("utf-8"))

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                return None
            raise
        except Exception as e:
            logger.error(f"Error getting metadata: {str(e)}")
            return None

    def export_as_react(
        self, conversation_id: str, version: int
    ) -> Optional[Dict[str, str]]:
        """Export wireframes as React components.

        Args:
            conversation_id: Conversation ID
            version: Version number

        Returns:
            Dict of {component_name: component_code} or None
        """
        try:
            metadata = self.get_metadata(conversation_id, version)
            if not metadata:
                return None

            components = {}
            for screen in metadata.get("screens", []):
                html = self.get_screen_html(conversation_id, version, screen["id"])
                if html:
                    component_name = self._to_component_name(screen["name"])
                    components[component_name] = self._html_to_react(html, component_name)

            return components

        except Exception as e:
            logger.error(f"Error exporting as React: {str(e)}")
            return None

    def _to_component_name(self, screen_name: str) -> str:
        """Convert screen name to React component name."""
        # Remove special chars and convert to PascalCase
        words = screen_name.replace("/", " ").replace("-", " ").replace("_", " ").split()
        return "".join(word.capitalize() for word in words)

    def _html_to_react(self, html: str, component_name: str) -> str:
        """Convert HTML to a React functional component."""
        # Extract body content (simplified conversion)
        body_start = html.lower().find("<body")
        body_end = html.lower().find("</body>")

        if body_start != -1 and body_end != -1:
            # Find the end of the body opening tag
            body_tag_end = html.find(">", body_start) + 1
            body_content = html[body_tag_end:body_end]
        else:
            body_content = html

        # Basic replacements for JSX compatibility
        jsx_content = body_content
        jsx_content = jsx_content.replace("class=", "className=")
        jsx_content = jsx_content.replace("for=", "htmlFor=")

        return f'''import React from 'react';

export default function {component_name}() {{
  return (
    <div className="min-h-screen">
      {jsx_content.strip()}
    </div>
  );
}}
'''
