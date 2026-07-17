const CACHE = "briar-crown-v1.7.2.0";
const ASSETS = [
  "./",
  "./index.html",
  "./manifest.json",
  "./icon-192.png",
  "./icon-512.png",
  "./assets/scenes/production-manifest-v1720.json",
  "./assets/scenes/apothecary-approach-v3.webp",
  "./assets/scenes/apothecary-door.webp",
  "./assets/scenes/apothecary-east.webp",
  "./assets/scenes/apothecary-north.webp",
  "./assets/scenes/apothecary-room.webp",
  "./assets/scenes/apothecary-south.webp",
  "./assets/scenes/apothecary-west.webp",
  "./assets/scenes/chapel-approach.webp",
  "./assets/scenes/chapel-road-v1720.webp",
  "./assets/scenes/chapel-yard.webp",
  "./assets/scenes/chapel.webp",
  "./assets/scenes/cottage-cellar.webp",
  "./assets/scenes/cottage-interior-v1720.webp",
  "./assets/scenes/cottage.webp",
  "./assets/scenes/crypt.webp",
  "./assets/scenes/fallen-log-v1720.webp",
  "./assets/scenes/ferry-landing.webp",
  "./assets/scenes/flower-clearing-v1720.webp",
  "./assets/scenes/forest.webp",
  "./assets/scenes/forge-door.webp",
  "./assets/scenes/forge-lane-v1720.webp",
  "./assets/scenes/forge.webp",
  "./assets/scenes/gate.webp",
  "./assets/scenes/hidden-alcove-coins-v1720.webp",
  "./assets/scenes/hidden-alcove-v1720.webp",
  "./assets/scenes/hidden-passage-v1720.webp",
  "./assets/scenes/hut-interior.webp",
  "./assets/scenes/hut.webp",
  "./assets/scenes/kings-road.webp",
  "./assets/scenes/moonwell-v1720.webp",
  "./assets/scenes/old-cemetery.webp",
  "./assets/scenes/square.webp",
  "./assets/scenes/tavern-approach.webp",
  "./assets/scenes/tavern-cellar-passage.webp",
  "./assets/scenes/tavern-cellar-v2.webp",
  "./assets/scenes/tavern-door.webp",
  "./assets/scenes/tavern-east.webp",
  "./assets/scenes/tavern-north.webp",
  "./assets/scenes/tavern-south.webp",
  "./assets/scenes/tavern-west.webp",
  "./assets/scenes/tavern.webp",
  "./assets/scenes/willow-trail-v1720.webp",
  "./assets/ui/satchel.png",
  "./assets/ui/world-map-v1720.webp"
];

self.addEventListener("install", event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(ASSETS)));
  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(key => key !== CACHE).map(key => caches.delete(key))))
  );
  self.clients.claim();
});

self.addEventListener("fetch", event => {
  if (event.request.method !== "GET") return;
  const url = new URL(event.request.url);
  const isPage = event.request.mode === "navigate" || event.request.destination === "document";
  const isScene = url.pathname.includes("/assets/scenes/");
  if (isPage || isScene) {
    event.respondWith(
      fetch(event.request, { cache: "no-store" }).then(response => {
        const copy = response.clone();
        caches.open(CACHE).then(cache => cache.put(event.request, copy));
        return response;
      }).catch(() => caches.match(event.request).then(cached => cached || (isPage ? caches.match("./index.html") : Response.error())))
    );
    return;
  }
  event.respondWith(
    caches.match(event.request).then(cached => cached || fetch(event.request).then(response => {
      const copy = response.clone();
      caches.open(CACHE).then(cache => cache.put(event.request, copy));
      return response;
    }).catch(() => caches.match("./index.html")))
  );
});
