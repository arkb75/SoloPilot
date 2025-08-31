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
    
    def extract_proposal_data(self, conversation: Dict) -> Dict:
        """
        DEPRECATED: Use ProposalDataMapper instead.
        This method is kept for backward compatibility only.
        
        Extract relevant data from the conversation for the proposal.

        Args:
            conversation: Full conversation history with metadata

        Returns:
            Dict with extracted proposal data
        """
        logger.warning("DEPRECATED: extract_proposal_data called. Use ProposalDataMapper instead.")
        # Use the main requirements (which are now always updated directly)
        effective_requirements = conversation.get("requirements", {})
        
        # Initialize field source tracking
        field_sources = {}

        # Get client info from conversation
        # client_email = conversation.get("client_email", "")  # Currently unused

        # Extract client name from email history
        client_name = "Client"
        if conversation.get("email_history"):
            first_email = conversation["email_history"][0]
            if first_email.get("direction") == "inbound":
                # Try to extract from email body signature
                body_lines = first_email.get("body", "").split("\n")
                signature_candidates = []

                # Collect potential name lines from signature area
                for line in reversed(body_lines):
                    line = line.strip()
                    if not line or line.startswith("--") or "@" in line:
                        continue

                    # Skip common non-name patterns
                    if any(
                        word in line.lower()
                        for word in ["thanks", "regards", "best", "sincerely", "cheers"]
                    ):
                        continue

                    # Skip lines that end with colon (likely headers like "Nice-to-haves:")
                    if line.endswith(":"):
                        continue

                    # Skip common section headers
                    if any(
                        header in line.lower()
                        for header in [
                            "nice-to-have",
                            "requirements",
                            "features",
                            "notes",
                            "additional",
                        ]
                    ):
                        continue

                    # Look for name-like patterns (1-3 words, starts with capital)
                    words = line.split()
                    if 1 <= len(words) <= 3 and words[0][0].isupper():
                        # Prefer lines that look like names over titles
                        if not any(
                            title in line.lower()
                            for title in [
                                "ceo",
                                "cto",
                                "manager",
                                "director",
                                "president",
                                "founder",
                            ]
                        ):
                            client_name = line.split("(")[0].strip()
                            field_sources["clientName"] = "PDF_GENERATOR: Extracted from email signature"
                            break
                        else:
                            signature_candidates.append(line)

                # Fallback to title lines if no pure name found
                if client_name == "Client" and signature_candidates:
                    client_name = signature_candidates[-1].split("(")[0].strip()
                    field_sources["clientName"] = "PDF_GENERATOR: Extracted from email signature (title line)"
                elif client_name == "Client":
                    field_sources["clientName"] = "PDF_GENERATOR: Default value (no signature found)"

        # Extract project details from understanding
        understanding = conversation.get("current_understanding", {})

        # Extract project type from email content
        project_type = "Web Development Project"
        field_sources["projectTitle"] = "PDF_GENERATOR: Default value"
        
        if conversation.get("email_history"):
            for email in conversation["email_history"]:
                if "dashboard" in email.get("body", "").lower():
                    project_type = "Internal Dashboard"
                    field_sources["projectTitle"] = "PDF_GENERATOR: Detected 'dashboard' in email content"
                    break
                elif "shopify" in email.get("body", "").lower():
                    project_type = "Shopify Dashboard"
                    field_sources["projectTitle"] = "PDF_GENERATOR: Detected 'shopify' in email content"
                    break

        # Build proposal data structure
        proposal_data = {
            "clientName": client_name,
            "projectTitle": project_type,
            "proposalDate": datetime.now().strftime("%B %Y"),
            "scope": [],
            "timeline": [],
            "pricing": [],
            "techStack": [],
        }

        # Extract scope from effective requirements
        removed_features = []  # No longer using revised_requirements

        if "dashboard" in project_type.lower():
            # Check if Shopify was originally mentioned but not removed
            has_shopify = False
            for email in conversation.get("email_history", []):
                body = email.get("body", "").lower()
                if "shopify" in body and "shopify" not in removed_features:
                    has_shopify = True
                    break

            if has_shopify:
                proposal_data["scope"] = [
                    {
                        "title": "Shopify Integration",
                        "description": "Connect to your Shopify store for real-time sales data",
                    },
                    {
                        "title": "Dashboard Development",
                        "description": "Build responsive dashboard with sales, inventory, and feedback widgets",
                    },
                    {
                        "title": "Google SSO Setup",
                        "description": "Implement secure authentication with Google Workspace",
                    },
                ]
                field_sources["scope"] = "PDF_GENERATOR: Shopify dashboard template (detected shopify + dashboard)"
            else:
                # Generic dashboard scope without Shopify
                proposal_data["scope"] = [
                    {
                        "title": "Dashboard Development",
                        "description": "Build a custom internal dashboard for your business metrics",
                    },
                    {
                        "title": "Data Integration",
                        "description": "Connect to your existing data sources and APIs",
                    },
                    {
                        "title": "User Authentication",
                        "description": "Implement secure access control for your team",
                    },
                ]
                field_sources["scope"] = "PDF_GENERATOR: Generic dashboard template"
        else:
            # Generic scope
            proposal_data["scope"] = [
                {
                    "title": "Discovery & Planning",
                    "description": "Understand requirements and create technical specification",
                },
                {
                    "title": "Development",
                    "description": "Build the solution with modern web technologies",
                },
                {
                    "title": "Testing & Launch",
                    "description": "Ensure quality and deploy to production",
                },
            ]
            field_sources["scope"] = "PDF_GENERATOR: Generic project template"

        # Generate timeline based on project complexity
        timeline_complexity = understanding.get("timeline", {})
        if timeline_complexity.get("urgency") == "high":
            weeks = [1, 2, 4, 1, 1]  # Faster timeline
            field_sources["timeline"] = "PDF_GENERATOR: Fast timeline template (high urgency detected)"
        else:
            weeks = [2, 3, 8, 2, 1]  # Standard timeline
            field_sources["timeline"] = "PDF_GENERATOR: Standard timeline template"

        phases = ["Discovery", "Design", "Development", "Testing", "Launch"]
        for phase, duration in zip(phases, weeks):
            proposal_data["timeline"].append(
                {"phase": phase, "duration": f'{duration} week{"s" if duration > 1 else ""}'}
            )

        # Use budget from effective requirements (includes any revisions)
        requested_budget = None
        budget_info = effective_requirements.get("budget", {})
        if budget_info.get("max_amount"):
            requested_budget = budget_info["max_amount"]
            field_sources["budget"] = f"REQUIREMENT_EXTRACTOR: ${requested_budget} from requirements.budget.max_amount"
            logger.info(f"Using budget from requirements: ${requested_budget}")
        else:
            # Fallback to scanning email history only if no budget in requirements
            for email in conversation.get("email_history", []):
                body = email.get("body", "").lower()
                if "$1k" in body or "$1,000" in body or "cost down to $1" in body:
                    requested_budget = 1000
                    field_sources["budget"] = "PDF_GENERATOR: $1000 detected in email content"
                    break
                elif "$500" in body or "cost down to $500" in body or "down to $500" in body:
                    requested_budget = 500
                    field_sources["budget"] = "PDF_GENERATOR: $500 detected in email content"
                    break
                elif "$3-4" in body or "$3-4k" in body:
                    requested_budget = 3500
                    field_sources["budget"] = "PDF_GENERATOR: $3500 detected in email content"
                    break
            
            if requested_budget is None:
                field_sources["budget"] = "PDF_GENERATOR: No budget found, using default pricing"

        # Generate realistic pricing based on project type
        if requested_budget == 500:
            # Ultra budget pricing - single line item
            pricing_items = [("Complete Dashboard Package", 500)]
            base_multiplier = 1
        elif requested_budget == 1000:
            # $1k budget pricing - simplified breakdown
            pricing_items = [
                ("Dashboard Development", 800),
                ("Setup & Deployment", 200),
            ]
            base_multiplier = 1
        elif "dashboard" in project_type.lower() and requested_budget:
            # Dashboard with specific budget
            pricing_items = [("Complete Dashboard Development", requested_budget)]
            base_multiplier = 1
        elif "dashboard" in project_type.lower():
            # Dashboard project standard pricing
            pricing_items = [
                ("Setup & Configuration", 800),
                ("Dashboard Development", 1500),
                ("Testing & Deployment", 200),
            ]
            base_multiplier = 1
        else:
            # Standard project pricing
            pricing_items = [
                ("Discovery & Research", 1000),
                ("Design & Prototyping", 2500),
                ("Development", 6000),
                ("Testing & QA", 1000),
                ("Launch Support", 500),
            ]
            base_multiplier = 1

        # Apply any budget constraints
        budget = understanding.get("budget", {})
        if budget.get("max_amount"):
            try:
                max_budget = float(budget["max_amount"])
                total_price = sum(price for _, price in pricing_items)
                if total_price > max_budget:
                    # Scale down prices to fit budget
                    base_multiplier = max_budget / total_price * 0.9  # 90% of budget
            except (ValueError, KeyError, TypeError):
                pass

        # Add pricing items
        for item, amount in pricing_items:
            final_amount = int(amount * base_multiplier)
            proposal_data["pricing"].append({"item": item, "amount": f"${final_amount:,}"})

        # Extract tech stack
        tech_mentioned = understanding.get("technical_requirements", {})
        default_stack = ["Next.js", "React", "Node.js", "PostgreSQL", "AWS"]

        # Add any specifically mentioned technologies
        if effective_requirements.get("tech_stack"):
            proposal_data["techStack"] = effective_requirements["tech_stack"][:9]  # Max 9 items
            field_sources["techStack"] = f"REQUIREMENT_EXTRACTOR: {', '.join(effective_requirements['tech_stack'])}"
        elif tech_mentioned.get("technologies"):
            proposal_data["techStack"] = tech_mentioned["technologies"][:9]  # Max 9 items
            field_sources["techStack"] = "PDF_GENERATOR: From conversation understanding"
        else:
            proposal_data["techStack"] = default_stack
            field_sources["techStack"] = "PDF_GENERATOR: Default tech stack"

        # Add comprehensive logging
        logger.info("=" * 80)
        logger.info("PDF GENERATOR - PROPOSAL DATA EXTRACTION COMPLETE")
        logger.info("=" * 80)
        logger.info("FIELD VALUES AND SOURCES:")
        logger.info(f"  clientName: '{proposal_data['clientName']}' - {field_sources['clientName']}")
        logger.info(f"  projectTitle: '{proposal_data['projectTitle']}' - {field_sources['projectTitle']}")
        logger.info(f"  proposalDate: '{proposal_data['proposalDate']}' - PDF_GENERATOR: Current month/year")
        logger.info(f"  scope: {len(proposal_data['scope'])} items - {field_sources['scope']}")
        for i, scope_item in enumerate(proposal_data['scope']):
            logger.info(f"    [{i+1}] {scope_item['title']}")
        logger.info(f"  timeline: {len(proposal_data['timeline'])} phases - {field_sources['timeline']}")
        logger.info(f"  budget: ${requested_budget if requested_budget else 'Not specified'} - {field_sources['budget']}")
        logger.info(f"  pricing: {len(proposal_data['pricing'])} items - PDF_GENERATOR: Generated based on budget/project type")
        total_price = sum(int(item['amount'].replace('$', '').replace(',', '')) for item in proposal_data['pricing'])
        logger.info(f"    Total: ${total_price:,}")
        logger.info(f"  techStack: {', '.join(proposal_data['techStack'])} - {field_sources['techStack']}")
        logger.info("=" * 80)
        logger.info("REQUIREMENTS FROM EXTRACTOR:")
        logger.info(f"  title: {effective_requirements.get('title', 'Not provided')}")
        logger.info(f"  summary: {effective_requirements.get('summary', 'Not provided')}")
        logger.info(f"  project_type: {effective_requirements.get('project_type', 'Not provided')}")
        logger.info(f"  features: {len(effective_requirements.get('features', []))} features")
        logger.info(f"  budget: {effective_requirements.get('budget', 'Not provided')}")
        logger.info(f"  timeline: {effective_requirements.get('timeline', 'Not provided')}")
        logger.info("=" * 80)

        return proposal_data

    def _get_project_description(
        self, requirements: Dict, understanding: Dict, conversation: Dict
    ) -> str:
        """Extract specific project description from conversation."""

        # Check for removed features
        # No longer using revised_requirements
        removed_features = []

        # Check for specific mentions in email content
        for email in conversation.get("email_history", []):
            body = email.get("body", "").lower()
            if "shopify" in body and "dashboard" in body and "shopify" not in removed_features:
                return "a Shopify dashboard for tracking sales and inventory"
            elif "dashboard" in body:
                return "an internal dashboard solution"
            elif "e-commerce" in body and "dashboard" in body:
                return "an e-commerce dashboard"

        # Fallback to extracted requirements
        project_type = requirements.get("project_type", understanding.get("project_type"))
        title = requirements.get("title", understanding.get("title", ""))

        if project_type == "web_app" and "dashboard" in title.lower():
            return f"a custom {title.lower()}"
        elif project_type == "web_app":
            return "a web application"
        elif project_type == "website":
            return "a website"
        elif project_type == "mobile_app":
            return "a mobile application"
        else:
            return "a web development solution"

    def generate_proposal_pdf(
        self, conversation: Dict, timeout: int = 5
    ) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Generate a proposal PDF for the current conversation.
        
        DEPRECATED: This method now uses ProposalDataMapper internally.
        Consider using generate_proposal_pdf_from_data directly.

        Args:
            conversation: Full conversation history with metadata
            timeout: Lambda invocation timeout in seconds

        Returns:
            Tuple of (pdf_bytes, error_message)
        """
        logger.warning("DEPRECATED: generate_proposal_pdf called. Consider using generate_proposal_pdf_from_data.")
        
        # Import mapper here to avoid circular imports
        from proposal_mapper import ProposalDataMapper
        
        # Extract requirements
        requirements = conversation.get("requirements", {})
        if not requirements:
            return None, "No requirements found in conversation"
        
        # Map requirements to proposal data
        mapper = ProposalDataMapper()
        proposal_data = mapper.map_requirements_to_proposal_data(requirements)
        
        # Use conversation_id for document Lambda
        conversation_id = conversation.get("conversation_id")
        if not conversation_id:
            return None, "Missing conversation_id in conversation"
        
        # Use the new method
        return self.generate_proposal_pdf_from_data(proposal_data, conversation_id, timeout)

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
        from proposal_mapper import ProposalDataMapper
        
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

            # Store in S3
            proposal_version, s3_key = self.s3_store.store_proposal(
                conversation_id=conversation_id,
                pdf_bytes=pdf_bytes,
                proposal_data=proposal_data,
                requirements=requirements,
                revised_requirements=None,  # No longer using revised_requirements
                generated_by=conversation.get("phase", "proposal_draft"),
            )

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

    def create_proposal_with_fallback(self, conversation: Dict) -> Dict:
        """
        Generate proposal with PDF attachment, with fallback to text-only.

        Args:
            conversation: Full conversation history

        Returns:
            Dict with email content and optional attachment
        """
        # Try to generate PDF
        pdf_bytes, error = self.generate_proposal_pdf(conversation)

        # Extract basic info
        client_name = conversation.get("client_name", "there")
        understanding = conversation.get("current_understanding", {})
        requirements = conversation.get("requirements", {})

        if pdf_bytes:
            # Success - create email with attachment
            email_content = f"""Hi {client_name},

I'm excited to share our project proposal with you! Please find the detailed proposal attached as a PDF.

The proposal includes:
- Complete project scope and deliverables
- Timeline with key milestones
- Transparent cost breakdown
- Our recommended technology approach

I've crafted this based on our discussion about {understanding.get('project_type', 'your project')}. The total investment comes to a competitive rate that reflects the value and quality you'll receive.

Please review the attached proposal at your convenience. I'm happy to schedule a call to discuss any questions or adjustments you might have.

Looking forward to bringing your vision to life!

Best regards,
Abdul"""

            return {
                "subject": f"Project Proposal - {understanding.get('project_type', 'Your Project')}",
                "body": email_content,
                "attachment": {
                    "filename": "project_proposal.pdf",
                    "content": pdf_bytes,
                    "content_type": "application/pdf",
                },
            }

        else:
            # Fallback - text-only proposal
            logger.warning(f"PDF generation failed, using text fallback: {error}")

            # Generate a simple text proposal
            pricing_total = sum(
                int(item.get("amount", "$0").replace("$", "").replace(",", ""))
                for item in self.extract_proposal_data(conversation).get("pricing", [])
            )

            email_content = f"""Hi {client_name},

I'm excited to share our project proposal with you!

**Project Overview**
Based on our discussion, I understand you need {self._get_project_description(requirements, understanding, conversation)}.

**Scope of Work**
1. Discovery & Planning - Understanding your exact needs
2. Design & Prototyping - Creating the perfect user experience
3. Development - Building your solution with modern technology
4. Testing & Launch - Ensuring everything works flawlessly

**Timeline**
The project will take approximately 12-16 weeks from start to finish, with regular updates throughout.

**Investment**
Total project cost: ${pricing_total:,}

This includes all development, testing, and launch support. Payment is typically split into milestones.

**Next Steps**
1. Review this proposal
2. Schedule a call to discuss any questions
3. Sign agreement to begin

I'm happy to provide a detailed PDF proposal or discuss any aspects over a call. Looking forward to working together!

Best regards,
Abdul"""

            return {
                "subject": f"Project Proposal - {understanding.get('project_type', 'Your Project')}",
                "body": email_content,
                "attachment": None,
            }
