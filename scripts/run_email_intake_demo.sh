#!/bin/bash
# Quick demo runner for email intake setup

set -e  # Exit on error

echo "🚀 SoloPilot Email Intake Demo Runner"
echo "===================================="

# Set region
export AWS_DEFAULT_REGION=us-east-2
echo "✅ Setting AWS region to: $AWS_DEFAULT_REGION"

# Step 1: Add IAM permissions
echo ""
echo "Step 1: Adding temporary IAM permissions..."
python scripts/add_demo_iam_permissions.py

# Step 2: Run setup
echo ""
echo "Step 2: Setting up email intake infrastructure..."
python scripts/setup_email_intake_demo.py

# Step 3: Show test options
echo ""
echo "Step 3: Ready to test!"
echo ""
echo "Test commands:"
echo "  # List recent conversations:"
echo "  python scripts/test_email_flow.py --list"
echo ""
echo "  # Send a basic test email:"
echo "  python scripts/test_email_flow.py --scenario basic"
echo ""
echo "  # Send detailed requirements:"
echo "  python scripts/test_email_flow.py --scenario detailed"
echo ""
echo "To remove permissions after demo:"
echo "  python scripts/add_demo_iam_permissions.py --remove"
echo ""
echo "✅ Demo setup complete!"
