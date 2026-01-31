# Installation Guide

This guide covers all installation methods for OTTO OS.

## Requirements

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Python | 3.10+ | 3.11+ |
| Memory | 2GB | 8GB |
| Storage | 500MB | 2GB |
| OS | Linux, macOS, Windows | Ubuntu 22.04+ |

### Optional Dependencies

| Feature | Requirement |
|---------|-------------|
| HSM Support | PKCS#11 library |
| GPU Acceleration | CUDA 11.8+ |
| Post-Quantum Crypto | liboqs |

---

## Installation Methods

### 1. pip (Recommended)

```bash
# Basic installation
pip install otto-os

# With all optional dependencies
pip install otto-os[all]

# Development installation
pip install otto-os[dev]
```

### 2. Docker

```bash
# Pull the latest image
docker pull ghcr.io/josephoibrahim/otto-os:latest

# Run the container
docker run -d \
  --name otto \
  -p 8080:8080 \
  -v otto-data:/data \
  ghcr.io/josephoibrahim/otto-os:latest
```

### 3. Docker Compose

```yaml
# docker-compose.yml
version: '3.8'
services:
  otto:
    image: ghcr.io/josephoibrahim/otto-os:latest
    ports:
      - "8080:8080"
    volumes:
      - otto-data:/data
      - ./config:/config
    environment:
      - OTTO_ENV=production
      - OTTO_LOG_LEVEL=info

volumes:
  otto-data:
```

```bash
docker-compose up -d
```

### 4. From Source

```bash
# Clone the repository
git clone https://github.com/JosephOIbrahim/OTTO_OS.git
cd OTTO_OS

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows

# Install in development mode
pip install -e ".[dev]"

# Run tests to verify installation
pytest
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `OTTO_ENV` | Environment (dev/prod) | `development` |
| `OTTO_PORT` | API port | `8080` |
| `OTTO_LOG_LEVEL` | Logging level | `info` |
| `OTTO_DATA_DIR` | Data directory | `~/.otto` |
| `OTTO_SECRET_KEY` | Secret key for signing | Generated |

### Configuration File

Create `~/.otto/config.yaml`:

```yaml
# OTTO Configuration
server:
  host: 0.0.0.0
  port: 8080
  workers: 4

security:
  secret_key: ${OTTO_SECRET_KEY}
  token_expiry: 3600
  enable_hsm: false

logging:
  level: info
  format: json
  file: ~/.otto/logs/otto.log

database:
  url: sqlite:///~/.otto/otto.db
  pool_size: 5

push:
  apns:
    enabled: false
    key_id: ""
    team_id: ""
  fcm:
    enabled: false
    project_id: ""
```

---

## Verification

### Check Installation

```bash
# Check version
otto --version

# Run health check
otto health

# Run self-test
otto test
```

### Expected Output

```
OTTO OS v1.0.0

Health Check:
  ✓ API Server: Running
  ✓ Database: Connected
  ✓ WebSocket: Available
  ✓ Push Service: Configured
  ✓ Security: Posture 95/100

All systems operational.
```

---

## Starting OTTO

### Development Mode

```bash
# Start with auto-reload
otto serve --reload

# With debug logging
otto serve --log-level debug
```

### Production Mode

```bash
# Start production server
otto serve --workers 4 --env production

# Or with gunicorn
gunicorn otto.api:app -w 4 -k uvicorn.workers.UvicornWorker
```

---

## Post-Installation

### 1. Initialize Database

```bash
otto db init
otto db migrate
```

### 2. Create Admin User

```bash
otto admin create --email admin@example.com
```

### 3. Configure Push Notifications

```bash
# iOS (APNS)
otto push configure apns \
  --key-id YOUR_KEY_ID \
  --team-id YOUR_TEAM_ID \
  --key-file /path/to/AuthKey.p8

# Android (FCM)
otto push configure fcm \
  --credentials /path/to/firebase-credentials.json
```

### 4. Enable Security Features

```bash
# Enable audit logging
otto security audit enable

# Enable self-healing
otto security healing enable

# Check posture
otto security posture
```

---

## Troubleshooting

### Common Issues

#### Port Already in Use

```bash
# Find process using port
lsof -i :8080

# Use different port
otto serve --port 8081
```

#### Permission Denied

```bash
# Fix permissions
chmod 755 ~/.otto
chmod 600 ~/.otto/config.yaml
```

#### Missing Dependencies

```bash
# Install system dependencies (Ubuntu)
sudo apt-get install libffi-dev libssl-dev

# Install optional dependencies
pip install otto-os[hsm]
pip install otto-os[pq]
```

---

## Next Steps

1. [Quick Start](../QUICKSTART.md) - Get started quickly
2. [Configuration](../CONFIGURATION.md) - Detailed configuration
3. [API Reference](../API.md) - API documentation
