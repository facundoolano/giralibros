// Minimal service worker for PWA installation
// No offline caching - just satisfies PWA requirements

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});
