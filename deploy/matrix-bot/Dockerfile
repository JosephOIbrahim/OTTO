# OTTO Matrix Bot - Production Dockerfile
# =========================================
#
# Multi-stage build for minimal production image
# Includes optional liboqs for post-quantum crypto

# Stage 1: Build dependencies
FROM python:3.11-slim as builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    git \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Optional: Build liboqs for post-quantum crypto
ARG ENABLE_PQ=true
RUN if [ "$ENABLE_PQ" = "true" ]; then \
    git clone --depth 1 https://github.com/open-quantum-safe/liboqs.git && \
    cd liboqs && \
    mkdir build && cd build && \
    cmake -DBUILD_SHARED_LIBS=ON .. && \
    make -j$(nproc) && \
    make install && \
    ldconfig; \
    fi

# Create virtual environment and install Python deps
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install matrix-nio with E2E support
RUN pip install --no-cache-dir "matrix-nio[e2e]"

# Install liboqs-python if PQ enabled
RUN if [ "$ENABLE_PQ" = "true" ]; then \
    pip install --no-cache-dir liboqs-python; \
    fi


# Stage 2: Production image
FROM python:3.11-slim as production

# Security: Run as non-root user
RUN useradd --create-home --shell /bin/bash otto

WORKDIR /app

# Copy liboqs if built
COPY --from=builder /usr/local/lib/liboqs* /usr/local/lib/
RUN ldconfig || true

# Copy virtual environment
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    libffi8 \
    libssl3 \
    && rm -rf /var/lib/apt/lists/*

# Copy application code
COPY --chown=otto:otto src/ ./src/
COPY --chown=otto:otto deploy/matrix-bot/entrypoint.sh ./

# Create data directories
RUN mkdir -p /data/store /data/keys /data/logs && \
    chown -R otto:otto /data

# Switch to non-root user
USER otto

# Environment variables (override in docker-compose or runtime)
ENV OTTO_HOMESERVER="https://matrix.org" \
    OTTO_USER_ID="" \
    OTTO_PASSWORD="" \
    OTTO_DEVICE_ID="OTTO_BOT" \
    OTTO_DATA_DIR="/data" \
    OTTO_LOG_LEVEL="INFO" \
    OTTO_ENABLE_PQ="true" \
    PYTHONPATH="/app/src"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import asyncio; from otto.messaging import create_bot; print('OK')" || exit 1

# Expose metrics port (optional)
EXPOSE 9090

ENTRYPOINT ["./entrypoint.sh"]
CMD ["python", "-m", "otto.messaging.run_bot"]
