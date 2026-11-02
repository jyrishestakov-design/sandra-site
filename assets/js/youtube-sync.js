// Hoiab galerii sünkroonis YouTube'i kanaliga "Mida teie ka kunstist taipate?".
// Adminis lisatud videod jäävad oma allkirjade ja algusaegadega. Kanali videod,
// mida galeriis veel pole, lisatakse
// automaatselt (allkirjaks YouTube'i pealkiri) ja kogu galerii pannakse
// avaldamise järjekorda, uuemad eespool.
// Andmed tulevad sama saidi funktsioonist /api/kanal (functions/api/kanal.js).
(function () {
  var gallery = document.querySelector(".portfolio-images[data-youtube-sync]");
  if (!gallery || !window.fetch) return;

  function idFromHref(href) {
    var m = href.match(/[?&]v=([A-Za-z0-9_-]{6,20})/) || href.match(/youtu\.be\/([A-Za-z0-9_-]{6,20})/);
    return m ? m[1] : null;
  }

  var have = {};
  gallery.querySelectorAll(".portfolio-video a[href]").forEach(function (a) {
    var id = idFromHref(a.getAttribute("href"));
    if (id) have[id] = true;
  });

  fetch("/api/kanal")
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (data) {
      if (!data || !data.videos) return;
      var missing = data.videos
        .filter(function (v) { return v.id && !have[v.id]; })
        .sort(function (a, b) { return new Date(b.published) - new Date(a.published); });
      var first = gallery.firstElementChild;
      missing.forEach(function (v) {
        var fig = document.createElement("figure");
        fig.className = "portfolio-video";
        var a = document.createElement("a");
        a.href = "https://www.youtube.com/watch?v=" + v.id;
        a.target = "_blank";
        a.rel = "noopener";
        a.setAttribute("aria-label", "Vaata YouTube'is");
        var img = document.createElement("img");
        img.src = "https://img.youtube.com/vi/" + v.id + "/hqdefault.jpg";
        img.alt = v.title || "";
        img.loading = "lazy";
        var play = document.createElement("span");
        play.className = "play-icon";
        play.setAttribute("aria-hidden", "true");
        a.appendChild(img);
        a.appendChild(play);
        fig.appendChild(a);
        if (v.title) {
          var cap = document.createElement("figcaption");
          cap.textContent = v.title;
          fig.appendChild(cap);
        }
        gallery.insertBefore(fig, first);
      });

      // Kogu galerii avaldamise järjekorda (uuemad eespool). Videod, mida
      // kanalil pole (ja pildid), jäävad oma järjekorras lõppu.
      var published = {};
      data.videos.forEach(function (v) { published[v.id] = new Date(v.published).getTime(); });
      var figs = Array.prototype.slice.call(gallery.children);
      var dated = [], rest = [];
      figs.forEach(function (f, i) {
        var a = f.querySelector(".portfolio-video a[href], a[href]");
        var id = a && f.classList.contains("portfolio-video") ? idFromHref(a.getAttribute("href")) : null;
        if (id && published[id]) dated.push({ f: f, t: published[id], i: i });
        else rest.push(f);
      });
      dated.sort(function (x, y) { return y.t - x.t || x.i - y.i; });
      dated.forEach(function (d) { gallery.appendChild(d.f); });
      rest.forEach(function (f) { gallery.appendChild(f); });
    })
    .catch(function () { /* kui kanal ei vasta, jääb galerii nagu adminis */ });
})();
