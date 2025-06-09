# SoloPilot Development Makefile
# Provides convenient commands for common development tasks

.PHONY: help venv install run test demo plan analyze-and-plan dev plan-dev dev-scout lint clean docker docker-down

# Default target
help:
	@echo "SoloPilot Development Commands:"
	@echo ""
	@echo "Setup Commands:"
	@echo "  make venv       Create virtual environment and install dependencies"
	@echo "  make install    Install dependencies in existing venv"
	@echo ""
	@echo "Development Commands:"
	@echo "  make run        Run analyser with sample input"
	@echo "  make plan       Run planner with latest specification"
	@echo "  make analyze-and-plan  Run full analyser → planner workflow"
	@echo "  make dev        Run dev agent with latest planning output"
	@echo "  make plan-dev   Run analyser → planner → dev agent (end-to-end)"
	@echo "  make dev-scout  Run dev agent with Context7 scouting enabled"
	@echo "  make test       Run test suite"
	@echo "  make lint       Run code linting and formatting"
	@echo "  make demo       Run demo script with sample data"
	@echo ""
	@echo "Docker Commands:"
	@echo "  make docker     Start services with docker-compose"
	@echo "  make docker-down Stop docker services"
	@echo ""
	@echo "Utility Commands:"
	@echo "  make clean      Clean build artifacts and cache"
	@echo "  make help       Show this help message"

# Create virtual environment and install all dependencies
venv:
	@echo "🔧 Creating virtual environment..."
	python3 -m venv .venv
	@echo "📦 Installing dependencies..."
	. .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt
	@echo "✅ Virtual environment ready! Run 'source .venv/bin/activate' to activate."

# Install dependencies in existing virtual environment
install:
	@echo "📦 Installing dependencies..."
	@if [ ! -d ".venv" ]; then echo "❌ Virtual environment not found. Run 'make venv' first."; exit 1; fi
	. .venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt
	@echo "✅ Dependencies installed!"

# Run analyser with sample input
run:
	@echo "🚀 Running SoloPilot analyser..."
	@if [ ! -d ".venv" ]; then echo "❌ Virtual environment not found. Run 'make venv' first."; exit 1; fi
	. .venv/bin/activate && python scripts/run_analyser.py --path sample_input

# Run test suite
test:
	@echo "🧪 Running tests..."
	@if [ ! -d ".venv" ]; then echo "❌ Virtual environment not found. Run 'make venv' first."; exit 1; fi
	. .venv/bin/activate && pytest tests/ -v

# Run code linting and formatting
lint:
	@echo "🧹 Running code linting and formatting..."
	@if [ ! -d ".venv" ]; then echo "❌ Virtual environment not found. Run 'make venv' first."; exit 1; fi
	. .venv/bin/activate && \
	echo "Running ruff..." && \
	(ruff check . --fix || echo "Ruff check completed") && \
	echo "Running black..." && \
	(black . --line-length=100 || echo "Black formatting completed") && \
	echo "Running isort..." && \
	(isort . --profile=black --line-length=100 || echo "isort completed") && \
	echo "✅ Linting complete!"

# Run demo script
demo:
	@echo "🎬 Running demo..."
	@chmod +x scripts/demo.sh
	./scripts/demo.sh

# Run planner with latest specification
plan:
	@echo "🔧 Running project planner..."
	@if [ ! -d ".venv" ]; then echo "❌ Virtual environment not found. Run 'make venv' first."; exit 1; fi
	. .venv/bin/activate && python scripts/run_planner.py --latest

# Run full analyser → planner workflow
analyze-and-plan:
	@echo "🚀 Running full analyser → planner workflow..."
	@if [ ! -d ".venv" ]; then echo "❌ Virtual environment not found. Run 'make venv' first."; exit 1; fi
	@echo "Step 1: Running analyser..."
	. .venv/bin/activate && python scripts/run_analyser.py --path sample_input
	@echo "Step 2: Running planner..."
	. .venv/bin/activate && python scripts/run_planner.py --latest

# Start docker services
docker:
	@echo "🐳 Starting Docker services..."
	docker-compose up --build

# Stop docker services
docker-down:
	@echo "🛑 Stopping Docker services..."
	docker-compose down

# Clean build artifacts and cache
clean:
	@echo "🧹 Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	rm -rf .pytest_cache 2>/dev/null || true
	@echo "✅ Cleanup complete!"

# Run dev agent with latest planning output
dev:
	@echo "⚙️ Running dev agent with latest planning output..."
	@if [ ! -d ".venv" ]; then echo "❌ Virtual environment not found. Run 'make venv' first."; exit 1; fi
	. .venv/bin/activate && python scripts/check_bedrock.py && python scripts/run_dev_agent.py

# Run full analyser → planner → dev agent workflow
plan-dev:
	@echo "🚀 Running full analyser → planner → dev agent workflow..."
	@if [ ! -d ".venv" ]; then echo "❌ Virtual environment not found. Run 'make venv' first."; exit 1; fi
	@echo "Step 1: Running analyser..."
	. .venv/bin/activate && python scripts/run_analyser.py --path sample_input
	@echo "Step 2: Running planner..."
	. .venv/bin/activate && python scripts/run_planner.py --latest
	@echo "Step 3: Running dev agent..."
	. .venv/bin/activate && python scripts/check_bedrock.py && python scripts/run_dev_agent.py

# Run dev agent with Context7 scouting enabled
dev-scout:
	@echo "🔍 Running dev agent with Context7 scouting enabled..."
	@if [ ! -d ".venv" ]; then echo "❌ Virtual environment not found. Run 'make venv' first."; exit 1; fi
	@if ! command -v context7 >/dev/null 2>&1; then \
		echo "⚠️  Context7 not found. Installing globally..."; \
		npm install -g context7; \
	fi
	. .venv/bin/activate && python scripts/check_bedrock.py && C7_SCOUT=1 python scripts/run_dev_agent.py

# Quick development setup (venv + dependencies + tesseract check)
setup: venv
	@echo "🔍 Checking system dependencies..."
	@if ! command -v tesseract >/dev/null 2>&1; then \
		echo "⚠️  Tesseract not found. Install with: brew install tesseract"; \
	else \
		echo "✅ Tesseract found"; \
	fi
	@echo "🎉 Setup complete! Run 'source .venv/bin/activate' then 'make run' to test."