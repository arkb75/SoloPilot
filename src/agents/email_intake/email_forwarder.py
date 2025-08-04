"""
Email forwarder Lambda function for SES.
Forwards emails from rafay@abdulkhurram.com to rafaykhurram@live.com
"""
import os
import boto3
import logging
from email import message_from_bytes
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ses_client = boto3.client('ses', region_name='us-east-2')
s3_client = boto3.client('s3')

# Configuration
FORWARD_FROM = os.environ.get('FORWARD_FROM', 'noreply@abdulkhurram.com')
FORWARD_TO = os.environ.get('FORWARD_TO', 'rafaykhurram@live.com')
EMAIL_BUCKET = os.environ.get('EMAIL_BUCKET', 'solopilot-emails')


def lambda_handler(event, context):
    """
    Process incoming email from SES and forward it.
    """
    try:
        # Extract info from event
        record = event['Records'][0]
        
        # Handle SES event (when Lambda is triggered directly by SES)
        if "ses" in record:
            mail = record['ses']['mail']
            message_id = mail['messageId']
            bucket = EMAIL_BUCKET
            obj_key = message_id
            logger.info(f"Processing SES event with message ID: {message_id}")
            logger.info(f"Recipients: {mail.get('destination', [])}")
        # Handle S3 event (when Lambda is triggered by S3)
        elif "s3" in record:
            bucket = record["s3"]["bucket"]["name"]
            obj_key = record["s3"]["object"]["key"]
            message_id = obj_key
            logger.info(f"Processing S3 event from: {bucket}/{obj_key}")
        else:
            raise ValueError("Unknown event type - neither SES nor S3 event")
        
        # Download email from S3
        obj = s3_client.get_object(Bucket=bucket, Key=obj_key)
        raw_email = obj['Body'].read()
        
        # Parse email
        msg = message_from_bytes(raw_email)
        
        # Log original sender
        original_from = msg.get('From', 'Unknown')
        original_subject = msg.get('Subject', 'No Subject')
        logger.info(f"Forwarding email from {original_from}: {original_subject}")
        
        # Forward the email using the original raw content
        # This preserves all attachments and formatting
        response = ses_client.send_raw_email(
            Source=FORWARD_FROM,  # Envelope sender (for SPF)
            Destinations=[FORWARD_TO],
            RawMessage={
                'Data': raw_email
            }
        )
        
        logger.info(f"Email forwarded successfully. MessageId: {response['MessageId']}")
        
        return {
            'statusCode': 200,
            'body': f'Email forwarded to {FORWARD_TO}'
        }
        
    except Exception as e:
        logger.error(f"Error forwarding email: {str(e)}", exc_info=True)
        # Don't raise - we don't want to retry failed forwards
        return {
            'statusCode': 500,
            'body': f'Error: {str(e)}'
        }