const CACHE = "briar-crown-v1.7.9.2.4-tavern-door-focus";
const CORE_ASSETS = [
  "./",
  "./index.html",
  "./manifest.json",
  "./release.json",
  "./assets/items/manifest.json",
  "./icon-192.png",
  "./icon-512.png",
  "./assets/ui/satchel.png",
  "./assets/characters/knight-avatar-v17921.webp",
  "./assets/characters/knight-select-v17921.webp",
  "./assets/characters/ranger-avatar-v17921.webp",
  "./assets/characters/ranger-select-v17921.webp",
  "./assets/characters/wizard-avatar-v17921.webp",
  "./assets/characters/wizard-select-v17921.webp",
  "./assets/characters/rogue-avatar-v17921.webp",
  "./assets/characters/rogue-select-v17921.webp",
  "./assets/characters/druid-avatar-v17921.webp",
  "./assets/characters/druid-select-v17921.webp",
  "./assets/characters/bard-avatar-v17921.webp",
  "./assets/characters/bard-select-v17921.webp",
  "./assets/ui/opening-v1730.webp",
  "./assets/ui/world-map-v1726.png",
  "./assets/ui/rowan-equipment-v1742.webp",
  "./assets/ui/restless-skeleton-v1750.webp",
  "./assets/ui/thorn-hound-v1750.webp",
  "./assets/scenes/square-v17922.webp",
  "./assets/scenes/tavern-approach-v17922.webp",
  "./assets/scenes/tavern-door-v17924.webp",
  "./assets/scenes/tavern-interior-v17922.webp",
  "./assets/scenes/tavern-north-v17923.webp",
  "./assets/scenes/tavern-east-v17923.webp",
  "./assets/scenes/tavern-west-v17923.webp",
  "./assets/scenes/tavern-south-v17923.webp",
  "./assets/scenes/chapel-route-v17922.webp",
  "./assets/scenes/chapel-yard-v17923.webp",
  "./assets/scenes/chapel-approach-v17923.webp",
  "./assets/scenes/old-cemetery-v17923.webp",
  "./assets/scenes/chapel-interior-v17922.webp",
  "./assets/scenes/production-manifest-v17924.json",
  "./assets/scenes/thorn-hedge-pass-day-v1790.webp",
  "./assets/scenes/broken-watch-crossing-v1729.webp",
  "./assets/scenes/outer-gate-approach-day-v1790.webp"
];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(CORE_ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(key => key.startsWith("briar-crown-") && key !== CACHE).map(key => caches.delete(key)))));
  self.clients.claim();
});

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  const isPage = event.request.mode === "navigate" || event.request.destination === "document";
  const isScene = url.pathname.includes("/assets/scenes/") || url.pathname.includes("/assets/ui/world-map-") || url.pathname.includes("/assets/ui/opening-");
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
      if(response.ok){const copy=response.clone(); caches.open(CACHE).then(cache=>cache.put("./index.html",copy));} return response;
    }).catch(()=>caches.match("./index.html")));
    return;
  }
  event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
    if(response.ok){const copy=response.clone(); caches.open(CACHE).then(cache=>cache.put(event.request,copy));} return response;
  })));
});
