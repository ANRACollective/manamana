// Mana-Mana service worker
// Bump this string on any change so old clients update.
const VERSION = 'v1-2026-07-08';
const SHELL = 'mm-shell-' + VERSION;
const DATA  = 'mm-data-'  + VERSION;

// App shell: everything needed to render an offline screen.
const SHELL_URLS = [
  '/',
  '/index.html',
  '/manifest.webmanifest',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
  '/icons/icon-maskable-512.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL).then((cache) => cache.addAll(SHELL_URLS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k !== SHELL && k !== DATA).map(k => caches.delete(k)));
    await self.clients.claim();
  })());
});

// Decide how to handle a request.
// - Navigations: network-first with app-shell fallback.
// - Same-origin JSON data feeds: stale-while-revalidate.
// - Icons / manifest: cache-first.
// - Everything else (Supabase, third-party APIs, fonts): pass through, no interception.
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  const sameOrigin = url.origin === self.location.origin;

  if (req.mode === 'navigate') {
    event.respondWith(networkFirstShell(req));
    return;
  }

  if (sameOrigin && (url.pathname === '/manifest.webmanifest' || url.pathname.startsWith('/icons/'))) {
    event.respondWith(cacheFirst(req, SHELL));
    return;
  }

  if (sameOrigin && (url.pathname.endsWith('.json') || url.pathname === '/station_ridership.json')) {
    event.respondWith(staleWhileRevalidate(req, DATA));
    return;
  }

  // Everything else: let the browser handle it directly.
});

async function networkFirstShell(req) {
  try {
    const fresh = await fetch(req);
    const cache = await caches.open(SHELL);
    cache.put('/index.html', fresh.clone()).catch(() => {});
    return fresh;
  } catch (_) {
    const cached = await caches.match('/index.html');
    if (cached) return cached;
    return new Response('offline', { status: 503, statusText: 'Offline' });
  }
}

async function cacheFirst(req, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);
  if (cached) return cached;
  const fresh = await fetch(req);
  if (fresh && fresh.ok) cache.put(req, fresh.clone()).catch(() => {});
  return fresh;
}

async function staleWhileRevalidate(req, cacheName) {
  const cache = await caches.open(cacheName);
  const cached = await cache.match(req);
  const network = fetch(req).then((res) => {
    if (res && res.ok) cache.put(req, res.clone()).catch(() => {});
    return res;
  }).catch(() => null);
  return cached || (await network) || new Response('offline', { status: 503 });
}
