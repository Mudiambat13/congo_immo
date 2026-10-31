/* Congo Immo : JavaScript léger, chaque fonction est facultative (le site marche sans). */
(function () {
  "use strict";
  var TUILES = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  var ATTRIB = "© contributeurs OpenStreetMap";
  var CENTRE_RDC = [-4.0, 21.8];

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function nombre(v) {
    var n = parseFloat(String(v || "").replace(",", "."));
    return isNaN(n) ? null : n;
  }
  function creerCarte(id, centre, zoom) {
    if (!window.L) return null;
    var carte = L.map(id, { scrollWheelZoom: false }).setView(centre, zoom);
    L.tileLayer(TUILES, { maxZoom: 19, attribution: ATTRIB }).addTo(carte);
    return carte;
  }

  /* Menu mobile */
  var bouton = document.querySelector("[data-menu]");
  if (bouton) {
    bouton.addEventListener("click", function () {
      var nav = document.getElementById(bouton.getAttribute("aria-controls"));
      var ouvert = nav.classList.toggle("is-ouverte");
      bouton.setAttribute("aria-expanded", ouvert ? "true" : "false");
    });
  }

  /* Favoris sans rechargement */
  document.addEventListener("submit", function (e) {
    var btn = e.target.querySelector && e.target.querySelector("[data-favori]");
    if (!btn || !window.fetch) return;
    e.preventDefault();
    var jeton = e.target.querySelector("[name=csrfmiddlewaretoken]").value;
    fetch(e.target.action, { method: "POST", headers: { "X-CSRFToken": jeton, "X-Requested-With": "fetch" }, credentials: "same-origin" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        btn.classList.toggle("is-on", d.favori);
        btn.setAttribute("aria-pressed", d.favori ? "true" : "false");
      })
      .catch(function () { e.target.submit(); });
  });

  /* Galerie photo */
  var galerie = document.querySelector("[data-galerie]");
  if (galerie) {
    var grande = galerie.querySelector("[data-galerie-grande]");
    galerie.querySelectorAll("[data-galerie-vignette]").forEach(function (v, i) {
      if (i === 0) v.classList.add("is-actif");
      v.addEventListener("click", function () {
        grande.src = v.dataset.src;
        grande.parentNode.href = v.dataset.src;
        grande.alt = "Photo " + (i + 1);
        galerie.querySelectorAll(".is-actif").forEach(function (x) { x.classList.remove("is-actif"); });
        v.classList.add("is-actif");
      });
    });
  }

  /* Copier le lien */
  document.querySelectorAll("[data-copier]").forEach(function (b) {
    b.addEventListener("click", function () {
      var url = b.dataset.copier, span = b.querySelector("span");
      var ok = function () { if (span) { var t = span.textContent; span.textContent = "Lien copié"; setTimeout(function () { span.textContent = t; }, 2000); } };
      if (navigator.clipboard) navigator.clipboard.writeText(url).then(ok);
      else { window.prompt("Copiez ce lien :", url); }
    });
  });

  /* Comptage des appels */
  document.querySelectorAll("[data-appel]").forEach(function (a) {
    a.addEventListener("click", function () { if (window.fetch) fetch(a.dataset.appel, { keepalive: true, credentials: "same-origin" }); });
  });

  /* Carte d'une annonce */
  var carteBien = document.getElementById("carte-bien");
  if (carteBien && window.L) {
    var la = nombre(carteBien.dataset.lat), lo = nombre(carteBien.dataset.lng);
    if (la !== null && lo !== null) {
      var c1 = creerCarte("carte-bien", [la, lo], 16);
      L.marker([la, lo]).addTo(c1).bindPopup(esc(carteBien.dataset.titre));
      c1.once("focus", function () { c1.scrollWheelZoom.enable(); });
    }
  }

  /* Carte des résultats */
  var carteRes = document.getElementById("carte-resultats");
  if (carteRes && window.L && window.fetch) {
    var c2 = creerCarte("carte-resultats", CENTRE_RDC, 5);
    fetch(carteRes.dataset.geojson).then(function (r) { return r.json(); }).then(function (data) {
      var points = [];
      data.features.forEach(function (f) {
        var p = f.properties, ll = [f.geometry.coordinates[1], f.geometry.coordinates[0]];
        var icone = L.divIcon({ className: "", html: '<div class="repere repere--' + (p.location ? "location" : "vente") + '" style="width:26px;height:26px"></div>', iconSize: [26, 26], iconAnchor: [13, 26], popupAnchor: [0, -26] });
        var html = '<div class="popup-bien">' + (p.image ? '<img src="' + esc(p.image) + '" alt="">' : "") +
          "<b>" + esc(p.prix) + (p.location ? " par mois" : "") + "</b>" + esc(p.objet) + "<br>" + esc(p.lieu) +
          (p.detail ? "<br>" + esc(p.detail) : "") + '<br><a href="' + esc(p.url) + '">Voir l\'annonce</a></div>';
        L.marker(ll, { icon: icone, title: p.objet }).addTo(c2).bindPopup(html);
        points.push(ll);
      });
      if (points.length) c2.fitBounds(points, { padding: [40, 40], maxZoom: 15 });
    });
  }

  /* Formulaire de publication */
  var form = document.querySelector("[data-formulaire-bien]");
  if (!form) return;
  var q = function (s) { return form.querySelector(s); };

  var radios = form.querySelectorAll("input[name=type_annonce]");
  var categorie = q("#id_categorie");
  var labelPrix = q("label[for=id_prix]");
  var titreCond = q("[data-titre-conditions]");
  var gpsMention = q("[data-gps-obligatoire]");

  function typeActuel() {
    var r = Array.prototype.find.call(radios, function (x) { return x.checked; });
    return r ? r.value : "location";
  }
  function majType() {
    var t = typeActuel();
    form.querySelectorAll("[data-only]").forEach(function (el) { el.hidden = el.dataset.only !== t; });
    if (titreCond) titreCond.textContent = t === "location" ? "Loyer et garantie" : "Prix et documents";
    if (labelPrix && labelPrix.firstChild) labelPrix.firstChild.textContent = t === "location" ? "Loyer mensuel" : "Prix de vente";
    if (gpsMention) gpsMention.textContent = t === "vente" ? "(obligatoire pour une vente)" : "(conseillée pour une location)";
  }
  function majCategorie() {
    var bloc = q("[data-logement]");
    if (!bloc || !categorie) return;
    bloc.hidden = ["parcelle", "concession"].indexOf(categorie.value) !== -1;
  }
  radios.forEach(function (r) { r.addEventListener("change", majType); });
  if (categorie) categorie.addEventListener("change", majCategorie);
  majType(); majCategorie();

  /* Province puis ville puis quartiers */
  var province = q("#id_province"), ville = q("#id_ville"), liste = document.getElementById("liste-quartiers");
  var toutes = Array.prototype.map.call(ville.options, function (o) {
    return { v: o.value, t: o.textContent, p: o.dataset.province, lat: o.dataset.lat, lng: o.dataset.lng };
  });
  function filtrerVilles() {
    var p = province.value, courante = ville.value;
    ville.innerHTML = "";
    toutes.forEach(function (o) {
      if (o.v && p && o.p !== p) return;
      var op = new Option(o.t, o.v);
      if (o.p) { op.dataset.province = o.p; op.dataset.lat = o.lat; op.dataset.lng = o.lng; }
      ville.add(op);
    });
    if (Array.prototype.some.call(ville.options, function (o) { return o.value === courante; })) ville.value = courante;
  }
  function chargerQuartiers() {
    if (!ville.value || !window.fetch) { liste.innerHTML = ""; return; }
    fetch("/api/quartiers/?ville=" + encodeURIComponent(ville.value)).then(function (r) { return r.json(); }).then(function (d) {
      liste.innerHTML = d.quartiers.map(function (n) { return '<option value="' + esc(n) + '">'; }).join("");
    });
  }
  filtrerVilles();
  if (ville.value && !province.value) {
    var sel = ville.options[ville.selectedIndex];
    if (sel && sel.dataset.province) province.value = sel.dataset.province;
  }
  chargerQuartiers();
  province.addEventListener("change", filtrerVilles);

  /* Sélecteur GPS */
  var lat = q("#id_latitude"), lng = q("#id_longitude");
  var carte = creerCarte("carte-formulaire", CENTRE_RDC, 5);
  var repere = null;
  function remplir(a, b) { lat.value = a.toFixed(6); lng.value = b.toFixed(6); }
  function poser(a, b, zoom) {
    if (!carte) return;
    if (repere) repere.setLatLng([a, b]);
    else {
      repere = L.marker([a, b], { draggable: true }).addTo(carte);
      repere.on("dragend", function () { var p = repere.getLatLng(); remplir(p.lat, p.lng); });
    }
    remplir(a, b);
    if (zoom) carte.setView([a, b], zoom);
  }
  if (carte) {
    var a0 = nombre(lat.value), b0 = nombre(lng.value);
    if (a0 !== null && b0 !== null) poser(a0, b0, 16);
    carte.on("click", function (e) { poser(e.latlng.lat, e.latlng.lng); });
    var pos = q("[data-ma-position]");
    if (pos) pos.addEventListener("click", function () {
      if (!navigator.geolocation) { alert("Votre appareil ne permet pas de se géolocaliser."); return; }
      pos.disabled = true;
      navigator.geolocation.getCurrentPosition(function (p) { pos.disabled = false; poser(p.coords.latitude, p.coords.longitude, 17); },
        function () { pos.disabled = false; alert("Position introuvable. Autorisez la localisation ou cliquez sur la carte."); },
        { enableHighAccuracy: true, timeout: 15000 });
    });
    var eff = q("[data-effacer-position]");
    if (eff) eff.addEventListener("click", function () { if (repere) { carte.removeLayer(repere); repere = null; } lat.value = ""; lng.value = ""; });
  }
  function centrerVille() {
    var o = ville.options[ville.selectedIndex];
    if (o && o.dataset.province) {
      if (!province.value) province.value = o.dataset.province;
      if (carte && !repere) carte.setView([nombre(o.dataset.lat), nombre(o.dataset.lng)], 12);
    }
    chargerQuartiers();
  }
  ville.addEventListener("change", centrerVille);
  if (carte && ville.value && !repere) {
    var o2 = ville.options[ville.selectedIndex];
    if (o2 && o2.dataset.lat) carte.setView([nombre(o2.dataset.lat), nombre(o2.dataset.lng)], 12);
  }

  /* Photos : aperçu et compteur */
  var fichiers = q("#id_photos_nouvelles"), apercu = q("[data-apercu]"), compteur = q("[data-compteur-photos]");
  function majPhotos() {
    var max = parseInt(compteur.dataset.max, 10), exist = parseInt(compteur.dataset.existantes, 10) || 0;
    var retirees = form.querySelectorAll("[data-photo-existante]:checked").length;
    var nouvelles = fichiers.files ? fichiers.files.length : 0;
    var total = exist - retirees + nouvelles;
    apercu.innerHTML = "";
    Array.prototype.forEach.call(fichiers.files || [], function (f) {
      var li = document.createElement("li"), img = document.createElement("img");
      img.src = URL.createObjectURL(f); img.alt = f.name; img.onload = function () { URL.revokeObjectURL(img.src); };
      li.appendChild(img); apercu.appendChild(li);
    });
    compteur.textContent = total + " photo" + (total > 1 ? "s" : "") + " sur " + max + " au maximum";
    compteur.classList.toggle("is-trop", total > max);
    if (total > max) compteur.textContent += ". Retirez " + (total - max) + " photo" + (total - max > 1 ? "s" : "") + ".";
  }
  if (fichiers && compteur) {
    fichiers.addEventListener("change", majPhotos);
    form.querySelectorAll("[data-photo-existante]").forEach(function (c) { c.addEventListener("change", majPhotos); });
    majPhotos();
  }
})();
