#!/usr/bin/env python3
"""Test conversation threading with real email scenarios."""

import json
import time

import boto3

# AWS clients
lambda_client = boto3.client("lambda", region_name="us-east-2")
dynamodb = boto3.resource("dynamodb", region_name="us-east-2")
s3_client = boto3.client("s3", region_name="us-east-2")

BUCKET = "solopilot-emails"
FUNCTION_NAME = "solopilot-email-intake"
CONVERSATIONS_TABLE = "conversations"
MESSAGE_MAP_TABLE = "email_message_map"


def upload_email_to_s3(email_content: str, key: str):
    """Upload test email to S3."""
    s3_client.put_object(Bucket=BUCKET, Key=key, Body=email_content.encode("utf-8"))
    print(f"Uploaded test email to s3://{BUCKET}/{key}")


def invoke_lambda(bucket: str, key: str):
    """Invoke Lambda function with S3 event."""
    event = {"Records": [{"s3": {"bucket": {"name": bucket}, "object": {"key": key}}}]}

    response = lambda_client.invoke(
        FunctionName=FUNCTION_NAME, InvocationType="RequestResponse", Payload=json.dumps(event)
    )

    result = json.loads(response["Payload"].read())
    print(f"Lambda response: {result}")
    return result


def check_conversation_state(conversation_id: str):
    """Check conversation in DynamoDB."""
    table = dynamodb.Table(CONVERSATIONS_TABLE)
    response = table.get_item(Key={"conversation_id": conversation_id})

    if "Item" in response:
        conv = response["Item"]
        print(f"\nConversation {conversation_id}:")
        print(f"  Email count: {len(conv.get('email_history', []))}")
        print(f"  Status: {conv.get('status')}")
        print(f"  Phase: {conv.get('phase')}")
        print(f"  Reply mode: {conv.get('reply_mode', 'manual')}")
        print(f"  Pending replies: {len(conv.get('pending_replies', []))}")
        return conv
    return None


def check_message_mapping(message_id: str):
    """Check message ID mapping."""
    table = dynamodb.Table(MESSAGE_MAP_TABLE)
    response = table.get_item(Key={"message_id": message_id})

    if "Item" in response:
        print(f"  Message {message_id} -> Conversation {response['Item']['conversation_id']}")
        return response["Item"]["conversation_id"]
    return None


def test_email_thread():
    """Test a complete email thread."""
    print("=== Testing Email Thread Conversation ID Stability ===\n")

    # Email 1: Initial inquiry
    email1 = """From: test@example.com
To: intake@solopilot.abdulkhurram.com
Subject: Need help with website
Message-ID: <test-001@example.com>
Date: Sun, 20 Jul 2025 10:00:00 +0000

Hi,

I need help building a website for my business. Can you help?

Thanks,
Test User
"""

    print("1. Sending initial email...")
    key1 = f"test/thread-test-{int(time.time())}-1.eml"
    upload_email_to_s3(email1, key1)
    result1 = invoke_lambda(BUCKET, key1)

    # Extract conversation ID
    body1 = json.loads(result1["body"])
    conv_id = body1.get("conversation_id")
    print(f"   Conversation ID: {conv_id}")

    # Check message mapping
    check_message_mapping("test-001@example.com")

    # Check conversation state
    conv1 = check_conversation_state(conv_id)

    time.sleep(2)

    # Email 2: Our system's reply (simulated)
    print("\n2. Simulating system reply...")
    print("   (In real scenario, this would be sent by Lambda)")

    # Email 3: User's reply to our email
    email3 = """From: test@example.com
To: intake@solopilot.abdulkhurram.com
Subject: Re: Need help with website
Message-ID: <test-003@example.com>
In-Reply-To: <test-001@example.com>
References: <test-001@example.com>
Date: Sun, 20 Jul 2025 11:00:00 +0000

Sure! It's an e-commerce site for selling handmade crafts.

We need:
- Product catalog
- Shopping cart
- Payment processing
- Admin panel

Budget is around $5000 and we need it in 2 months.

Thanks,
Test User
"""

    print("\n3. Sending user's reply...")
    key3 = f"test/thread-test-{int(time.time())}-3.eml"
    upload_email_to_s3(email3, key3)
    result3 = invoke_lambda(BUCKET, key3)

    # Check if same conversation ID
    body3 = json.loads(result3["body"])
    conv_id_3 = body3.get("conversation_id")
    print(f"   Conversation ID: {conv_id_3}")

    if conv_id == conv_id_3:
        print("   ✅ SUCCESS: Same conversation ID maintained!")
    else:
        print(f"   ❌ FAILURE: Different conversation ID! {conv_id} != {conv_id_3}")

    # Check message mapping
    check_message_mapping("test-003@example.com")

    # Check updated conversation
    conv3 = check_conversation_state(conv_id)

    # Email 4: Another reply in thread
    email4 = """From: test@example.com
To: intake@solopilot.abdulkhurram.com
Subject: Re: Need help with website
Message-ID: <test-004@example.com>
In-Reply-To: <test-003@example.com>
References: <test-001@example.com> <test-003@example.com>
Date: Sun, 20 Jul 2025 12:00:00 +0000

Oh, I forgot to mention - we also need mobile responsive design!

Thanks,
Test User
"""

    print("\n4. Sending another reply...")
    key4 = f"test/thread-test-{int(time.time())}-4.eml"
    upload_email_to_s3(email4, key4)
    result4 = invoke_lambda(BUCKET, key4)

    body4 = json.loads(result4["body"])
    conv_id_4 = body4.get("conversation_id")
    print(f"   Conversation ID: {conv_id_4}")

    if conv_id == conv_id_4:
        print("   ✅ SUCCESS: Conversation ID still stable!")
    else:
        print(f"   ❌ FAILURE: Conversation ID changed! {conv_id} != {conv_id_4}")

    # Final conversation state
    print("\n=== Final Conversation State ===")
    final_conv = check_conversation_state(conv_id)

    # Check all message mappings
    print("\n=== Message ID Mappings ===")
    for msg_id in ["test-001@example.com", "test-003@example.com", "test-004@example.com"]:
        check_message_mapping(msg_id)

    print("\n=== Test Complete ===")


if __name__ == "__main__":
    test_email_thread()
