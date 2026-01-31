/**
 * OTTO Dashboard - Service Worker
 *
 * Provides offline support and caching for the PWA.
 */

const CACHE_NAME = 'otto-dashboard-v1';
const STATIC_ASSETS = [
    '/',
    '/index.html',
    '/manifest.json',
    '/static/css/dashboard.css',
    '/static/js/dashboard.js',
    '/static/icons/icon-192.png',
    '/static/icons/icon-512.png',
];

// API endpoints to cache
const API_CACHE_NAME = 'otto-api-v1';
const API_CACHE_DURATION = 60 * 1000; // 1 minute

// Install event - cache static assets
self.addEventListener('install', (event) => {
    console.log('[SW] Installing...');

    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => {
                console.log('[SW] Caching static assets');
                return cache.addAll(STATIC_ASSETS);
            })
            .then(() => {
                console.log('[SW] Install complete');
                return self.skipWaiting();
            })
    );
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
    console.log('[SW] Activating...');

    event.waitUntil(
        caches.keys()
            .then((cacheNames) => {
                return Promise.all(
                    cacheNames
                        .filter((name) => name !== CACHE_NAME && name !== API_CACHE_NAME)
                        .map((name) => {
                            console.log('[SW] Deleting old cache:', name);
                            return caches.delete(name);
                        })
                );
            })
            .then(() => {
                console.log('[SW] Activate complete');
                return self.clients.claim();
            })
    );
});

// Fetch event - serve from cache or network
self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);

    // Handle API requests differently
    if (url.pathname.startsWith('/api/')) {
        event.respondWith(handleAPIRequest(event.request));
        return;
    }

    // For static assets, try cache first, then network
    event.respondWith(
        caches.match(event.request)
            .then((cachedResponse) => {
                if (cachedResponse) {
                    return cachedResponse;
                }

                return fetch(event.request)
                    .then((networkResponse) => {
                        // Only cache successful responses
                        if (!networkResponse || networkResponse.status !== 200) {
                            return networkResponse;
                        }

                        // Clone the response
                        const responseToCache = networkResponse.clone();

                        caches.open(CACHE_NAME)
                            .then((cache) => {
                                cache.put(event.request, responseToCache);
                            });

                        return networkResponse;
                    })
                    .catch(() => {
                        // Offline fallback for navigation
                        if (event.request.mode === 'navigate') {
                            return caches.match('/index.html');
                        }
                        return null;
                    });
            })
    );
});

// Handle API requests with network-first strategy
async function handleAPIRequest(request) {
    try {
        // Try network first
        const networkResponse = await fetch(request);

        // Cache successful GET responses
        if (request.method === 'GET' && networkResponse.ok) {
            const cache = await caches.open(API_CACHE_NAME);
            const responseToCache = networkResponse.clone();

            // Add timestamp for cache invalidation
            const headers = new Headers(responseToCache.headers);
            headers.append('sw-cache-time', Date.now().toString());

            const cachedResponse = new Response(await responseToCache.blob(), {
                status: responseToCache.status,
                statusText: responseToCache.statusText,
                headers: headers,
            });

            cache.put(request, cachedResponse);
        }

        return networkResponse;

    } catch (error) {
        // Network failed, try cache for GET requests
        if (request.method === 'GET') {
            const cache = await caches.open(API_CACHE_NAME);
            const cachedResponse = await cache.match(request);

            if (cachedResponse) {
                // Check if cache is still valid
                const cacheTime = cachedResponse.headers.get('sw-cache-time');
                if (cacheTime && (Date.now() - parseInt(cacheTime)) < API_CACHE_DURATION) {
                    console.log('[SW] Serving from API cache:', request.url);
                    return cachedResponse;
                }
            }
        }

        // Return error response for failed requests
        return new Response(
            JSON.stringify({
                error: 'Network unavailable',
                offline: true,
            }),
            {
                status: 503,
                headers: { 'Content-Type': 'application/json' },
            }
        );
    }
}

// Handle push notifications
self.addEventListener('push', (event) => {
    console.log('[SW] Push received');

    let data = { title: 'OTTO', body: 'New notification' };

    if (event.data) {
        try {
            data = event.data.json();
        } catch (e) {
            data.body = event.data.text();
        }
    }

    const options = {
        body: data.body,
        icon: '/static/icons/icon-192.png',
        badge: '/static/icons/icon-72.png',
        vibrate: [100, 50, 100],
        data: data,
        actions: [
            { action: 'open', title: 'Open' },
            { action: 'dismiss', title: 'Dismiss' },
        ],
    };

    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
    console.log('[SW] Notification clicked');

    event.notification.close();

    if (event.action === 'dismiss') {
        return;
    }

    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then((windowClients) => {
                // Focus existing window
                for (const client of windowClients) {
                    if ('focus' in client) {
                        return client.focus();
                    }
                }
                // Open new window
                if (clients.openWindow) {
                    return clients.openWindow('/');
                }
            })
    );
});

// Background sync for offline commands
self.addEventListener('sync', (event) => {
    console.log('[SW] Background sync:', event.tag);

    if (event.tag === 'sync-commands') {
        event.waitUntil(syncPendingCommands());
    }
});

async function syncPendingCommands() {
    // Get pending commands from IndexedDB (if implemented)
    // For now, just log
    console.log('[SW] Syncing pending commands...');
}

// Message handling
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'SKIP_WAITING') {
        self.skipWaiting();
    }
});

console.log('[SW] Service Worker loaded');
