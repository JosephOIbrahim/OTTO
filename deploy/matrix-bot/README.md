# OTTO Matrix Bot Deployment

Secure mobile interface for OTTO OS via the Matrix protocol.

## Features

- **End-to-End Encryption**: Matrix Olm/Megolm + optional PQ crypto layer
- **All OTTO Commands**: !health, !info, !secure, !threshold, !state, !projects
- **Mobile Access**: Works with Element, FluffyChat, or any Matrix client
- **Post-Quantum Ready**: ML-KEM-768 + X25519 hybrid encryption

## Quick Start (Docker)

### 1. Prerequisites

- Docker and Docker Compose
- A Matrix account (create at [Element](https://app.element.io))

### 2. Configure

```bash
cd deploy/matrix-bot
cp .env.example .env
# Edit .env with your Matrix credentials
nano .env
```

### 3. Deploy

```bash
# Build and start
docker-compose up -d

# Check logs
docker-compose logs -f otto-bot

# Stop
docker-compose down
```

## Alternative: Systemd Deployment

### 1. Install OTTO

```bash
# Create otto user
sudo useradd -r -s /bin/false otto
sudo mkdir -p /opt/otto /var/lib/otto /var/log/otto
sudo chown otto:otto /var/lib/otto /var/log/otto

# Clone and setup
cd /opt/otto
sudo git clone https://github.com/JosephOIbrahim/otto-os.git .
sudo python3 -m venv venv
sudo ./venv/bin/pip install -e ".[matrix]"
```

### 2. Configure

```bash
# Create environment file
sudo mkdir -p /etc/otto
sudo nano /etc/otto/bot.env
```

Add to `/etc/otto/bot.env`:
```bash
OTTO_HOMESERVER=https://matrix.org
OTTO_USER_ID=@your-bot:matrix.org
OTTO_PASSWORD=your-password
OTTO_DEVICE_ID=OTTO_BOT
OTTO_DATA_DIR=/var/lib/otto
OTTO_LOG_LEVEL=INFO
OTTO_ENABLE_PQ=true
```

### 3. Install Service

```bash
sudo cp deploy/matrix-bot/otto-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable otto-bot
sudo systemctl start otto-bot

# Check status
sudo systemctl status otto-bot
journalctl -u otto-bot -f
```

## Usage

Once the bot is running, message it from any Matrix client:

```
You: !help
Bot: OTTO Commands:
     !health  - Check system health
     !info    - Show system information
     !secure  - Manage secure channels
     !threshold - Threshold operations
     !state   - Query cognitive state
     !projects - List active projects
     !admin   - Admin operations (authorized users only)

You: !health
Bot: OTTO Health Status
     ==================
     Core: OK
     Crypto: OK (PQ: Enabled)
     Matrix Bot: OK
     Memory: OK

You: !secure status
Bot: Secure Channel Status
     =====================
     PQ Available: True
     Algorithm: ML-KEM-768
     Classical: X25519
     Mode: hybrid
```

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Mobile Device                             │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Element / FluffyChat / Any Matrix Client              │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
                              │
                              │ Matrix Protocol (E2E Encrypted)
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                    Matrix Homeserver                          │
│  (matrix.org / self-hosted Synapse / Conduit)                │
└──────────────────────────────────────────────────────────────┘
                              │
                              │ Matrix Protocol (E2E Encrypted)
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                    OTTO Matrix Bot                            │
│  ┌──────────────────┐  ┌──────────────────┐                  │
│  │  Matrix Client   │──│  PQ Secure       │                  │
│  │  (matrix-nio)    │  │  Channel         │                  │
│  └──────────────────┘  └──────────────────┘                  │
│           │                     │                             │
│           ▼                     ▼                             │
│  ┌──────────────────────────────────────────────────────┐    │
│  │              OTTO Core                                │    │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ │    │
│  │  │ Crypto   │ │ Security │ │ Agents   │ │ State   │ │    │
│  │  │ PQ+Thr   │ │ Posture  │ │ Planner  │ │ Manage  │ │    │
│  │  └──────────┘ └──────────┘ └──────────┘ └─────────┘ │    │
│  └──────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

## Security Layers

| Layer | Technology | Protection |
|-------|------------|------------|
| 1 | TLS | Transport encryption |
| 2 | Matrix Olm/Megolm | E2E message encryption |
| 3 | OTTO PQ Channel | Post-quantum key exchange |
| 4 | Threshold Signatures | N-of-M approval for critical ops |

## Configuration Options

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OTTO_HOMESERVER` | Yes | - | Matrix homeserver URL |
| `OTTO_USER_ID` | Yes | - | Bot's Matrix user ID |
| `OTTO_PASSWORD` | Yes* | - | Bot's password |
| `OTTO_ACCESS_TOKEN` | Yes* | - | Alternative to password |
| `OTTO_DEVICE_ID` | No | OTTO_BOT | Device identifier |
| `OTTO_DATA_DIR` | No | ~/.otto | Data storage path |
| `OTTO_LOG_LEVEL` | No | INFO | Logging verbosity |
| `OTTO_ENABLE_PQ` | No | true | Enable PQ crypto |
| `OTTO_ALLOWED_USERS` | No | (all) | Restrict to users |
| `OTTO_AUTO_JOIN` | No | false | Auto-join invites |

*Either `OTTO_PASSWORD` or `OTTO_ACCESS_TOKEN` is required.

## Troubleshooting

### Bot won't login

1. Check credentials in `.env`
2. Verify homeserver URL is correct
3. Try with access token instead of password
4. Check firewall allows outbound HTTPS

### Messages not delivered

1. Verify E2E keys are trusted (may need to verify in Element)
2. Check bot is in the room
3. Look for errors in logs: `docker-compose logs otto-bot`

### PQ crypto not working

1. Check `OTTO_ENABLE_PQ=true`
2. Verify liboqs is installed: bot logs will show PQ status
3. PQ is optional - bot works with classical crypto if unavailable

## Upgrading

```bash
# Docker
docker-compose pull
docker-compose up -d

# Systemd
cd /opt/otto
sudo git pull
sudo ./venv/bin/pip install -e ".[matrix]"
sudo systemctl restart otto-bot
```

## License

MIT License - See [LICENSE](../../LICENSE)
