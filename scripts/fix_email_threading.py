#!/usr/bin/env python3
"""Fix email threading by updating Lambda to use send_raw_email with proper headers."""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.agents.email_intake.lambda_function_v2 import *

# Create the fixed version with proper email threading
FIXED_FOLLOWUP_FUNCTION = '''def _send_followup_email_v2(
    to_email: str, subject: str, questions: str, conversation_id: str, in_reply_to: str
) -> Optional[str]:
    """Send follow-up email with proper threading headers."""
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import email.utils
    
    body = f"""Thank you for your interest in our development services!

To better understand your project needs, could you please provide some additional information:

{questions}

Looking forward to your response!

Best regards,
The SoloPilot Team

--
Conversation ID: {conversation_id}
"""

    try:
        # Create MIME message with proper headers
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email
        msg["Subject"] = f"Re: {subject}"
        msg["Message-ID"] = email.utils.make_msgid(domain="solopilot.abdulkhurram.com")
        msg["In-Reply-To"] = f"<{in_reply_to}>"
        msg["References"] = f"<{in_reply_to}>"
        msg["Reply-To"] = SENDER_EMAIL
        
        # Add body
        msg.attach(MIMEText(body, "plain"))
        
        # Send raw email
        response = ses_client.send_raw_email(
            Source=SENDER_EMAIL,
            Destinations=[to_email],
            RawMessage={"Data": msg.as_string()},
            Tags=[
                {"Name": "conversation_id", "Value": conversation_id},
                {"Name": "email_type", "Value": "followup"},
            ],
        )

        return response.get("MessageId")

    except Exception as e:
        logger.error(f"Error sending follow-up email: {str(e)}")
        return None'''

FIXED_CONFIRMATION_FUNCTION = '''def _send_confirmation_email_v2(
    to_email: str, requirements: Dict[str, Any], conversation_id: str
) -> Optional[str]:
    """Send confirmation email with scope summary and threading headers."""
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    import email.utils
    
    features = "\\n".join(
        [f"- {f['name']}: {f['desc']}" for f in requirements.get("features", [])]
    )

    body = f"""Thank you for providing all the information!

Here's what we understand about your project:

**Project:** {requirements.get('title', 'Your Project')}
**Type:** {requirements.get('project_type', 'N/A')}
**Timeline:** {requirements.get('timeline', 'To be discussed')}
**Budget:** {requirements.get('budget', 'To be discussed')}

**Key Features:**
{features}

We'll begin working on your project plan and development roadmap. You'll receive our detailed proposal within 24 hours.

Best regards,
The SoloPilot Team

--
Conversation ID: {conversation_id}
"""

    try:
        # Create MIME message with proper headers
        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email
        msg["Subject"] = "Project Scope Confirmed - SoloPilot"
        msg["Message-ID"] = email.utils.make_msgid(domain="solopilot.abdulkhurram.com")
        # Note: No In-Reply-To for confirmation as it starts a new thread
        msg["Reply-To"] = SENDER_EMAIL
        
        # Add body
        msg.attach(MIMEText(body, "plain"))
        
        # Send raw email
        response = ses_client.send_raw_email(
            Source=SENDER_EMAIL,
            Destinations=[to_email],
            RawMessage={"Data": msg.as_string()},
            Tags=[
                {"Name": "conversation_id", "Value": conversation_id},
                {"Name": "email_type", "Value": "confirmation"},
            ],
        )

        return response.get("MessageId")

    except Exception as e:
        logger.error(f"Error sending confirmation email: {str(e)}")
        return None'''

print("Email Threading Fix")
print("==================")
print("\nThis fix updates the Lambda to use send_raw_email with proper email headers.")
print("\nThe fix includes:")
print("1. In-Reply-To header for email threading")
print("2. References header for email chain")
print("3. Message-ID with proper domain")
print("4. MIME message structure")
print("\nTo apply this fix:")
print("1. Update lambda_function_v2.py with the new functions")
print("2. Rebuild the Lambda package")
print("3. Upload to AWS Lambda")
print("\nNew functions to add:")
print(FIXED_FOLLOWUP_FUNCTION)
print("\n" + "=" * 60 + "\n")
print(FIXED_CONFIRMATION_FUNCTION)
