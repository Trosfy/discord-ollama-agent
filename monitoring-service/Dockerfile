FROM python:3.11-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Install uv for faster package installation
RUN pip install uv

# Copy project definition
COPY pyproject.toml ./

# Install dependencies using uv
RUN uv pip install --system --no-cache .

# Copy application
COPY *.py ./
COPY templates/ ./templates/

# Create data directory for SQLite
RUN mkdir -p /app/data

# Expose port
EXPOSE 8080

CMD ["python", "monitor.py"]
