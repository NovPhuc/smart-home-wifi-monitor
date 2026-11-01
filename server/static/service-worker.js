/* An Tâm Home — service worker (app shell).
 *
 * Chiến lược: network-first cho tài nguyên tĩnh, bỏ qua hoàn toàn /api/*
 * (dữ liệu cảm biến không bao giờ được phục vụ từ cache).
 *
 * Sửa so với bản cũ:
 *  - APP_SHELL trỏ tới /static/app.js (ba file app*.js đã gộp thành một).
 *  - Chỉ ghi cache khi phản hồi hợp lệ; bản cũ cache cả 404/500.
 *  - Chỉ trả về trang chủ khi điều hướng thất bại. Bản cũ trả HTML cho mọi
 *    request lỗi, kể cả CSS/JS — trình duyệt nhận HTML thay cho script.
 */
const CACHE_NAME = 'an-tam-home-v5';
const APP_SHELL = [
  '/',
  '/static/style.css',
  '/static/mobile.css',
  '/static/account.css',
  '/static/app.js',
  '/static/manifest.webmanifest',
  '/static/icons/app-icon.svg'
];

self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE_NAME).then(cache => cache.addAll(APP_SHELL)));
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const request = event.request;
  const url = new URL(request.url);

  // Chỉ xử lý GET cùng nguồn; API luôn đi thẳng ra mạng.
  if (request.method !== 'GET') return;
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return;

  event.respondWith((async () => {
    try {
      const response = await fetch(request);
      if (response.ok) {
        const copy = response.clone();
        caches.open(CACHE_NAME).then(cache => cache.put(request, copy)).catch(() => {});
      }
      return response;
    } catch (error) {
      const cached = await caches.match(request);
      if (cached) return cached;
      if (request.mode === 'navigate') {
        const shell = await caches.match('/');
        if (shell) return shell;
      }
      throw error;
    }
  })());
});
