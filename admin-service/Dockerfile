FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including Docker CLI, procps, and openssh-client
RUN apt-get update && apt-get install -y \
    curl \
    ca-certificates \
    gnupg \
    procps \
    openssh-client \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && apt-get update \
    && apt-get install -y docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

# Create docker group with GID 999 (typical host docker group)
# Create app user with UID 1001 to match host user (for SSH key access)
RUN groupadd --system --gid 999 docker || true \
    && useradd --system --uid 1001 --gid 999 --groups docker --shell /bin/bash app \
    && chown -R app:docker /app \
    && mkdir -p /home/app/.ssh \
    && chown -R app:docker /home/app \
    && chmod 700 /home/app/.ssh

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=app:docker app/ ./app/

EXPOSE 8000

# Switch to app user
USER app

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
