"""Data models for proposal storage system."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class ProposalVersion:
    """Represents a single version of a proposal."""

    conversation_id: str
    version: int
    s3_key: str
    created_at: datetime
    file_size: int
    requirements_hash: str
    metadata: Dict[str, Any]

    @property
    def s3_pdf_key(self) -> str:
        """Get the S3 key for the PDF file."""
        return f"{self.s3_key}/proposal.pdf"

    @property
    def s3_metadata_key(self) -> str:
        """Get the S3 key for the metadata file."""
        return f"{self.s3_key}/metadata.json"


@dataclass
class ProposalMetadata:
    """Metadata stored alongside each proposal PDF."""

    version: int
    created_at: str
    requirements_hash: str
    budget: Optional[int]
    removed_features: List[str]
    client_name: str
    project_type: str
    file_size: int
    generated_by: str  # phase that generated it
    requirements_used: Dict[str, Any]  # snapshot of requirements
    revised_requirements_used: Optional[Dict[str, Any]]  # if any


@dataclass
class ProposalListItem:
    """Summary item for listing proposals."""

    version: int
    created_at: str
    file_size: int
    budget: Optional[int]
    has_revisions: bool
    s3_key: str
