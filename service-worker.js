const CACHE = "briar-crown-v1.7.2.4";
const CORE_ASSETS = [
  "./",
  "./index.html",
  "./manifest.json",
  "./icon-192.png",
  "./icon-512.png",
  "./assets/ui/satchel.png",
  "./assets/ui/world-map-v1724.webp",
  "./assets/scenes/square-v1724.webp",
  "./assets/scenes/production-manifest-v1724.json"
];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(CORE_ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key)))));
  self.clients.claim();
});

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  const isPage = event.request.mode === "navigate" || event.request.destination === "document";
  const isScene = url.pathname.includes("/assets/scenes/") || url.pathname.includes("/assets/ui/world-map-");
  if (isScene) {
    event.respondWith(caches.open(CACHE).then(async cache => {
      const cached = await cache.match(event.request, { ignoreSearch: true });
      const refresh = fetch(event.request).then(response => { if (response.ok) cache.put(event.request, response.clone()); return response; }).catch(()=>null);
      return cached || (await refresh) || Response.error();
    }));
    return;
  }
  if (isPage) {
    event.respondWith(fetch(event.request, { cache: "no-store" }).then(response => {
      const copy=response.clone(); caches.open(CACHE).then(cache=>cache.put("./index.html",copy)); return response;
    }).catch(()=>caches.match("./index.html")));
    return;
  }
  event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
    const copy=response.clone(); caches.open(CACHE).then(cache=>cache.put(event.request,copy)); return response;
  })));
});
