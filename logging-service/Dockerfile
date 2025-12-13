FROM python:3.11-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install uv for faster package installation
RUN pip install uv

# Copy project definition
COPY pyproject.toml ./

# Install dependencies using uv (minimal dependencies)
RUN uv pip install --system --no-cache .

# Copy application
COPY server.py .

# Create logs directory
RUN mkdir -p /app/logs

CMD ["python", "server.py"]
