FROM python:3.11-slim

WORKDIR /app

# Install curl for healthcheck, procps for 'free' command, and uv
RUN apt-get update && apt-get install -y curl procps && rm -rf /var/lib/apt/lists/*
RUN pip install uv

# Create unprivileged user
RUN useradd --system --uid 1000 --shell /bin/bash app \
    && chown -R app:app /app

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies with uv
RUN uv pip install --system --no-cache .

# Copy application code
COPY --chown=app:app app/ ./app/

EXPOSE 8000

# Switch to unprivileged user
USER app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
