FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

# Set working directory
WORKDIR /workspace

# Copy project files
COPY . /workspace

# Install project dependencies
RUN . /root/.local/bin/activate && uv pip install -r requirements.txt

# Install Serena via uvx
RUN . /root/.local/bin/activate && uvx --from git+https://github.com/oraios/serena index-project .

# Expose port for SSE mode (if needed)
EXPOSE 8765

# Default command starts Serena MCP server
CMD ["sh", "-c", ". /root/.local/bin/activate && uvx --from git+https://github.com/oraios/serena serena-mcp-server --project /workspace --transport sse --port 8765 --enable-web-dashboard false --enable-gui-log-window false"]
