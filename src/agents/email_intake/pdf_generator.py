"""
PDF Generation Integration for Email Intake Agent

This module handles the integration between the email intake agent and the
document generation Lambda for creating proposal PDFs.
"""

import base64
import json
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple

import boto3

logger = logging.getLogger()

# Initialize Lambda client
lambda_client = boto3.client("lambda")


class ProposalPDFGenerator:
    """Handles proposal PDF generation for the email intake agent."""

    def __init__(self, pdf_lambda_arn: str):
        """
        Initialize the PDF generator.

        Args:
            pdf_lambda_arn: ARN of the document generation Lambda
        """
        self.pdf_lambda_arn = pdf_lambda_arn

    def extract_proposal_data(self, conversation: Dict) -> Dict:
        """
        Extract relevant data from the conversation for the proposal.

        Args:
            conversation: Full conversation history with metadata

        Returns:
            Dict with extracted proposal data
        """
        # Get client info from conversation
        client_email = conversation.get("client_email", "")

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

                    # Look for name-like patterns (1-3 words, starts with capital)
                    words = line.split()
                    if 1 <= len(words) <= 3 and words[0][0].isupper():
                        # Prefer lines that look like names over titles
                        if not any(
                            title in line.lower()
                            for title in ["ceo", "cto", "manager", "director", "president"]
                        ):
                            client_name = line.split("(")[0].strip()
                            break
                        else:
                            signature_candidates.append(line)

                # Fallback to title lines if no pure name found
                if client_name == "Client" and signature_candidates:
                    client_name = signature_candidates[-1].split("(")[0].strip()

        # Extract project details from understanding
        understanding = conversation.get("current_understanding", {})

        # Extract project type from email content
        project_type = "Web Development Project"
        if conversation.get("email_history"):
            for email in conversation["email_history"]:
                if "dashboard" in email.get("body", "").lower():
                    project_type = "Internal Dashboard"
                    break
                elif "shopify" in email.get("body", "").lower():
                    project_type = "Shopify Dashboard"
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

        # Extract scope from email content for dashboard projects
        if "dashboard" in project_type.lower():
            # Parse dashboard requirements from email
            for email in conversation.get("email_history", []):
                body = email.get("body", "").lower()
                if "shopify" in body and "dashboard" in body:
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
                    break
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

        # Generate timeline based on project complexity
        timeline_complexity = understanding.get("timeline", {})
        if timeline_complexity.get("urgency") == "high":
            weeks = [1, 2, 4, 1, 1]  # Faster timeline
        else:
            weeks = [2, 3, 8, 2, 1]  # Standard timeline

        phases = ["Discovery", "Design", "Development", "Testing", "Launch"]
        for phase, duration in zip(phases, weeks):
            proposal_data["timeline"].append(
                {"phase": phase, "duration": f'{duration} week{"s" if duration > 1 else ""}'}
            )

        # Check if user requested specific budget
        requested_budget = None
        for email in conversation.get("email_history", []):
            body = email.get("body", "").lower()
            if "$500" in body or "cost down to $500" in body or "down to $500" in body:
                requested_budget = 500
                break
            elif "$3-4" in body or "$3-4k" in body:
                requested_budget = 3500
                break

        # Generate realistic pricing based on project type
        if requested_budget == 500:
            # Ultra budget pricing - single line item
            pricing_items = [("Complete Dashboard Package", 500)]
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
            except:
                pass

        # Add pricing items
        for item, amount in pricing_items:
            final_amount = int(amount * base_multiplier)
            proposal_data["pricing"].append({"item": item, "amount": f"${final_amount:,}"})

        # Extract tech stack
        tech_mentioned = understanding.get("technical_requirements", {})
        default_stack = ["Next.js", "React", "Node.js", "PostgreSQL", "AWS"]

        # Add any specifically mentioned technologies
        if tech_mentioned.get("technologies"):
            proposal_data["techStack"] = tech_mentioned["technologies"][:9]  # Max 9 items
        else:
            proposal_data["techStack"] = default_stack

        return proposal_data

    def _get_project_description(
        self, requirements: Dict, understanding: Dict, conversation: Dict
    ) -> str:
        """Extract specific project description from conversation."""

        # Check for specific mentions in email content
        for email in conversation.get("email_history", []):
            body = email.get("body", "").lower()
            if "shopify" in body and "dashboard" in body:
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

        Args:
            conversation: Full conversation history with metadata
            timeout: Lambda invocation timeout in seconds

        Returns:
            Tuple of (pdf_bytes, error_message)
        """
        try:
            # Extract proposal data from conversation
            proposal_data = self.extract_proposal_data(conversation)

            # Prepare the payload for the PDF Lambda
            # Extract clientId from email (required by document Lambda)
            client_id = (
                conversation.get("client_email", "unknown-client")
                .split("@")[0]
                .replace(".", "-")
                .replace("_", "-")
            )

            payload = {
                "template": "glassmorphic-proposal",
                "data": proposal_data,
                "clientId": client_id,
                "docType": "proposal",
                "filename": "project-proposal.pdf",
            }

            logger.info(
                f"Generating proposal PDF for {proposal_data['clientName']} with clientId: {client_id}"
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
                            document_url = body_json.get("documentUrl")
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
