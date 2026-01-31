# PWA Dashboard

OTTO includes a Progressive Web App (PWA) dashboard for monitoring and interacting with your cognitive state from any device.

## Overview

The OTTO PWA provides:

- **Real-time State Monitoring** - Live cognitive state updates
- **Burnout Visualization** - Visual burnout indicators
- **Project Management** - View and switch projects
- **Command Interface** - Execute OTTO commands
- **Offline Support** - Works without network

## Installation

### From Browser

1. Visit `https://app.otto-os.io`
2. Click "Install" in browser menu
3. Add to Home Screen

### Direct URLs

| Platform | URL |
|----------|-----|
| Web App | `https://app.otto-os.io` |
| API Docs | `https://docs.otto-os.io` |

---

## Features

### Dashboard View

```
+------------------------------------------+
|  OTTO Dashboard            [user] [gear] |
+------------------------------------------+
|                                          |
|  Cognitive State                         |
|  +------------------------------------+  |
|  | Mode: FOCUSED      Energy: HIGH   |  |
|  | Burnout: [====----] GREEN         |  |
|  | Momentum: rolling                 |  |
|  +------------------------------------+  |
|                                          |
|  Active Project: OTTO OS                 |
|  +------------------------------------+  |
|  | Status: FOCUS                     |  |
|  | Progress: 65%                     |  |
|  | Next: Complete API docs           |  |
|  +------------------------------------+  |
|                                          |
|  Quick Actions                           |
|  [Health] [State] [Projects] [Break]    |
|                                          |
+------------------------------------------+
```

### State Visualization

The dashboard provides real-time visualization of:

| Component | Visualization |
|-----------|---------------|
| Burnout Level | Color-coded bar (GREEN/YELLOW/ORANGE/RED) |
| Energy Level | Battery-style indicator |
| Momentum | Flow indicator with phase name |
| Mode | Icon + text label |

---

## Configuration

### Enable PWA in OTTO

```yaml
# ~/.otto/config.yaml
pwa:
  enabled: true
  title: "OTTO Dashboard"
  theme_color: "#7c3aed"
  background_color: "#1f2937"

  features:
    offline_mode: true
    push_notifications: true
    background_sync: true
```

### Manifest

The PWA manifest (`manifest.json`):

```json
{
  "name": "OTTO Dashboard",
  "short_name": "OTTO",
  "description": "Cognitive Operating System Dashboard",
  "start_url": "/",
  "display": "standalone",
  "theme_color": "#7c3aed",
  "background_color": "#1f2937",
  "icons": [
    {
      "src": "/icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/icons/icon-512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

---

## WebSocket Integration

The PWA connects to OTTO via WebSocket for real-time updates:

```javascript
// PWA WebSocket connection
const otto = new OTTOWebSocket(accessToken);

otto.on('state_update', (state) => {
  updateDashboard(state);
});

otto.on('alert', (alert) => {
  showNotification(alert);
});

otto.subscribe(['state', 'alerts', 'projects']);
```

---

## Offline Support

The PWA includes service worker caching for offline functionality:

### Cached Resources

| Resource Type | Strategy |
|---------------|----------|
| App Shell | Cache-first |
| API Responses | Network-first |
| Static Assets | Cache-first |
| Fonts | Cache-first |

### Service Worker

```javascript
// sw.js
const CACHE_NAME = 'otto-v1';

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll([
        '/',
        '/index.html',
        '/app.js',
        '/styles.css'
      ]);
    })
  );
});
```

---

## Push Notifications

Enable browser push notifications:

```javascript
// Request permission
const permission = await Notification.requestPermission();

if (permission === 'granted') {
  // Subscribe to push
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: vapidPublicKey
  });

  // Send to OTTO
  await otto.registerPushToken(subscription);
}
```

---

## Development

### Running Locally

```bash
# Start development server
cd pwa
npm install
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | React 18 |
| Styling | Tailwind CSS |
| State | React Query |
| WebSocket | Custom hook |
| Build | Vite |
| PWA | Workbox |

---

## Deployment

### Static Hosting

```bash
# Build PWA
npm run build

# Deploy to CDN
aws s3 sync dist/ s3://otto-pwa --delete
aws cloudfront create-invalidation --distribution-id XXX --paths "/*"
```

### Docker

```dockerfile
FROM nginx:alpine
COPY dist/ /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
```

---

## See Also

- [Mobile API](../api/mobile.md) - API reference
- [WebSocket API](../api/websocket.md) - Real-time updates
- [Matrix Integration](matrix.md) - Matrix bot
