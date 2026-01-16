#!/bin/bash
# Build and deploy TROISE TUI to PATH
#
# Usage:
#   ./build-deploy.sh [options]
#
# Options:
#   --prefix PATH    Installation prefix (default: /usr/local)
#   --no-minify      Skip minification for faster builds
#   --debug          Build with debug info
#   --help           Show this help message

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Defaults
PREFIX="${HOME}/.local"  # User-local by default (no sudo needed)
MINIFY="--minify"
DEBUG=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --prefix)
            PREFIX="$2"
            shift 2
            ;;
        --no-minify)
            MINIFY=""
            shift
            ;;
        --debug)
            DEBUG="--sourcemap"
            shift
            ;;
        --help)
            echo "Build and deploy TROISE TUI"
            echo ""
            echo "Usage:"
            echo "  ./build-deploy.sh [options]"
            echo ""
            echo "Options:"
            echo "  --prefix PATH    Installation prefix (default: /usr/local)"
            echo "  --no-minify      Skip minification for faster builds"
            echo "  --debug          Build with debug info"
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

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Find bun
find_bun() {
    if command -v bun &> /dev/null; then
        echo "bun"
    elif [ -x "$HOME/.bun/bin/bun" ]; then
        echo "$HOME/.bun/bin/bun"
    else
        error "Bun not found. Install it with: curl -fsSL https://bun.sh/install | bash"
    fi
}

# Main
main() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║      TROISE TUI Build & Deploy         ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    echo ""

    cd "$SCRIPT_DIR"

    # Find bun
    BUN=$(find_bun)
    info "Using bun: $BUN"

    # Install dependencies if needed
    if [ ! -d "node_modules" ]; then
        info "Installing dependencies..."
        $BUN install
    fi

    # Create dist directory
    mkdir -p dist

    # Build
    info "Building TROISE TUI..."
    BUILD_START=$(date +%s)

    $BUN build src/index.tsx \
        --compile \
        $MINIFY \
        $DEBUG \
        --outfile=dist/troise

    BUILD_END=$(date +%s)
    BUILD_TIME=$((BUILD_END - BUILD_START))

    success "Built in ${BUILD_TIME}s"

    # Get binary info
    BINARY_SIZE=$(ls -lh dist/troise | awk '{print $5}')
    info "Binary size: $BINARY_SIZE"

    # Deploy to PATH
    info "Deploying to ${PREFIX}/bin..."

    # Check if we need sudo
    INSTALL_CMD=""
    if [ ! -w "${PREFIX}/bin" ]; then
        if command -v sudo &> /dev/null; then
            INSTALL_CMD="sudo"
            info "Using sudo for installation"
        else
            error "Cannot write to ${PREFIX}/bin and sudo is not available"
        fi
    fi

    # Create bin directory if needed
    $INSTALL_CMD mkdir -p "${PREFIX}/bin"

    # Install binary
    $INSTALL_CMD cp dist/troise "${PREFIX}/bin/troise"
    $INSTALL_CMD chmod +x "${PREFIX}/bin/troise"

    # Verify installation
    if [ -x "${PREFIX}/bin/troise" ]; then
        VERSION=$("${PREFIX}/bin/troise" --version 2>/dev/null || echo "0.1.0")
        success "Installed troise ${VERSION} to ${PREFIX}/bin/troise"
    else
        error "Installation verification failed"
    fi

    # Check PATH
    if ! echo "$PATH" | grep -q "${PREFIX}/bin"; then
        echo ""
        echo -e "${YELLOW}[WARN]${NC} ${PREFIX}/bin is not in your PATH"
        echo "Add to your shell profile:"
        echo ""
        echo "  export PATH=\"\$PATH:${PREFIX}/bin\""
        echo ""
    fi

    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║         Build & Deploy Complete!       ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "Run ${GREEN}troise${NC} to start the TUI"
    echo ""
}

main
