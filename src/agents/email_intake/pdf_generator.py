"""
PDF Generation Integration for Email Intake Agent

This module handles the integration between the email intake agent and the
document generation Lambda for creating proposal PDFs.
"""

import base64
import json
import logging
import os
from datetime import datetime
from typing import Dict, Optional, Tuple

import boto3

logger = logging.getLogger()

# Initialize Lambda client
lambda_client = boto3.client("lambda")

# Import storage modules if available
try:
    from src.storage import S3ProposalStore

    STORAGE_AVAILABLE = True
except ImportError:
    # Running in Lambda without storage module
    STORAGE_AVAILABLE = False
    logger.info("Storage module not available, S3 storage disabled")


class ProposalPDFGenerator:
    """Handles proposal PDF generation for the email intake agent."""

    def __init__(self, pdf_lambda_arn: str, s3_bucket: Optional[str] = None):
        """
        Initialize the PDF generator.

        Args:
            pdf_lambda_arn: ARN of the document generation Lambda
            s3_bucket: S3 bucket name for storing proposals (optional)
        """
        self.pdf_lambda_arn = pdf_lambda_arn
        # Prefer unified DOCUMENT_BUCKET; fallback for legacy env var
        self.s3_bucket = s3_bucket or os.environ.get("DOCUMENT_BUCKET") or os.environ.get("ATTACHMENTS_BUCKET")

        # Initialize S3 store if available and bucket is configured
        self.s3_store = None
        if STORAGE_AVAILABLE and self.s3_bucket:
            try:
                self.s3_store = S3ProposalStore(self.s3_bucket)
                logger.info(f"S3 storage enabled for bucket: {self.s3_bucket}")
            except Exception as e:
                logger.warning(f"Failed to initialize S3 store: {str(e)}")
                self.s3_store = None

    def generate_proposal_pdf_from_data(
        self, proposal_data: Dict, conversation_id: str, timeout: int = 5
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Generate a proposal PDF from pre-extracted proposal data.
        
        Args:
            proposal_data: Formatted proposal data (from ProposalDataMapper)
            conversation_id: Conversation identifier for S3 keying and traceability
            timeout: Lambda invocation timeout in seconds
            
        Returns:
            Tuple of (pdf_bytes, error_message)
        """
        try:
            # Prepare the payload for the PDF Lambda
            payload = {
                "template": "glassmorphic-proposal",
                "data": proposal_data,
                "conversationId": conversation_id,
                "docType": "proposal",
                "filename": "project-proposal.pdf",
            }

            logger.info(
                f"Generating proposal PDF for {proposal_data['clientName']} with conversationId: {conversation_id}"
            )
            logger.info(
                f"Payload keys: {list(payload.keys())}, data keys: {list(payload['data'].keys())}"
            )

            # Invoke the PDF generation Lambda synchronously
            response = lambda_client.invoke(
                FunctionName=self.pdf_lambda_arn,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload),
            )

            # Parse the response
            raw_response = response["Payload"].read()
            logger.info(
                f"Lambda response status: {response.get('StatusCode')}, response size: {len(raw_response)} bytes"
            )

            try:
                response_payload = json.loads(raw_response)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse Lambda response as JSON: {e}")
                logger.error(f"Raw response (first 500 chars): {raw_response[:500]}")
                return None, f"Invalid JSON response from PDF Lambda: {str(e)}"

            logger.info(f"Parsed response keys: {list(response_payload.keys())}")

            # Check if this is an HTTP response format (with statusCode and body)
            if response_payload.get("statusCode") == 200:
                # Parse the nested body JSON
                try:
                    body_json = json.loads(response_payload.get("body", "{}"))
                    logger.info(f"Parsed body keys: {list(body_json.keys())}")

                    if body_json.get("success"):
                        # Get the PDF from the response (base64 encoded)
                        pdf_base64 = body_json.get("pdf")
                        if pdf_base64:
                            pdf_bytes = base64.b64decode(pdf_base64)
                            logger.info(f"Successfully generated PDF ({len(pdf_bytes)} bytes)")
                            return pdf_bytes, None
                        else:
                            # If PDF not in response, might be in S3
                            s3_key = body_json.get("s3Key")
                            if s3_key:
                                logger.info(f"PDF stored in S3: {s3_key}")
                                # For now, we need the PDF bytes, so this is considered an error
                                return (
                                    None,
                                    f"PDF generated but not included in response. S3 key: {s3_key}",
                                )
                    else:
                        # Handle errors in the nested body
                        error_msg = body_json.get(
                            "error", body_json.get("errorMessage", "Unknown error in body")
                        )
                        return None, error_msg

                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse Lambda body JSON: {e}")
                    return None, f"Invalid body JSON in Lambda response: {str(e)}"

            elif response.get("StatusCode") == 200 and response_payload.get("success"):
                # Direct format (fallback for compatibility)
                pdf_base64 = response_payload.get("pdf")
                if pdf_base64:
                    pdf_bytes = base64.b64decode(pdf_base64)
                    logger.info(f"Successfully generated PDF ({len(pdf_bytes)} bytes)")
                    return pdf_bytes, None

            # Handle errors - log full response for debugging
            logger.error(f"PDF generation failed. Full response: {response_payload}")
            error_msg = response_payload.get(
                "error", response_payload.get("errorMessage", "Unknown error generating PDF")
            )
            if "errors" in response_payload:
                error_msg = f"Validation errors: {response_payload['errors']}"
            return None, error_msg

        except Exception as e:
            logger.error(f"Exception generating PDF: {str(e)}")
            return None, f"Failed to generate PDF: {str(e)}"

    def generate_and_store_proposal_pdf(
        self, conversation: Dict, timeout: int = 5
    ) -> Tuple[Optional[bytes], Optional[str], Optional[Dict]]:
        """
        Generate a proposal PDF and optionally store it in S3.

        Args:
            conversation: Full conversation history with metadata
            timeout: Lambda invocation timeout in seconds

        Returns:
            Tuple of (pdf_bytes, error_message, storage_info)
            storage_info contains version and s3_key if stored
        """
        # Import mapper here to avoid circular imports
        from src.agents.email_intake.proposal_mapper import ProposalDataMapper
        
        # Extract requirements
        requirements = conversation.get("requirements", {})
        if not requirements:
            return None, "No requirements found in conversation", None
        
        # Map requirements to proposal data
        mapper = ProposalDataMapper()
        proposal_data = mapper.map_requirements_to_proposal_data(requirements)
        
        # Use conversation_id
        conversation_id = conversation.get("conversation_id")
        if not conversation_id:
            return None, "Missing conversation_id in conversation", None
        
        # Generate the PDF
        pdf_bytes, error = self.generate_proposal_pdf_from_data(proposal_data, conversation_id, timeout)

        if not pdf_bytes or error:
            return pdf_bytes, error, None

        # If S3 storage is not available, just return the PDF
        if not self.s3_store:
            return pdf_bytes, error, None

        try:
            conversation_id = conversation.get("conversation_id")

            if not conversation_id:
                logger.warning("No conversation_id found, skipping S3 storage")
                return pdf_bytes, error, None

            # Allocate version and compute target key to avoid double-writes
            proposal_version_number = self.s3_store.version_index.allocate_next_version(conversation_id)
            s3_key_prefix = f"proposals/{conversation_id}/v{proposal_version_number:04d}"
            target_pdf_key = f"{s3_key_prefix}/proposal.pdf"

            # Ask doc-service to write directly to the target key using the same payload
            payload = {
                "template": "glassmorphic-proposal",
                "data": proposal_data,
                "conversationId": conversation_id,
                "docType": "proposal",
                "filename": "project-proposal.pdf",
                "s3Key": target_pdf_key,
            }

            response = lambda_client.invoke(
                FunctionName=self.pdf_lambda_arn,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload),
            )

            raw_response = response["Payload"].read()
            try:
                response_payload = json.loads(raw_response)
            except json.JSONDecodeError:
                logger.error(f"Doc-service returned non-JSON when writing to {target_pdf_key}: {raw_response[:200]}")
                return pdf_bytes, "Doc-service response parse error", None

            # Validate result
            if response_payload.get("statusCode") != 200:
                logger.error(f"Doc-service write failed for {target_pdf_key}: {response_payload}")
                return pdf_bytes, "Doc-service write failed", None

            # Store metadata.json in S3 (email-intake owns metadata and index)
            requirements_hash = self.s3_store._calculate_requirements_hash(requirements)
            metadata = {
                "version": proposal_version_number,
                "created_at": datetime.utcnow().isoformat(),
                "requirements_hash": requirements_hash,
                "budget": proposal_data.get("pricing", [{}])[0].get("amount", "").replace("$", "").replace(",", "") or None,
                "client_name": proposal_data.get("clientName", ""),
                "project_type": proposal_data.get("projectTitle", ""),
                "file_size": len(pdf_bytes),
                "generated_by": conversation.get("phase", "proposal_draft"),
            }

            try:
                self.s3_store.s3_client.put_object(
                    Bucket=self.s3_bucket,
                    Key=f"{s3_key_prefix}/metadata.json",
                    Body=json.dumps(metadata, default=str),
                    ContentType="application/json",
                )
            except Exception as meta_err:
                logger.warning(f"Failed to write metadata.json: {meta_err}")

            # Record in DynamoDB
            proposal_version = self.s3_store.version_index.record_version(
                conversation_id=conversation_id,
                version=proposal_version_number,
                s3_key=s3_key_prefix,
                file_size=len(pdf_bytes),
                requirements_hash=requirements_hash,
                metadata={
                    "budget": metadata["budget"],
                    "client_name": metadata["client_name"],
                    "project_type": metadata["project_type"],
                    "has_revisions": False,
                },
            )

            s3_key = s3_key_prefix

            storage_info = {
                "version": proposal_version.version,
                "s3_key": s3_key,
                "stored_at": proposal_version.created_at.isoformat(),
                "file_size": len(pdf_bytes),
            }

            logger.info(
                f"Stored proposal version {proposal_version.version} "
                f"for conversation {conversation_id}"
            )

            return pdf_bytes, error, storage_info

        except Exception as e:
            # Log but don't fail if storage fails
            logger.error(f"Failed to store proposal in S3: {str(e)}")
            return pdf_bytes, error, None
