# SoloPilot Development Makefile
# Provides convenient commands for common development tasks

.PHONY: help venv install run test demo plan analyze-and-plan dev plan-dev dev-scout lint clean docker docker-down test-bedrock test-bedrock-cli index review promote announce validate benchmark

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
	@echo "  make dev-serena Run dev agent with Serena LSP context engine"
	@echo "  make setup-serena Install and configure Serena LSP integration"
	@echo "  make index      Build/update Chroma vector store for context engine"
	@echo "  make test       Run test suite"
	@echo "  make test-bedrock    Run comprehensive Bedrock API tests"
	@echo "  make test-bedrock-cli Run AWS CLI Bedrock ping test"
	@echo "  make lint       Run code linting and formatting"
	@echo "  make demo       Run demo script with sample data"
	@echo "  make review     Run AI code review on latest milestone"
	@echo "  make promote    Run review and promote to staging if passing"
	@echo "  make announce   Generate marketing announcement for milestone"
	@echo "  make validate   Run complex project validation with real providers"
	@echo "  make benchmark  Run performance benchmark suite"
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

# Build/update Chroma vector store for context engine
index:
	@echo "🗂️  Building/updating context engine vector store..."
	@if [ ! -d ".venv" ]; then echo "❌ Virtual environment not found. Run 'make venv' first."; exit 1; fi
	. .venv/bin/activate && python scripts/build_index.py

# Run dev agent with latest planning output
dev:
	@echo "⚙️ Running dev agent with latest planning output..."
	@if [ ! -d ".venv" ]; then echo "❌ Virtual environment not found. Run 'make venv' first."; exit 1; fi
	@# Auto-index if using lc_chroma engine and index is missing/outdated
	@if [ "$$CONTEXT_ENGINE" = "lc_chroma" ] && [ ! -f "./vector_store/chroma.sqlite3" ]; then \
		echo "🗂️  Context engine cache miss, building index..."; \
		$(MAKE) index; \
	fi
	. .venv/bin/activate && python scripts/check_bedrock.py && python scripts/run_dev_agent.py
	@if [ ! -z "$(PUSH_REMOTE)" ]; then \
		echo "🚀 Pushing artifacts to remote repository..."; \
		. .venv/bin/activate && \
		LATEST_OUTPUT=$$(find output/dev -maxdepth 1 -type d -name "20*" | sort | tail -1) && \
		if [ ! -z "$$LATEST_OUTPUT" ]; then \
			python scripts/push_artifacts.py --src "$$LATEST_OUTPUT" --remote "$(PUSH_REMOTE)"; \
		else \
			echo "⚠️ No dev output directory found to push"; \
		fi; \
	fi

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

# Run comprehensive Bedrock API tests
test-bedrock:
	@echo "🔍 Running comprehensive Bedrock API tests..."
	@if [ ! -d ".venv" ]; then echo "❌ Virtual environment not found. Run 'make venv' first."; exit 1; fi
	. .venv/bin/activate && python scripts/test_bedrock_direct.py

# Run AWS CLI Bedrock ping test
test-bedrock-cli:
	@echo "🔧 Running AWS CLI Bedrock ping test..."
	@chmod +x scripts/ping_bedrock_cli.sh
	./scripts/ping_bedrock_cli.sh

# Run AI code review on latest milestone
review:
	@echo "🔍 Running AI code review on latest milestone..."
	@if [ ! -d ".venv" ]; then echo "❌ Virtual environment not found. Run 'make venv' first."; exit 1; fi
	@# Find latest dev output or create review directory
	@LATEST_MILESTONE=$$(find output/dev -maxdepth 1 -type d -name "20*" | sort | tail -1); \
	if [ -z "$$LATEST_MILESTONE" ]; then \
		echo "📁 No dev output found, creating review directory with current source..."; \
		mkdir -p temp_review/milestone-current; \
		cp -r agents/ temp_review/milestone-current/ 2>/dev/null || true; \
		cp -r utils/ temp_review/milestone-current/ 2>/dev/null || true; \
		cp -r scripts/ temp_review/milestone-current/ 2>/dev/null || true; \
		LATEST_MILESTONE="temp_review/milestone-current"; \
	fi; \
	echo "🔍 Reviewing milestone: $$LATEST_MILESTONE"; \
	. .venv/bin/activate && python -m agents.review.reviewer_agent "$$LATEST_MILESTONE"

# Run review and promote to staging if passing
promote:
	@echo "🚀 Running review and promotion workflow..."
	@if [ ! -d ".venv" ]; then echo "❌ Virtual environment not found. Run 'make venv' first."; exit 1; fi
	@# Create promotion review directory
	@mkdir -p promotion_review/milestone-main
	@cp -r agents/ promotion_review/milestone-main/ 2>/dev/null || true
	@cp -r utils/ promotion_review/milestone-main/ 2>/dev/null || true
	@cp -r scripts/ promotion_review/milestone-main/ 2>/dev/null || true
	@echo "🔍 Running AI code review for promotion..."
	@. .venv/bin/activate && python -m agents.review.reviewer_agent promotion_review/milestone-main
	@# Check review status
	@REVIEW_STATUS=$$(. .venv/bin/activate && python scripts/check_review_status.py promotion_review/milestone-main/review-report.md); \
	echo "📊 Review Status: $$REVIEW_STATUS"; \
	if [ "$$REVIEW_STATUS" = "pass" ]; then \
		echo "✅ Review passed - proceeding with promotion"; \
		git config user.name "Local Developer" || true; \
		git config user.email "dev@localhost" || true; \
		if git show-ref --verify --quiet refs/heads/staging; then \
			echo "📋 Staging branch exists, checking out..."; \
			git checkout staging && git merge --ff-only main || echo "❌ Fast-forward merge failed"; \
		else \
			echo "🆕 Creating new staging branch..."; \
			git checkout -b staging || echo "❌ Failed to create staging branch"; \
		fi; \
		echo "🎉 Promotion complete! Code is on staging branch."; \
	else \
		echo "❌ Review failed - promotion blocked"; \
		echo "📄 Review report: promotion_review/milestone-main/review-report.md"; \
		exit 1; \
	fi

# Generate marketing announcement for milestone
announce:
	@echo "📢 Generating marketing announcement..."
	@if [ ! -d ".venv" ]; then echo "❌ Virtual environment not found. Run 'make venv' first."; exit 1; fi
	@# Find latest milestone or use current source
	@LATEST_MILESTONE=$$(find output/dev -maxdepth 1 -type d -name "20*" | sort | tail -1); \
	if [ -z "$$LATEST_MILESTONE" ]; then \
		echo "📁 No dev output found, using current source..."; \
		mkdir -p temp_announce/milestone-current; \
		cp -r agents/ temp_announce/milestone-current/ 2>/dev/null || true; \
		cp -r utils/ temp_announce/milestone-current/ 2>/dev/null || true; \
		LATEST_MILESTONE="temp_announce/milestone-current"; \
	fi; \
	echo "📢 Announcing milestone: $$LATEST_MILESTONE"; \
	. .venv/bin/activate && python -m agents.marketing.poster "$$LATEST_MILESTONE"

# Run complex project validation with real providers
validate:
	@echo "🔍 Running complex project validation suite..."
	@if [ ! -d ".venv" ]; then echo "❌ Virtual environment not found. Run 'make venv' first."; exit 1; fi
	@echo "⚠️  This will use REAL AI providers if configured (not fake). Set AI_PROVIDER=fake for offline testing."
	@echo "📊 Testing with complex projects (500+ files each)..."
	. .venv/bin/activate && python scripts/validate_complex_projects.py

# Run performance benchmark suite
benchmark:
	@echo "📊 Running performance benchmark suite..."
	@if [ ! -d ".venv" ]; then echo "❌ Virtual environment not found. Run 'make venv' first."; exit 1; fi
	@echo "🔧 Testing timeout behavior, performance guards, and complex project handling..."
	. .venv/bin/activate && python tests/performance/benchmark_suite.py

# Install and configure Serena LSP integration
setup-serena:
	@echo "🔧 Setting up Serena LSP integration..."
	@if [ ! -d ".venv" ]; then echo "❌ Virtual environment not found. Run 'make venv' first."; exit 1; fi
	. .venv/bin/activate && python scripts/setup_serena.py

# Run dev agent with Serena LSP context engine
dev-serena:
	@echo "🔍 Running dev agent with Serena LSP context engine..."
	@if [ ! -d ".venv" ]; then echo "❌ Virtual environment not found. Run 'make venv' first."; exit 1; fi
	@if [ ! -d ".serena" ]; then \
		echo "⚠️  Serena not configured. Running setup first..."; \
		$(MAKE) setup-serena; \
	fi
	. .venv/bin/activate && CONTEXT_ENGINE=serena python scripts/check_bedrock.py && CONTEXT_ENGINE=serena python scripts/run_dev_agent.py