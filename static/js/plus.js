/* Congo Immo v2 : thème, comparateur, visionneuse photo, « près de moi », application installable, aides à la saisie. */
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var csrf = function () { var m = $('meta[name="csrf-token"]'); return m ? m.content : ""; };

  function toast(msg) {
    var zone = $("[data-toasts]");
    if (!zone) return;
    var t = document.createElement("div");
    t.className = "toast";
    t.textContent = msg;
    zone.appendChild(t);
    setTimeout(function () { t.classList.add("is-sortie"); setTimeout(function () { t.remove(); }, 320); }, 3800);
  }

  /* Thème clair / sombre */
  var racine = document.documentElement;
  function themeActuel() {
    if (racine.dataset.theme) return racine.dataset.theme;
    return window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  $$("[data-theme-toggle]").forEach(function (b) {
    b.addEventListener("click", function () {
      var n = themeActuel() === "dark" ? "light" : "dark";
      racine.dataset.theme = n;
      try { localStorage.setItem("theme", n); } catch (e) {}
    });
  });

  /* Comparateur (3 biens au maximum) */
  var barre = $("[data-barre-comparer]");
  function majBarre(n) {
    if (!barre) return;
    barre.hidden = n === 0;
    $("[data-compare-n]", barre).textContent = n;
    $("[data-compare-s]", barre).textContent = n > 1 ? "s" : "";
  }
  document.addEventListener("click", function (e) {
    var b = e.target.closest("[data-comparer]");
    if (!b || !window.fetch) return;
    e.preventDefault();
    e.stopPropagation();
    var ref = b.dataset.comparer;
    fetch("/comparer/" + encodeURIComponent(ref) + "/", { method: "POST", credentials: "same-origin", headers: { "X-CSRFToken": csrf(), "X-Requested-With": "fetch" } })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (x) {
        if (!x.ok) { toast(x.d.erreur || "Impossible d'ajouter ce bien."); return; }
        $$('[data-comparer="' + ref + '"]').forEach(function (el) {
          el.classList.toggle("is-on", x.d.actif);
          el.setAttribute("aria-pressed", x.d.actif ? "true" : "false");
        });
        majBarre(x.d.n);
        toast(x.d.actif ? "Ajouté à la comparaison" : "Retiré de la comparaison");
      })
      .catch(function () { toast("Connexion impossible. Réessayez."); });
  });

  /* Visionneuse photo plein écran */
  var galerie = $("[data-galerie]");
  if (galerie && galerie.dataset.photos) {
    var photos = [];
    try { photos = JSON.parse(galerie.dataset.photos); } catch (e) {}
    if (photos.length) {
      var lb = document.createElement("div");
      lb.className = "lightbox";
      lb.hidden = true;
      lb.setAttribute("role", "dialog");
      lb.setAttribute("aria-modal", "true");
      lb.setAttribute("aria-label", "Photos du bien");
      lb.innerHTML = '<div class="lightbox__haut"><span class="lightbox__compte" aria-live="polite"></span>' +
        '<button type="button" class="lightbox__fermer" aria-label="Fermer"><svg class="ic" width="26" height="26" aria-hidden="true"><use href="#i-close"/></svg></button></div>' +
        '<div class="lightbox__scene"><button type="button" class="lightbox__nav lightbox__nav--g" aria-label="Photo précédente"><svg class="ic" width="30" height="30" aria-hidden="true"><use href="#i-gauche"/></svg></button>' +
        '<img class="lightbox__img" alt="">' +
        '<button type="button" class="lightbox__nav lightbox__nav--d" aria-label="Photo suivante"><svg class="ic" width="30" height="30" aria-hidden="true"><use href="#i-droite"/></svg></button></div>';
      document.body.appendChild(lb);
      var img = $(".lightbox__img", lb), compte = $(".lightbox__compte", lb), i = 0, avant = null;
      var aff = function (n) {
        i = (n + photos.length) % photos.length;
        img.src = photos[i];
        img.alt = "Photo " + (i + 1) + " sur " + photos.length;
        compte.textContent = (i + 1) + " / " + photos.length;
      };
      var ouvrir = function (n) { avant = document.activeElement; aff(n); lb.hidden = false; document.body.classList.add("lb-ouvert"); $(".lightbox__fermer", lb).focus(); };
      var fermer = function () { lb.hidden = true; document.body.classList.remove("lb-ouvert"); if (avant && avant.focus) avant.focus(); };
      $$("[data-lightbox-ouvrir]").forEach(function (a) {
        a.addEventListener("click", function (e) { e.preventDefault(); ouvrir(parseInt(galerie.dataset.courant || "0", 10)); });
      });
      $$("[data-galerie-vignette]").forEach(function (v) {
        v.addEventListener("click", function () { galerie.dataset.courant = v.dataset.index; });
      });
      $(".lightbox__fermer", lb).addEventListener("click", fermer);
      $(".lightbox__nav--g", lb).addEventListener("click", function () { aff(i - 1); });
      $(".lightbox__nav--d", lb).addEventListener("click", function () { aff(i + 1); });
      document.addEventListener("keydown", function (e) {
        if (lb.hidden) return;
        if (e.key === "Escape") fermer();
        else if (e.key === "ArrowLeft") aff(i - 1);
        else if (e.key === "ArrowRight") aff(i + 1);
        else if (e.key === "Tab") {
          var f = $$("button", lb), premier = f[0], dernier = f[f.length - 1];
          if (e.shiftKey && document.activeElement === premier) { e.preventDefault(); dernier.focus(); }
          else if (!e.shiftKey && document.activeElement === dernier) { e.preventDefault(); premier.focus(); }
        }
      });
      var x0 = null;
      lb.addEventListener("touchstart", function (e) { x0 = e.touches[0].clientX; }, { passive: true });
      lb.addEventListener("touchend", function (e) {
        if (x0 === null) return;
        var dx = e.changedTouches[0].clientX - x0;
        if (Math.abs(dx) > 50) aff(i + (dx < 0 ? 1 : -1));
        x0 = null;
      });
    }
  }

  /* Partage natif (WhatsApp, SMS, e-mail...) quand le téléphone le permet */
  $$("[data-partager]").forEach(function (a) {
    a.addEventListener("click", function (e) {
      if (!navigator.share) return;
      e.preventDefault();
      navigator.share({ title: a.dataset.titre, url: a.dataset.url }).catch(function () {});
    });
  });

  /* Près de moi */
  function localiser(ok) {
    if (!navigator.geolocation) { toast("Votre appareil ne permet pas de vous localiser."); return; }
    toast("Recherche de votre position...");
    navigator.geolocation.getCurrentPosition(ok, function () {
      toast("Position introuvable. Autorisez la localisation dans votre navigateur.");
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 });
  }
  $$("[data-pres-de-moi]").forEach(function (b) {
    b.addEventListener("click", function () {
      var f = b.closest("form");
      localiser(function (p) {
        f.elements.lat.value = p.coords.latitude.toFixed(6);
        f.elements.lng.value = p.coords.longitude.toFixed(6);
        f.submit();
      });
    });
  });
  $$("[data-pres-de-moi-accueil]").forEach(function (b) {
    b.addEventListener("click", function () {
      localiser(function (p) { location.href = "/biens/?lat=" + p.coords.latitude.toFixed(6) + "&lng=" + p.coords.longitude.toFixed(6) + "&rayon=10"; });
    });
  });

  /* Application installable et mode hors ligne */
  var invite = null;
  var boutonsInstall = $$("[data-installer]");
  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    invite = e;
    boutonsInstall.forEach(function (b) { b.hidden = false; });
  });
  boutonsInstall.forEach(function (b) {
    b.addEventListener("click", function () {
      if (!invite) return;
      invite.prompt();
      invite.userChoice.then(function () { invite = null; boutonsInstall.forEach(function (x) { x.hidden = true; }); });
    });
  });
  window.addEventListener("appinstalled", function () { boutonsInstall.forEach(function (x) { x.hidden = true; }); toast("Application installée"); });
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () { navigator.serviceWorker.register("/sw.js").catch(function () {}); });
  }
  window.addEventListener("offline", function () { toast("Hors ligne : les annonces déjà ouvertes restent disponibles."); });
  window.addEventListener("online", function () { toast("Connexion rétablie"); });

  /* Formulaire de publication : texte automatique et prix du marché */
  var f = $("[data-formulaire-bien]");
  if (!f) return;
  var val = function (n) { var e = f.elements[n]; return e && e.value ? e.value.trim() : ""; };
  var etiquette = function (sel) { var o = sel && sel.options[sel.selectedIndex]; return o && o.value ? o.textContent.trim() : ""; };
  var typeAnnonce = function () { var r = f.querySelector("input[name=type_annonce]:checked"); return r ? r.value : "location"; };
  var liste = function (a) { return a.length > 1 ? a.slice(0, -1).join(", ") + " et " + a[a.length - 1] : a[0] || ""; };

  var bouton = $("[data-rediger]");
  if (bouton) bouton.addEventListener("click", function () {
    var type = typeAnnonce(), cat = etiquette(f.elements.categorie).toLowerCase(), objet = val("objet");
    var ch = val("chambres"), sa = val("salons"), sn = val("sanitaires"), sup = val("superficie"), devise = val("devise") === "CDF" ? "FC" : "$";
    var piec = [];
    if (ch && ch !== "0") piec.push(ch + (ch === "1" ? " chambre" : " chambres"));
    if (sa && sa !== "0") piec.push(sa + (sa === "1" ? " salon" : " salons"));
    if (sn && sn !== "0") piec.push(sn + (sn === "1" ? " sanitaire" : " sanitaires"));
    var lieu = [val("quartier_nom"), etiquette(f.elements.ville)].filter(Boolean).join(", ");
    var equip = $$("input[name=equipements]:checked", f).map(function (c) { return c.parentNode.textContent.trim().toLowerCase(); });
    var intro = objet || (type === "location" ? "Bien à louer" : "Bien à vendre");
    if (cat && intro.toLowerCase().indexOf(cat) === -1) intro += " (" + cat + ")";
    if (piec.length) intro += " comprenant " + liste(piec);
    if (sup) intro += (piec.length ? ", sur " : " de ") + sup + " m²";
    if (lieu) intro += ", situé à " + lieu;
    if (val("adresse")) intro += " (" + val("adresse") + ")";
    var texte = [intro + "."];
    if (equip.length) texte.push("Équipements : " + equip.join(", ") + ".");
    if (val("prix")) {
      if (type === "location") texte.push("Loyer : " + val("prix") + " " + devise + " par mois" + (val("garantie_mois") ? ", garantie de " + val("garantie_mois") + " mois." : "."));
      else texte.push("Prix demandé : " + val("prix") + " " + devise + "." + (etiquette(f.elements.type_document) ? " Document disponible : " + etiquette(f.elements.type_document).toLowerCase() + "." : ""));
    }
    texte.push("Visite possible sur rendez-vous.");
    var ta = f.elements.description;
    if (ta.value.trim() && !window.confirm("Remplacer la description actuelle par ce nouveau texte ?")) return;
    ta.value = texte.join("\n");
    ta.focus();
  });

  var indice = $("[data-marche-hint]"), minuterie;
  function majMarche() {
    if (!indice) return;
    clearTimeout(minuterie);
    minuterie = setTimeout(function () {
      if (!val("ville")) { indice.hidden = true; return; }
      var q = new URLSearchParams({ type: typeAnnonce(), categorie: val("categorie"), ville: val("ville"), quartier: val("quartier_nom"), devise: val("devise") });
      fetch("/api/marche/?" + q.toString()).then(function (r) { return r.json(); }).then(function (d) {
        if (!d.disponible) { indice.hidden = true; return; }
        var prix = parseFloat(val("prix").replace(",", "."));
        var t = d.n + " bien" + (d.n > 1 ? "s" : "") + " comparable" + (d.n > 1 ? "s" : "") + " à " + d.portee + " : entre " + d.mini + " et " + d.maxi + ", " + d.moyenne + " en moyenne.";
        if (prix > 0) {
          var e = Math.round((prix / d.moy - 1) * 100);
          t += e > 10 ? " Votre prix est " + e + " % au-dessus : les contacts risquent d'être rares." : e < -10 ? " Votre prix est " + Math.abs(e) + " % en dessous de la moyenne." : " Votre prix est dans la moyenne.";
        }
        indice.textContent = t;
        indice.hidden = false;
      }).catch(function () { indice.hidden = true; });
    }, 450);
  }
  ["categorie", "ville", "quartier_nom", "devise", "prix"].forEach(function (n) {
    var e = f.elements[n];
    if (e) { e.addEventListener("input", majMarche); e.addEventListener("change", majMarche); }
  });
  $$("input[name=type_annonce]", f).forEach(function (r) { r.addEventListener("change", majMarche); });
  majMarche();
})();
