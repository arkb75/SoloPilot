"""Adapter for integrating simulator with email intake Lambda."""

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


@dataclass
class SystemResponse:
    """Represents a response from the email intake system."""

    conversation_id: str
    phase: str
    response_body: str
    subject: str
    requirements: Dict[str, Any]
    pending_reply: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class IntakeAdapter:
    """Bridges simulator to email intake Lambda and DynamoDB."""

    def __init__(
        self,
        aws_profile: str = "root",
        aws_region: str = "us-east-2",
        lambda_function: str = "email-agent-api",
        dynamodb_table: str = "conversations",
    ):
        """Initialize adapter with AWS clients.
        
        Args:
            aws_profile: AWS profile to use
            aws_region: AWS region
            lambda_function: Name of the API Lambda function
            dynamodb_table: Name of the DynamoDB conversations table
        """
        self.aws_profile = aws_profile
        self.aws_region = aws_region
        self.lambda_function = lambda_function
        self.dynamodb_table = dynamodb_table
        
        # Initialize AWS clients with profile
        session = boto3.Session(profile_name=aws_profile, region_name=aws_region)
        self.lambda_client = session.client("lambda")
        self.dynamodb = session.resource("dynamodb")
        self.table = self.dynamodb.Table(dynamodb_table)

    def create_conversation(
        self,
        client_email: str,
        subject: str,
        body: str,
    ) -> SystemResponse:
        """Create a new conversation by simulating an incoming email.
        
        This directly creates the conversation in DynamoDB and triggers
        the conversational responder, bypassing actual SES email flow.
        
        Args:
            client_email: Email address of the simulated client
            subject: Email subject
            body: Email body content
        
        Returns:
            SystemResponse with the system's reply
        """
        import uuid
        from datetime import datetime, timezone
        
        # Generate conversation ID
        conversation_id = f"sim_{uuid.uuid4().hex[:12]}"
        
        # Create the conversation record directly
        conversation_data = {
            "conversation_id": conversation_id,
            "status": "active",
            "phase": "understanding",
            "reply_mode": "manual",  # Use manual mode for simulation inspection
            "subject": subject,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "participants": [client_email, "hello@solopilot.ai"],
            "email_history": [
                {
                    "email_id": f"{conversation_id}-001",
                    "from": client_email,
                    "to": "hello@solopilot.ai",
                    "subject": subject,
                    "body": body,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "direction": "inbound",
                }
            ],
            "requirements": {},
            "thread_references": [],
            "pending_replies": [],
            "attachments": [],
            "simulation": True,  # Mark as simulation
        }
        
        try:
            # Create conversation in DynamoDB
            self.table.put_item(Item=conversation_data)
            logger.info(f"Created simulation conversation: {conversation_id}")
            
            # Invoke the API Lambda to process the email and generate response
            response = self._invoke_process_email(conversation_id, client_email, subject, body)
            
            return response
            
        except ClientError as e:
            logger.error(f"Failed to create conversation: {e}")
            return SystemResponse(
                conversation_id=conversation_id,
                phase="error",
                response_body="",
                subject=subject,
                requirements={},
                error=str(e),
            )

    def send_reply(
        self,
        conversation_id: str,
        client_email: str,
        body: str,
    ) -> SystemResponse:
        """Send a client reply to an existing conversation.
        
        Args:
            conversation_id: Existing conversation ID
            client_email: Client email address
            body: Reply body content
        
        Returns:
            SystemResponse with the system's reply
        """
        from datetime import datetime, timezone
        
        try:
            # Get current conversation state
            conversation = self.get_conversation_state(conversation_id)
            if not conversation:
                return SystemResponse(
                    conversation_id=conversation_id,
                    phase="error",
                    response_body="",
                    subject="",
                    requirements={},
                    error="Conversation not found",
                )
            
            # Append client reply to email history
            email_count = len(conversation.get("email_history", []))
            new_email = {
                "email_id": f"{conversation_id}-{email_count + 1:03d}",
                "from": client_email,
                "to": "hello@solopilot.ai",
                "subject": f"Re: {conversation.get('subject', 'Project')}",
                "body": body,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "direction": "inbound",
            }
            
            # Update DynamoDB
            self.table.update_item(
                Key={"conversation_id": conversation_id},
                UpdateExpression="SET email_history = list_append(email_history, :email), updated_at = :now",
                ExpressionAttributeValues={
                    ":email": [new_email],
                    ":now": datetime.now(timezone.utc).isoformat(),
                },
            )
            
            # Generate system response
            response = self._invoke_process_email(
                conversation_id,
                client_email,
                conversation.get("subject", "Project"),
                body,
            )
            
            return response
            
        except ClientError as e:
            logger.error(f"Failed to send reply: {e}")
            return SystemResponse(
                conversation_id=conversation_id,
                phase="error",
                response_body="",
                subject="",
                requirements={},
                error=str(e),
            )

    def get_conversation_state(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Fetch current conversation state from DynamoDB.
        
        Args:
            conversation_id: Conversation ID
        
        Returns:
            Conversation state dict or None if not found
        """
        try:
            response = self.table.get_item(Key={"conversation_id": conversation_id})
            return response.get("Item")
        except ClientError as e:
            logger.error(f"Failed to get conversation: {e}")
            return None

    def get_pending_reply(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get the pending reply for a conversation.
        
        Args:
            conversation_id: Conversation ID
        
        Returns:
            Pending reply dict or None
        """
        conversation = self.get_conversation_state(conversation_id)
        if not conversation:
            return None
        
        pending = conversation.get("pending_replies", [])
        # Return the most recent pending reply
        for reply in reversed(pending):
            if reply.get("status") == "pending":
                return reply
        
        return None

    def approve_reply(self, conversation_id: str, reply_id: str) -> bool:
        """Approve a pending reply (for testing the full flow).
        
        Args:
            conversation_id: Conversation ID
            reply_id: Reply ID to approve
        
        Returns:
            True if approval succeeded
        """
        try:
            # Call the approve endpoint via Lambda
            payload = {
                "httpMethod": "POST",
                "resource": "/replies/{reply_id}/approve",
                "pathParameters": {"reply_id": reply_id},
                "body": json.dumps({
                    "conversation_id": conversation_id,
                    "reviewed_by": "simulation",
                }),
            }
            
            response = self.lambda_client.invoke(
                FunctionName=self.lambda_function,
                InvocationType="RequestResponse",
                Payload=json.dumps(payload),
            )
            
            result = json.loads(response["Payload"].read())
            return result.get("statusCode") == 200
            
        except Exception as e:
            logger.error(f"Failed to approve reply: {e}")
            return False

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a simulation conversation (cleanup).
        
        Args:
            conversation_id: Conversation ID to delete
        
        Returns:
            True if deletion succeeded
        """
        try:
            self.table.delete_item(Key={"conversation_id": conversation_id})
            logger.info(f"Deleted simulation conversation: {conversation_id}")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete conversation: {e}")
            return False

    def _invoke_process_email(
        self,
        conversation_id: str,
        client_email: str,
        subject: str,
        body: str,
    ) -> SystemResponse:
        """Process email by calling ConversationalResponder directly.
        
        This generates an AI response and stores it as a pending reply, bypassing
        the Lambda API which only handles frontend management operations.
        """
        import sys
        import os
        from pathlib import Path
        
        # Add project root to path for imports
        project_root = Path(__file__).parent.parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        
        # Set required environment variables for the responder
        # These would normally be set in the Lambda environment
        # Use the inference profile ID format that works with boto3 invoke_model
        os.environ.setdefault("BEDROCK_IP_ARN", "us.anthropic.claude-sonnet-4-5-20250929-v1:0")
        os.environ.setdefault("AWS_REGION", self.aws_region)
        os.environ.setdefault("USE_AI_PROVIDER", "false")  # Use Bedrock directly
        os.environ.setdefault("CONVERSATIONS_TABLE", self.dynamodb_table)
        
        try:
            # Force direct Bedrock mode in the modules by patching before import
            # This avoids the provider factory which has ARN validation issues
            import src.agents.email_intake.metadata_extractor as me_module
            import src.agents.email_intake.conversational_responder as cr_module
            me_module.USE_AI_PROVIDER = False
            cr_module.USE_AI_PROVIDER = False
            
            # Inject boto3 into modules (they conditionally import it)
            cr_module.boto3 = boto3
            
            # Create a Bedrock client with the correct AWS profile
            session = boto3.Session(profile_name=self.aws_profile, region_name=self.aws_region)
            profile_bedrock_client = session.client("bedrock-runtime")
            
            # Initialize Bedrock client directly in the modules with correct profile
            me_module.bedrock_client = profile_bedrock_client
            
            # Now import the responder
            from src.agents.email_intake.conversational_responder import ConversationalResponder
            from src.agents.email_intake.conversation_state import ConversationStateManager
            
            # Get the current conversation state
            conversation = self.get_conversation_state(conversation_id)
            if not conversation:
                return SystemResponse(
                    conversation_id=conversation_id,
                    phase="error",
                    response_body="",
                    subject=subject,
                    requirements={},
                    error="Conversation not found",
                )
            
            # Get the latest email from history
            email_history = conversation.get("email_history", [])
            latest_email = email_history[-1] if email_history else {
                "from": client_email,
                "subject": subject,
                "body": body,
            }
            
            # Initialize responder and state manager
            responder = ConversationalResponder()
            state_manager = ConversationStateManager(table_name=self.dynamodb_table)
            
            # Patch responder's bedrock client to use the correct profile
            # (it creates its own client without profile in __init__)
            responder.bedrock_client = profile_bedrock_client
            
            # Generate response - returns tuple (response_body, metadata, prompt)
            logger.info(f"Generating response for conversation {conversation_id}")
            response_body, response_metadata, used_prompt = responder.generate_response_with_tracking(
                conversation=conversation,
                latest_email=latest_email,
            )
            
            # Add pending reply to conversation
            from datetime import datetime, timezone
            import uuid
            
            reply_id = f"reply_{uuid.uuid4().hex[:8]}"
            pending_reply = {
                "reply_id": reply_id,
                "status": "pending",
                "llm_response": response_body,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "phase": conversation.get("phase", "understanding"),
                "metadata": {
                    "email_body": response_body,
                    "subject": f"Re: {subject}",
                    "recipient": client_email,
                },
            }
            
            # Update conversation with pending reply and new phase
            new_phase = response_metadata.get("stage", conversation.get("phase", "understanding"))
            self.table.update_item(
                Key={"conversation_id": conversation_id},
                UpdateExpression="SET pending_replies = list_append(if_not_exists(pending_replies, :empty), :reply), phase = :phase, updated_at = :now",
                ExpressionAttributeValues={
                    ":reply": [pending_reply],
                    ":empty": [],
                    ":phase": new_phase,
                    ":now": datetime.now(timezone.utc).isoformat(),
                },
            )
            
            logger.info(f"Generated response for {conversation_id}, phase: {new_phase}")
            
            return SystemResponse(
                conversation_id=conversation_id,
                phase=new_phase,
                response_body=response_body,
                subject=f"Re: {subject}",
                requirements=response_metadata.get("requirements", {}),
                pending_reply=pending_reply,
            )
            
        except Exception as e:
            logger.error(f"Failed to generate response: {e}", exc_info=True)
            return SystemResponse(
                conversation_id=conversation_id,
                phase="error",
                response_body="",
                subject=subject,
                requirements={},
                error=f"Intake error: {str(e)}",
            )
