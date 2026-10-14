/* HC-1 : service worker — appli installable, page disponible hors connexion, notifications push. */
const CACHE = "hc1-v48";
const SHELL = ["/", "/fx.js", "/character/redrock.js", "/character/face.js", "/logo.png", "/icon-192.png", "/manifest.webmanifest"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).catch(() => {}));
  self.skipWaiting();
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
// réseau d'abord (toujours la dernière version), copie locale seulement si le serveur est injoignable ; jamais les données /api
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method === "GET" && url.hostname === "cdn.jsdelivr.net" && url.pathname.includes("/three@")) {
    e.respondWith(caches.open(CACHE).then(c => c.match(e.request).then(hit => hit || fetch(e.request).then(r => { if (r.ok) c.put(e.request, r.clone()); return r; }))));
    return;
  }
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  e.respondWith(fetch(e.request).then(r => {
    if (r.ok && SHELL.includes(url.pathname)) { const copy = r.clone(); caches.open(CACHE).then(c => c.put(url.pathname, copy)); }
    return r;
  }).catch(() => caches.match(url.pathname).then(r => r || caches.match("/"))));
});

self.addEventListener("push", e => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (_) { d = {title: "RedRock", body: e.data ? e.data.text() : ""}; }
  e.waitUntil(self.registration.showNotification(d.title || "RedRock", {
    body: d.body || "", icon: "/icon-192.png", badge: "/icon-192.png", tag: d.tag || undefined, renotify: !!d.tag,
    data: {url: d.url || "/"},
  }));
});
self.addEventListener("notificationclick", e => {
  e.notification.close();
  const target = (e.notification.data && e.notification.data.url) || "/";
  e.waitUntil(self.clients.matchAll({type: "window", includeUncontrolled: true}).then(list => {
    for (const c of list) if ("focus" in c) { c.navigate && c.url !== new URL(target, location.origin).href && c.navigate(target); return c.focus(); }
    return self.clients.openWindow(target);
  }));
});
