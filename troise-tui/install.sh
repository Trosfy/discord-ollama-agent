#!/bin/bash
# TROISE TUI Installer
# Install the TROISE terminal UI client
#
# Usage:
#   curl -fsSL https://install.troise.ai | bash
#   or
#   ./install.sh [options]
#
# Options:
#   --prefix PATH    Installation prefix (default: /usr/local)
#   --no-color       Disable colored output
#   --help           Show this help message

set -e

# Colors (unless --no-color)
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Defaults
PREFIX="/usr/local"
NO_COLOR=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --prefix)
            PREFIX="$2"
            shift 2
            ;;
        --no-color)
            NO_COLOR=true
            RED=''
            GREEN=''
            YELLOW=''
            BLUE=''
            NC=''
            shift
            ;;
        --help)
            echo "TROISE TUI Installer"
            echo ""
            echo "Usage:"
            echo "  curl -fsSL https://install.troise.ai | bash"
            echo "  ./install.sh [options]"
            echo ""
            echo "Options:"
            echo "  --prefix PATH    Installation prefix (default: /usr/local)"
            echo "  --no-color       Disable colored output"
            echo "  --help           Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Helper functions
info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Detect OS and architecture
detect_platform() {
    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)

    case "$OS" in
        linux)
            OS="linux"
            ;;
        darwin)
            OS="darwin"
            ;;
        *)
            error "Unsupported OS: $OS"
            ;;
    esac

    case "$ARCH" in
        x86_64|amd64)
            ARCH="x64"
            ;;
        arm64|aarch64)
            ARCH="arm64"
            ;;
        *)
            error "Unsupported architecture: $ARCH"
            ;;
    esac

    echo "${OS}-${ARCH}"
}

# Check for required commands
check_requirements() {
    if ! command -v curl &> /dev/null && ! command -v wget &> /dev/null; then
        error "Either curl or wget is required"
    fi
}

# Download function (uses curl or wget)
download() {
    local url="$1"
    local output="$2"

    if command -v curl &> /dev/null; then
        curl -fsSL "$url" -o "$output"
    elif command -v wget &> /dev/null; then
        wget -q "$url" -O "$output"
    fi
}

# Main installation
main() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║        TROISE TUI Installer            ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    echo ""

    # Check requirements
    info "Checking requirements..."
    check_requirements

    # Detect platform
    info "Detecting platform..."
    PLATFORM=$(detect_platform)
    info "Platform: $PLATFORM"

    # Version (latest)
    VERSION="latest"
    BINARY_NAME="troise-${PLATFORM}"

    # Download URL (update this to your actual release URL)
    BASE_URL="https://github.com/trosfy/troise-tui/releases/download"
    DOWNLOAD_URL="${BASE_URL}/${VERSION}/${BINARY_NAME}"

    # Create temp directory
    TEMP_DIR=$(mktemp -d)
    trap "rm -rf $TEMP_DIR" EXIT

    # Download binary
    info "Downloading TROISE TUI..."
    BINARY_PATH="${TEMP_DIR}/troise"

    # For development, check if we have a local build first
    if [ -f "./dist/${BINARY_NAME}" ]; then
        info "Using local build..."
        cp "./dist/${BINARY_NAME}" "$BINARY_PATH"
    else
        # Download from release
        if ! download "$DOWNLOAD_URL" "$BINARY_PATH"; then
            error "Failed to download TROISE TUI from $DOWNLOAD_URL"
        fi
    fi

    # Make executable
    chmod +x "$BINARY_PATH"

    # Install to prefix
    info "Installing to ${PREFIX}/bin..."

    # Check if we need sudo
    INSTALL_CMD=""
    if [ ! -w "${PREFIX}/bin" ]; then
        if command -v sudo &> /dev/null; then
            INSTALL_CMD="sudo"
        else
            error "Cannot write to ${PREFIX}/bin and sudo is not available"
        fi
    fi

    # Create bin directory if needed
    $INSTALL_CMD mkdir -p "${PREFIX}/bin"

    # Install binary
    $INSTALL_CMD cp "$BINARY_PATH" "${PREFIX}/bin/troise"
    $INSTALL_CMD chmod +x "${PREFIX}/bin/troise"

    # Verify installation
    if command -v "${PREFIX}/bin/troise" &> /dev/null; then
        success "TROISE TUI installed successfully!"
        echo ""
        echo -e "${GREEN}Run 'troise --help' to get started${NC}"
        echo ""

        # Check if in PATH
        if ! echo "$PATH" | grep -q "${PREFIX}/bin"; then
            warn "${PREFIX}/bin is not in your PATH"
            echo ""
            echo "Add the following to your shell profile:"
            echo ""
            echo "  export PATH=\"\$PATH:${PREFIX}/bin\""
            echo ""
        fi
    else
        error "Installation verification failed"
    fi

    # Create default config directory
    CONFIG_DIR="${HOME}/.config/troise"
    if [ ! -d "$CONFIG_DIR" ]; then
        mkdir -p "$CONFIG_DIR"
        info "Created config directory: $CONFIG_DIR"
    fi

    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║         Installation Complete!         ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    echo ""
}

# Run main
main
