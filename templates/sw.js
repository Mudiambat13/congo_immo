{% load static %}
/* Congo Immo : service worker. Les annonces déjà consultées restent lisibles sans réseau. */
const V = "ci-v2";
const STATIQUE = V + "-static", PAGES = V + "-pages", IMAGES = V + "-images";
const PRECACHE = ["{% url 'listings:hors_ligne' %}", "{% static 'css/app.css' %}", "{% static 'js/app.js' %}", "{% static 'js/plus.js' %}", "{% static 'icons/icon-192.png' %}"];
const FICHE = /^\/bien\/[^/]+\/$/;

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(STATIQUE).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => !k.startsWith(V)).map((k) => caches.delete(k)))).then(() => self.clients.claim()));
});

async function limiter(nom, max) {
  const c = await caches.open(nom), ks = await c.keys();
  if (ks.length > max) { await c.delete(ks[0]); limiter(nom, max); }
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== location.origin) return;
  const p = url.pathname;
  if (p.startsWith("/admin/") || p.startsWith("/compte/") || p.startsWith("/api/") || p === "/sw.js") return;

  if (p.startsWith("/static/")) {
    e.respondWith(caches.match(req).then((r) => r || fetch(req).then((res) => { const cp = res.clone(); caches.open(STATIQUE).then((c) => c.put(req, cp)); return res; })));
    return;
  }
  if (p.startsWith("/media/")) {
    e.respondWith(caches.open(IMAGES).then((c) => c.match(req).then((r) => {
      const reseau = fetch(req).then((res) => { if (res.ok) { c.put(req, res.clone()); limiter(IMAGES, 120); } return res; }).catch(() => r);
      return r || reseau;
    })));
    return;
  }
  if (req.mode === "navigate") {
    e.respondWith(fetch(req).then((res) => {
      if (res.ok && FICHE.test(p)) { const cp = res.clone(); caches.open(PAGES).then((c) => { c.put(req, cp); limiter(PAGES, 40); }); }
      return res;
    }).catch(() => caches.match(req).then((r) => r || caches.match("{% url 'listings:hors_ligne' %}"))));
  }
});
