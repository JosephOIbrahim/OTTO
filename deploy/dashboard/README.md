# OTTO Dashboard PWA

Mobile-first Progressive Web App for OTTO OS cognitive management.

## Features

- **Real-time Status**: Health, energy, burnout, and momentum tracking
- **Cognitive State**: View active mode, paradigm, and altitude
- **Security Dashboard**: Security posture, PQ crypto status, E2E encryption
- **Quick Commands**: Execute OTTO commands from mobile
- **Offline Support**: Service worker caching for offline use
- **Push Notifications**: Real-time alerts (when configured)
- **Installable**: Add to home screen on iOS/Android

## Quick Start

### 1. Run the Dashboard Server

```bash
cd deploy/dashboard
python server.py --port 8080
```

### 2. Open in Browser

Navigate to `http://localhost:8080`

### 3. Install as PWA

- **iOS**: Safari > Share > Add to Home Screen
- **Android**: Chrome > Menu > Add to Home Screen
- **Desktop**: Chrome > Menu > Install OTTO Dashboard

## Development

### File Structure

```
deploy/dashboard/
├── index.html           # Main HTML file
├── manifest.json        # PWA manifest
├── sw.js               # Service worker
├── server.py           # Python server
├── static/
│   ├── css/
│   │   └── dashboard.css
│   ├── js/
│   │   └── dashboard.js
│   └── icons/
│       └── (icon files)
```

### Local Development

1. Start the server:
   ```bash
   python server.py --port 8080
   ```

2. The dashboard auto-connects to the API at the same origin

3. Changes to CSS/JS are reflected on refresh

### Docker Deployment

```bash
docker build -t otto-dashboard .
docker run -p 8080:8080 otto-dashboard
```

## API Integration

The dashboard communicates with OTTO through these endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/mobile/sync` | GET | Sync cognitive state |
| `/api/v1/security/posture` | GET | Security posture |
| `/api/v1/security/crypto` | GET | Crypto capabilities |
| `/api/v1/commands/:cmd` | POST | Execute command |

## Offline Behavior

When offline, the dashboard:
1. Shows cached state data
2. Queues commands for later sync
3. Displays "Offline" status indicator
4. Uses cached API responses (1 minute TTL)

## Push Notifications

To enable push notifications:

1. Register device via API
2. Configure push token (APNS/FCM)
3. Dashboard will receive real-time alerts

## Customization

### Themes

The dashboard supports light/dark mode based on system preference.
Override with CSS custom properties in `dashboard.css`.

### Adding Commands

Add new command buttons in `index.html`:
```html
<button class="command-btn" data-command="yourcommand">
    <span class="btn-icon">&#9881;</span>
    <span class="btn-label">Label</span>
</button>
```

## Security

- All API requests require authentication token
- Service worker validates cached content
- CSP headers prevent XSS
- No inline scripts (all external)

## Browser Support

- iOS Safari 14+
- Android Chrome 90+
- Desktop Chrome/Firefox/Edge (latest)
- Requires JavaScript enabled
