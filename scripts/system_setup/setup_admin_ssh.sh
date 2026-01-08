#!/bin/bash
#
# Setup SSH key for admin-service container to execute host scripts
#
# This script:
# 1. Generates an ED25519 SSH key pair for the admin-service
# 2. Adds the public key to the current user's authorized_keys
# 3. Tests SSH connectivity to localhost
#
# Usage:
#   ./scripts/system_setup/setup_admin_ssh.sh
#
# After running this script:
# 1. Rebuild the admin-service container: docker compose build admin-service
# 2. Restart the stack: docker compose -f docker-compose.infra.yml up -d
#

set -e

# Configuration
SSH_KEY_PATH="$HOME/.ssh/admin_service_key"
SSH_KEY_COMMENT="admin-service-container"

echo "========================================"
echo "Admin Service SSH Setup"
echo "========================================"
echo ""

# Check if key already exists
if [ -f "$SSH_KEY_PATH" ]; then
    echo "SSH key already exists at $SSH_KEY_PATH"
    read -p "Regenerate key? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Keeping existing key."
    else
        echo "Removing existing key..."
        rm -f "$SSH_KEY_PATH" "$SSH_KEY_PATH.pub"
    fi
fi

# Generate new key if it doesn't exist
if [ ! -f "$SSH_KEY_PATH" ]; then
    echo "[1/4] Generating ED25519 SSH key..."
    ssh-keygen -t ed25519 -f "$SSH_KEY_PATH" -N "" -C "$SSH_KEY_COMMENT"
    chmod 600 "$SSH_KEY_PATH"
    chmod 644 "$SSH_KEY_PATH.pub"
    echo "  Key generated at $SSH_KEY_PATH"
else
    echo "[1/4] Using existing SSH key"
fi

# Add to authorized_keys if not already present
echo "[2/4] Configuring authorized_keys..."
mkdir -p "$HOME/.ssh"
chmod 700 "$HOME/.ssh"

PUBLIC_KEY=$(cat "$SSH_KEY_PATH.pub")
if grep -qF "$SSH_KEY_COMMENT" "$HOME/.ssh/authorized_keys" 2>/dev/null; then
    echo "  Public key already in authorized_keys"
else
    echo "$PUBLIC_KEY" >> "$HOME/.ssh/authorized_keys"
    chmod 600 "$HOME/.ssh/authorized_keys"
    echo "  Public key added to authorized_keys"
fi

# Test SSH connectivity
echo "[3/4] Testing SSH connectivity..."
if ssh -o StrictHostKeyChecking=no \
       -o UserKnownHostsFile=/dev/null \
       -o BatchMode=yes \
       -o ConnectTimeout=5 \
       -o LogLevel=ERROR \
       -i "$SSH_KEY_PATH" \
       "$(whoami)@localhost" \
       "echo 'SSH connection successful'" 2>/dev/null; then
    echo "  SSH test passed"
else
    echo "  WARNING: SSH test failed. Ensure sshd is running:"
    echo "    sudo systemctl status ssh"
    echo "    sudo systemctl start ssh"
fi

# Verify key permissions
echo "[4/4] Verifying file permissions..."
ls -la "$SSH_KEY_PATH" "$SSH_KEY_PATH.pub"

echo ""
echo "========================================"
echo "Setup Complete"
echo "========================================"
echo ""
echo "SSH key location: $SSH_KEY_PATH"
echo ""
echo "Next steps:"
echo "  1. Rebuild admin-service:"
echo "     docker compose -f docker-compose.infra.yml build admin-service"
echo ""
echo "  2. Restart the infrastructure stack:"
echo "     docker compose -f docker-compose.infra.yml up -d"
echo ""
echo "  3. Test from inside the container:"
echo "     docker exec trollama-admin ssh -i /home/app/.ssh/id_ed25519 \\"
echo "       -o StrictHostKeyChecking=no $(whoami)@host.docker.internal 'echo OK'"
echo ""
