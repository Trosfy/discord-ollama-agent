#!/bin/bash
# Helper script to start Discord-Trollama Agent services
# Checks for conflicting environment variables before starting

echo "🔍 Checking for conflicting environment variables..."

# List of variables that should come from .env file only
ENV_VARS=("DISCORD_TOKEN" "OLLAMA_HOST" "OLLAMA_DEFAULT_MODEL")

CONFLICTS=()
for var in "${ENV_VARS[@]}"; do
    if [ ! -z "${!var}" ]; then
        CONFLICTS+=("$var=${!var}")
    fi
done

if [ ${#CONFLICTS[@]} -gt 0 ]; then
    echo "⚠️  WARNING: The following environment variables are set in your shell:"
    for conflict in "${CONFLICTS[@]}"; do
        echo "   - $conflict"
    done
    echo ""
    echo "These will override values in .env file!"
    echo ""
    read -p "Do you want to unset them and continue? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        for var in "${ENV_VARS[@]}"; do
            unset "$var"
        done
        echo "✅ Environment variables unset"
    else
        echo "❌ Cancelled. Please unset these variables manually:"
        echo "   unset ${ENV_VARS[*]}"
        exit 1
    fi
fi

echo "✅ No conflicting environment variables found"
echo "🚀 Starting services..."
docker compose up -d "$@"
