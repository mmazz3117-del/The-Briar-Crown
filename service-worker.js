const CACHE = "briar-crown-v1.6.9.3";
const ASSETS = [
  "./",
  "./index.html",
  "./manifest.json",
  "./icon-192.png",
  "./icon-512.png",
  "./assets/scenes/square.webp",
  "./assets/scenes/tavern.webp",
  "./assets/scenes/tavern-north.webp",
  "./assets/scenes/tavern-east.webp",
  "./assets/scenes/tavern-west.webp",
  "./assets/scenes/tavern-south.webp",
  "./assets/scenes/tavern-approach.webp",
  "./assets/scenes/tavern-door.webp",
  "./assets/scenes/apothecary-approach-v3.webp",
  "./assets/scenes/forge.webp",
  "./assets/scenes/forge-lane.webp",
  "./assets/scenes/forge-door.webp",
  "./assets/scenes/chapel-yard.webp",
  "./assets/scenes/chapel-approach.webp",
  "./assets/scenes/old-cemetery.webp",
  "./assets/scenes/chapel.webp",
  "./assets/scenes/kings-road.webp",
  "./assets/scenes/apothecary-door.webp",
  "./assets/scenes/apothecary-room.webp",
  "./assets/scenes/apothecary-north.webp",
  "./assets/scenes/apothecary-east.webp",
  "./assets/scenes/apothecary-west.webp",
  "./assets/scenes/apothecary-south.webp",
  "./assets/scenes/forest.webp",
  "./assets/scenes/cottage.webp",
  "./assets/scenes/moonfen.webp",
  "./assets/scenes/crypt.webp",
  "./assets/scenes/gate.webp",
  "./assets/scenes/forge-lane-v2.webp",
  "./assets/scenes/cottage-interior.webp",
  "./assets/scenes/cottage-cellar.webp",
  "./assets/scenes/moonwell.webp",
  "./assets/scenes/ferry-landing.webp",
  "./assets/scenes/hut.webp",
  "./assets/scenes/hut-interior.webp",
  "./assets/scenes/tavern-cellar-v2.webp",
  "./assets/scenes/tavern-cellar-passage.webp",
  "./assets/scenes/willow-trail.webp",
  "./assets/scenes/flower-clearing.webp",
  "./assets/scenes/fallen-log.webp",
  "./assets/scenes/moonwell-v2.webp",
  "./assets/scenes/secret-tunnel.webp"
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
    // Network-first for the app page and scene artwork. This ensures new builds
    // and replacement paintings appear immediately, with cached files offline.
    event.respondWith(
      fetch(event.request, { cache: "no-store" }).then(response => {
        const copy = response.clone();
        caches.open(CACHE).then(cache => cache.put(event.request, copy));
        return response;
      }).catch(() =>
        caches.match(event.request).then(cached => cached || (isPage ? caches.match("./index.html") : Response.error()))
      )
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
