FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (curl for healthcheck, procps for 'free', git for strands-agents)
RUN apt-get update && apt-get install -y curl procps git && rm -rf /var/lib/apt/lists/*
RUN pip install uv

# Create unprivileged user
RUN useradd --system --uid 1000 --shell /bin/bash app \
    && chown -R app:app /app

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies with uv (need git for strands-agents from GitHub)
# Include diffusion extra for FLUX 2.dev image generation
RUN uv pip install --system --no-cache ".[diffusion]"

# Copy application code
COPY --chown=app:app app/ ./app/
COPY --chown=app:app config/ ./config/

EXPOSE 8000

# Switch to unprivileged user
USER app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
