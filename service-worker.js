const CACHE = "briar-crown-v1.7.2.2";
const ASSETS = [
  "./",
  "./index.html",
  "./manifest.json",
  "./icon-192.png",
  "./icon-512.png",
  "./assets/scenes/apothecary-approach-v1722.webp",
  "./assets/scenes/apothecary-back-room-v1722.webp",
  "./assets/scenes/apothecary-center-v1722.webp",
  "./assets/scenes/apothecary-door-v1722.webp",
  "./assets/scenes/apothecary-east-v1722.webp",
  "./assets/scenes/apothecary-north-v1722.webp",
  "./assets/scenes/apothecary-south-v1722.webp",
  "./assets/scenes/apothecary-west-v1722.webp",
  "./assets/scenes/chapel-approach-v1722.webp",
  "./assets/scenes/chapel-crypt-v1722.webp",
  "./assets/scenes/chapel-interior-v1722.webp",
  "./assets/scenes/chapel-road-v1722.webp",
  "./assets/scenes/chapel-yard-v1722.webp",
  "./assets/scenes/collapsed-alcove-open-v1722.webp",
  "./assets/scenes/collapsed-alcove-v1722.webp",
  "./assets/scenes/east-road-v1722.webp",
  "./assets/scenes/fallen-log-v1722.webp",
  "./assets/scenes/flower-clearing-v1722.webp",
  "./assets/scenes/forest-edge-v1722.webp",
  "./assets/scenes/forge-door-v1722.webp",
  "./assets/scenes/forge-interior-v1722.webp",
  "./assets/scenes/forge-lane-v1722.webp",
  "./assets/scenes/hidden-passage-v1722.webp",
  "./assets/scenes/ironthorn-gate-v1722.webp",
  "./assets/scenes/kings-road-v1722.webp",
  "./assets/scenes/moonfen-ferry-landing-v1722.webp",
  "./assets/scenes/moonfen-hut-exterior-v1722.webp",
  "./assets/scenes/moonfen-hut-interior-v1722.webp",
  "./assets/scenes/moonwell-v1722.webp",
  "./assets/scenes/old-cemetery-v1722.webp",
  "./assets/scenes/square-v1722.webp",
  "./assets/scenes/tavern-approach-v1722.webp",
  "./assets/scenes/tavern-cellar-passage-v1722.webp",
  "./assets/scenes/tavern-cellar-v1722.webp",
  "./assets/scenes/tavern-center-v1722.webp",
  "./assets/scenes/tavern-door-v1722.webp",
  "./assets/scenes/tavern-east-v1722.webp",
  "./assets/scenes/tavern-north-v1722.webp",
  "./assets/scenes/tavern-south-v1722.webp",
  "./assets/scenes/tavern-west-v1722.webp",
  "./assets/scenes/whispering-forest-v1722.webp",
  "./assets/scenes/willow-trail-v1722.webp",
  "./assets/scenes/witch-cottage-cellar-v1722.webp",
  "./assets/scenes/witch-cottage-exterior-v1722.webp",
  "./assets/scenes/witch-cottage-interior-v1722.webp",
  "./assets/ui/satchel.png",
  "./assets/ui/world-map-v1722.webp",
  "./assets/scenes/production-manifest-v1722.json"
];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)));
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
  if (isPage || isScene) {
    event.respondWith(fetch(event.request, { cache: "no-store" }).then(response => {
      const copy = response.clone(); caches.open(CACHE).then(cache => cache.put(event.request, copy)); return response;
    }).catch(() => caches.match(event.request).then(cached => cached || (isPage ? caches.match("./index.html") : Response.error()))));
    return;
  }
  event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
    const copy = response.clone(); caches.open(CACHE).then(cache => cache.put(event.request, copy)); return response;
  }).catch(() => caches.match("./index.html"))));
});
