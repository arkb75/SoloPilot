#!/bin/bash
# SoloPilot Demo Script
# Demonstrates end-to-end requirement analysis workflow

set -e  # Exit on any error

echo "🚀 SoloPilot Requirement Analyser Demo"
echo "======================================"

# Check if we're in the right directory
if [ ! -f "requirements.txt" ]; then
    echo "❌ Please run this script from the SoloPilot root directory"
    exit 1
fi

# Create sample input if it doesn't exist
if [ ! -d "sample_input" ]; then
    mkdir -p sample_input
fi

# Create demo requirements file
cat > sample_input/project_brief.md << 'EOF'
# E-Commerce Platform Requirements

## Project Overview
We need to build a modern e-commerce platform that allows customers to browse products, add items to cart, and complete purchases securely.

## Core Features

### User Management
- User registration and authentication
- Customer profiles with order history
- Admin accounts for store management

### Product Catalog
- Product listings with search and filtering
- Category-based navigation
- Product detail pages with images and descriptions
- Inventory management

### Shopping Experience
- Shopping cart functionality
- Wishlist/favorites
- Product reviews and ratings
- Promotional codes and discounts

### Payment & Orders
- Secure checkout process
- Multiple payment methods (credit card, PayPal)
- Order tracking and status updates
- Email confirmations

### Administration
- Admin dashboard for store management
- Product and inventory management
- Order processing and fulfillment
- Customer service tools

## Technical Requirements
- React frontend with TypeScript
- Node.js backend with Express
- PostgreSQL database
- Redis for session management
- Payment integration with Stripe
- AWS S3 for image storage
- Mobile-responsive design

## Constraints
- Must support 1000+ concurrent users
- 99.9% uptime requirement
- GDPR compliance for EU customers
- PCI DSS compliance for payments
- Mobile-first design approach

## Timeline
8-10 weeks development timeline with these phases:
1. Phase 1: User auth and basic product catalog (2 weeks)
2. Phase 2: Shopping cart and checkout (3 weeks)
3. Phase 3: Admin panel and advanced features (3 weeks)
4. Phase 4: Testing and deployment (2 weeks)

## Budget
$75,000 - $100,000 development budget
EOF

echo "✅ Created sample project brief"

# Create sample text requirements
cat > sample_input/additional_requirements.txt << 'EOF'
Additional Requirements:

Performance Requirements:
- Page load times under 2 seconds
- Support for 10,000 products minimum
- Image optimization and lazy loading
- CDN integration for global performance

Security Requirements:
- Two-factor authentication for admin accounts
- Rate limiting for API endpoints
- SQL injection protection
- XSS and CSRF protection
- Regular security audits

Integration Requirements:
- Google Analytics for tracking
- Mailchimp for email marketing
- Zendesk for customer support
- Social media login (Google, Facebook)
- Inventory sync with existing warehouse system
EOF

echo "✅ Created additional requirements file"

# Setup virtual environment and dependencies
echo "🔍 Setting up Python environment..."

# Create venv if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source .venv/bin/activate

# Check if dependencies are installed in venv
if ! python -c "import agents.analyser" 2>/dev/null; then
    echo "📦 Installing Python dependencies in virtual environment..."
    
    # Check if tesseract is installed (required for OCR)
    if ! command -v tesseract &> /dev/null; then
        echo "⚠️  Tesseract OCR not found. Installing via Homebrew..."
        if command -v brew &> /dev/null; then
            brew install tesseract
        else
            echo "❌ Homebrew not found. Please install tesseract manually:"
            echo "   brew install tesseract"
            echo "   or visit: https://github.com/tesseract-ocr/tesseract"
            exit 1
        fi
    fi
    
    # Install Python packages in venv
    pip install --upgrade pip
    pip install -r requirements.txt
    
    # If FAISS installation failed on macOS, suggest alternatives
    if ! python -c "import faiss" 2>/dev/null && ! python -c "import sklearn" 2>/dev/null; then
        echo "⚠️  Vector similarity search library not available."
        echo "   Installing scikit-learn as fallback..."
        pip install scikit-learn==1.5.2
    fi
else
    echo "✅ Dependencies already installed in virtual environment"
fi

# Run the analyser
echo "🔧 Running requirement analysis..."
python scripts/run_analyser.py --path sample_input --config config/model_config.yaml

# Check if analysis was successful
if [ -d "analysis/output" ]; then
    LATEST_DIR=$(ls -t analysis/output | head -n1)
    if [ -n "$LATEST_DIR" ]; then
        echo ""
        echo "✅ Analysis completed successfully!"
        echo "📊 Results saved to: analysis/output/$LATEST_DIR"
        echo ""
        echo "📋 Generated files:"
        ls -la "analysis/output/$LATEST_DIR/"
        echo ""
        echo "🎯 Specification preview:"
        echo "========================"
        if [ -f "analysis/output/$LATEST_DIR/specification.json" ]; then
            python -c "
import json
with open('analysis/output/$LATEST_DIR/specification.json') as f:
    spec = json.load(f)
print(f'Title: {spec[\"title\"]}')
print(f'Features: {len(spec[\"features\"])} identified')
print(f'Constraints: {len(spec[\"constraints\"])} listed')
print(f'Assets: {len(spec[\"assets\"][\"docs\"])} documents processed')
"
        fi
        echo ""
        echo "🎨 Generated artifacts:"
        if [ -f "analysis/output/$LATEST_DIR/component_diagram.md" ]; then
            echo "   ✓ Component diagram"
        fi
        if [ -f "analysis/output/$LATEST_DIR/task_flow.md" ]; then
            echo "   ✓ Task flow diagram"
        fi
        if [ -f "analysis/output/$LATEST_DIR/wireframe.md" ]; then
            echo "   ✓ UI wireframe"
        fi
        echo ""
        echo "🎉 Demo completed! Check the output directory for detailed results."
        echo "🔗 Next: Use this specification with the Planning Agent"
    else
        echo "❌ No output directory found"
        exit 1
    fi
else
    echo "❌ Analysis failed - no output directory created"
    exit 1
fi