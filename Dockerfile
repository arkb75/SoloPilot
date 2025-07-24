# SoloPilot Dockerfile
# Multi-stage build for optimal image size

FROM python:3.11-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash solopilot
RUN chown -R solopilot:solopilot /app

# Copy application code
COPY --chown=solopilot:solopilot . .

# Create necessary directories
RUN mkdir -p analysis/output temp logs sample_input \
    && chown -R solopilot:solopilot analysis temp logs sample_input

# Switch to non-root user
USER solopilot

# Set Python path
ENV PYTHONPATH=/app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import src.agents.analyser; print('OK')" || exit 1

# Default command
CMD ["python", "scripts/run_analyser.py", "--help"]
