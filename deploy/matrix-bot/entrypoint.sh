#!/bin/bash
# OTTO Matrix Bot - Container Entrypoint
# =======================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validate required environment variables
validate_env() {
    if [ -z "$OTTO_HOMESERVER" ]; then
        log_error "OTTO_HOMESERVER is required"
        exit 1
    fi

    if [ -z "$OTTO_USER_ID" ]; then
        log_error "OTTO_USER_ID is required (e.g., @otto:matrix.org)"
        exit 1
    fi

    if [ -z "$OTTO_PASSWORD" ] && [ -z "$OTTO_ACCESS_TOKEN" ]; then
        log_error "Either OTTO_PASSWORD or OTTO_ACCESS_TOKEN is required"
        exit 1
    fi
}

# Check PQ crypto availability
check_pq_crypto() {
    if [ "$OTTO_ENABLE_PQ" = "true" ]; then
        if python -c "from otto.crypto.pqcrypto import is_pq_available; exit(0 if is_pq_available() else 1)" 2>/dev/null; then
            log_info "Post-quantum crypto: ENABLED (ML-KEM-768 + X25519)"
        else
            log_warn "Post-quantum crypto: UNAVAILABLE (using classical X25519 only)"
        fi
    else
        log_info "Post-quantum crypto: DISABLED by configuration"
    fi
}

# Initialize data directories
init_data_dirs() {
    mkdir -p "$OTTO_DATA_DIR/store"
    mkdir -p "$OTTO_DATA_DIR/keys"
    mkdir -p "$OTTO_DATA_DIR/logs"
    mkdir -p "$OTTO_DATA_DIR/audit"
    log_info "Data directories initialized: $OTTO_DATA_DIR"
}

# Display startup banner
show_banner() {
    echo ""
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║                    OTTO Matrix Bot                        ║"
    echo "║         Secure Mobile Interface for OTTO OS               ║"
    echo "╠═══════════════════════════════════════════════════════════╣"
    echo "║  Homeserver: $OTTO_HOMESERVER"
    echo "║  User ID:    $OTTO_USER_ID"
    echo "║  Device:     ${OTTO_DEVICE_ID:-auto}"
    echo "║  PQ Crypto:  ${OTTO_ENABLE_PQ:-true}"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo ""
}

# Main entrypoint
main() {
    show_banner
    validate_env
    init_data_dirs
    check_pq_crypto

    log_info "Starting OTTO Matrix Bot..."

    # Execute the command
    exec "$@"
}

main "$@"
