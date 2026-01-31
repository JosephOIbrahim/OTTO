# OTTO Dashboard PWA - Dockerfile
# =================================
#
# Multi-stage build for production deployment
#
# Build:
#   docker build -t otto-dashboard .
#
# Run:
#   docker run -p 8080:8080 otto-dashboard

# =============================================================================
# Stage 1: Builder (optional minification)
# =============================================================================
FROM python:3.11-slim as builder

WORKDIR /build

# Copy static assets
COPY index.html manifest.json sw.js ./
COPY static/ ./static/

# Optional: Install tools for minification
# RUN pip install --no-cache-dir csscompressor jsmin
# RUN python -c "import csscompressor; ..."

# =============================================================================
# Stage 2: Production
# =============================================================================
FROM python:3.11-slim

LABEL maintainer="OTTO OS Team"
LABEL description="OTTO Dashboard PWA"
LABEL version="1.0.0"

# Security: Non-root user
RUN useradd --create-home --shell /bin/bash otto
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy OTTO source (for API integration)
COPY --chown=otto:otto ../../src/otto /app/otto
COPY --chown=otto:otto ../../pyproject.toml /app/

# Install Python dependencies
RUN pip install --no-cache-dir -e /app

# Copy dashboard files
COPY --from=builder --chown=otto:otto /build/ /app/dashboard/
COPY --chown=otto:otto server.py /app/dashboard/

# Switch to non-root user
USER otto

# Environment
ENV PYTHONUNBUFFERED=1
ENV DASHBOARD_PORT=8080

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${DASHBOARD_PORT}/ || exit 1

# Expose port
EXPOSE 8080

# Run dashboard server
WORKDIR /app/dashboard
CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8080"]
