FROM python:3.11-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies with uv
RUN uv pip install --system --no-cache .

# Copy application code
COPY bot/ ./bot/

CMD ["python", "-u", "-m", "bot.main"]
