"""S3 storage operations for proposal PDFs."""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

from .models import ProposalMetadata, ProposalVersion
from .proposal_version_index import ProposalVersionIndex

logger = logging.getLogger(__name__)


class S3ProposalStore:
    """Manages proposal PDF storage in S3."""

    def __init__(
        self,
        bucket_name: str,
        version_index: Optional[ProposalVersionIndex] = None,
        s3_client=None,
    ):
        """Initialize S3 store.

        Args:
            bucket_name: S3 bucket name
            version_index: ProposalVersionIndex instance
            s3_client: Optional S3 client (for testing)
        """
        self.bucket_name = bucket_name
        self.s3_client = s3_client or boto3.client("s3")
        self.version_index = version_index or ProposalVersionIndex()

    def _calculate_requirements_hash(self, requirements: Dict) -> str:
        """Calculate a hash of requirements for change detection.

        Args:
            requirements: Requirements dictionary

        Returns:
            SHA256 hash of requirements
        """
        # Sort keys for consistent hashing
        def _default(o):
            # Convert Decimal to string to get stable hash across environments
            try:
                from decimal import Decimal  # local import to avoid global dependency
                if isinstance(o, Decimal):
                    # Preserve numeric intent while avoiding float rounding
                    return str(o)
            except Exception:
                pass
            return str(o)

        sorted_req = json.dumps(requirements, sort_keys=True, default=_default)
        return hashlib.sha256(sorted_req.encode()).hexdigest()[:16]

    def store_proposal(
        self,
        conversation_id: str,
        pdf_bytes: bytes,
        proposal_data: Dict[str, any],
        requirements: Dict[str, any],
        revised_requirements: Optional[Dict[str, Any]] = None,
        generated_by: str = "proposal_draft",
    ) -> Tuple[ProposalVersion, str]:
        """Store a proposal PDF and metadata in S3.

        Args:
            conversation_id: Conversation ID
            pdf_bytes: PDF content
            proposal_data: Data used to generate the proposal
            requirements: Original requirements
            revised_requirements: Revised requirements if any
            generated_by: Phase that generated the proposal

        Returns:
            Tuple of (ProposalVersion, s3_key)
        """
        try:
            # Allocate version number
            version = self.version_index.allocate_next_version(conversation_id)

            # Build S3 key structure
            s3_key_prefix = f"proposals/{conversation_id}/v{version:04d}"
            pdf_key = f"{s3_key_prefix}/proposal.pdf"
            metadata_key = f"{s3_key_prefix}/metadata.json"

            # Calculate requirements hash
            all_requirements = requirements.copy()
            if revised_requirements:
                all_requirements.update(revised_requirements)
            requirements_hash = self._calculate_requirements_hash(all_requirements)

            # Prepare metadata
            metadata = ProposalMetadata(
                version=version,
                created_at=datetime.now(timezone.utc).isoformat(),
                requirements_hash=requirements_hash,
                budget=proposal_data.get("pricing", [{}])[0]
                .get("amount", "")
                .replace("$", "")
                .replace(",", "")
                or None,
                removed_features=(
                    revised_requirements.get("removed_features", []) if revised_requirements else []
                ),
                client_name=proposal_data.get("clientName", ""),
                project_type=proposal_data.get("projectTitle", ""),
                file_size=len(pdf_bytes),
                generated_by=generated_by,
                requirements_used=requirements,
                revised_requirements_used=revised_requirements,
            )

            # Store PDF in S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=pdf_key,
                Body=pdf_bytes,
                ContentType="application/pdf",
                Metadata={
                    "conversation_id": conversation_id,
                    "version": str(version),
                    "generated_at": metadata.created_at,
                },
            )
            logger.info(f"Stored PDF at s3://{self.bucket_name}/{pdf_key}")

            # Store metadata in S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=metadata_key,
                Body=json.dumps(metadata.__dict__, default=str),
                ContentType="application/json",
            )
            logger.info(f"Stored metadata at s3://{self.bucket_name}/{metadata_key}")

            # Record in DynamoDB
            proposal_version = self.version_index.record_version(
                conversation_id=conversation_id,
                version=version,
                s3_key=s3_key_prefix,
                file_size=len(pdf_bytes),
                requirements_hash=requirements_hash,
                metadata={
                    "budget": metadata.budget,
                    "client_name": metadata.client_name,
                    "project_type": metadata.project_type,
                    "has_revisions": bool(revised_requirements),
                },
            )

            return proposal_version, s3_key_prefix

        except Exception as e:
            logger.error(f"Error storing proposal: {str(e)}")
            raise

    def get_proposal_pdf(self, conversation_id: str, version: int) -> Optional[bytes]:
        """Retrieve a proposal PDF from S3.

        Args:
            conversation_id: Conversation ID
            version: Version number

        Returns:
            PDF bytes if found, None otherwise
        """
        try:
            # Get version info from DynamoDB
            proposal_version = self.version_index.get_version(conversation_id, version)
            if not proposal_version:
                logger.warning(f"Version {version} not found for {conversation_id}")
                return None

            # Get PDF from S3
            pdf_key = proposal_version.s3_pdf_key
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=pdf_key)

            return response["Body"].read()

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning(f"PDF not found in S3: {pdf_key}")
                return None
            logger.error(f"Error getting PDF: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error getting proposal PDF: {str(e)}")
            return None

    def get_proposal_metadata(self, conversation_id: str, version: int) -> Optional[Dict[str, Any]]:
        """Retrieve proposal metadata from S3.

        Args:
            conversation_id: Conversation ID
            version: Version number

        Returns:
            Metadata dict if found, None otherwise
        """
        try:
            # Get version info from DynamoDB
            proposal_version = self.version_index.get_version(conversation_id, version)
            if not proposal_version:
                return None

            # Get metadata from S3
            metadata_key = proposal_version.s3_metadata_key
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=metadata_key)

            return json.loads(response["Body"].read())

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                logger.warning(f"Metadata not found in S3: {metadata_key}")
                return None
            logger.error(f"Error getting metadata: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error getting proposal metadata: {str(e)}")
            return None

    def generate_presigned_url(
        self, conversation_id: str, version: int, expiration: int = 3600
    ) -> Optional[str]:
        """Generate a presigned URL for secure PDF access.

        Args:
            conversation_id: Conversation ID
            version: Version number
            expiration: URL expiration in seconds (default 1 hour)

        Returns:
            Presigned URL if successful, None otherwise
        """
        try:
            # Get version info
            proposal_version = self.version_index.get_version(conversation_id, version)
            if not proposal_version:
                return None

            # Generate presigned URL
            pdf_key = proposal_version.s3_pdf_key
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": pdf_key},
                ExpiresIn=expiration,
            )

            logger.info(f"Generated presigned URL for {pdf_key}, expires in {expiration}s")
            return url

        except Exception as e:
            logger.error(f"Error generating presigned URL: {str(e)}")
            return None

    def delete_proposal(self, conversation_id: str, version: int) -> bool:
        """Delete a proposal (soft delete in DynamoDB, keep S3 files).

        Args:
            conversation_id: Conversation ID
            version: Version number

        Returns:
            True if successful, False otherwise
        """
        # Only mark as deleted in DynamoDB, keep S3 files for audit
        return self.version_index.delete_version(conversation_id, version)
