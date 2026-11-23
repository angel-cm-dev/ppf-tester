/* Service worker: la app funciona sin conexión después de la primera visita. */
const VERSION = "ppf-app-3";
const PY = ["ppf_format", "sig", "dsp", "modelos", "sonido", "motor", "grooves", "estilos",
  "analisis", "compat", "importar_wav", "demo", "web_api"];
const APP = ["./", "index.html", "app.css?v=3", "app.js?v=1", "audio.js?v=1", "worker.js?v=1",
  "manifest.webmanifest", "icon-192.png", "icon-512.png", "apple-touch-icon.png",
  ...PY.map((m) => `py/${m}.py?v=1`)];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(APP)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== VERSION && k !== "pyodide").map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET") return;
  // Pyodide (CDN, versión fija): primero la caché
  if (url.hostname === "cdn.jsdelivr.net" && url.pathname.startsWith("/pyodide/")) {
    e.respondWith(caches.open("pyodide").then(async (c) => {
      const hit = await c.match(e.request);
      if (hit) return hit;
      const r = await fetch(e.request);
      if (r.ok) await c.put(e.request, r.clone());
      return r;
    }));
    return;
  }
  if (url.origin !== location.origin) return;
  // la app: red primero (para recibir mejoras), caché si no hay conexión
  e.respondWith(fetch(e.request).then((r) => {
    if (r.ok) { const copia = r.clone(); caches.open(VERSION).then((c) => c.put(e.request, copia)); }
    return r;
  }).catch(() => caches.match(e.request, { ignoreSearch: false }).then((r) => r || caches.match("index.html"))));
});
