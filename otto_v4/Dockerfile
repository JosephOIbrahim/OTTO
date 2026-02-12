FROM python:3.12-slim

WORKDIR /app

# Install only runtime deps (no dev)
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

# Create data directory
RUN mkdir -p /data

ENV OTTO_DB_PATH=/data/commitments.db
ENV OTTO_WATCHER_PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["otto", "watch", "--schedule"]
