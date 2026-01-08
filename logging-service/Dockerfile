FROM python:3.11-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Create docker group and app user (same as admin-service for log file permissions)
RUN groupadd --system --gid 999 docker || true \
    && useradd --system --uid 1000 --gid 999 --shell /bin/bash app \
    && chown -R app:docker /app

# Install uv for faster package installation
RUN pip install uv

# Copy project definition
COPY pyproject.toml ./

# Install dependencies using uv (minimal dependencies)
RUN uv pip install --system --no-cache .

# Copy application
COPY --chown=app:docker server.py .

# Create logs directory with proper ownership
RUN mkdir -p /app/logs && chown -R app:docker /app/logs

# Switch to app user
USER app

CMD ["python", "server.py"]
