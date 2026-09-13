// Kaks alalist linki admini nurgas:
//  - Eelvaade: avab saidi ise, nimelises target-aknas (mitte lihtsalt
//    _blank), et klõpsuga saaks admini ja eelvaate vahel kiiresti edasi-
//    tagasi liikuda ilma iga kord uut vahelehte tekitamata.
//  - GitHub: viimased salvestused GitHubi ajaloos, et näha, kas salvestus
//    jõudis kohale — sõltumata sellest, kas sait on juba avaldatud.
// Sveltia tühjendab käivitudes kogu <body>, seega ei piisa linkide lihtsalt
// HTML-i kirjutamisest: MutationObserver lisab need iga kord tagasi, kui
// Sveltia oma osa uuesti joonistab.
(function () {
  function addLink(opts) {
    if (document.getElementById(opts.id)) return;
    var a = document.createElement("a");
    a.id = opts.id;
    a.href = opts.href;
    a.target = opts.target;
    a.rel = "noopener";
    a.title = opts.title;
    a.style.cssText =
      "position:fixed;right:14px;" + opts.bottom + ";z-index:2147483647;" +
      "display:flex;align-items:center;gap:6px;background:#14110f;color:#fff;" +
      "font:500 12px/1 system-ui,sans-serif;padding:9px 14px;border-radius:999px;" +
      "text-decoration:none;box-shadow:0 2px 10px rgba(0,0,0,.3);opacity:.82;";
    a.innerHTML = opts.icon + opts.label;
    document.body.appendChild(a);
  }

  function addLinks() {
    addLink({
      id: "preview-badge",
      href: "/",
      target: "sandra-eelvaade",
      title: "Ava saidi eelvaade (sama vaheleht iga kord)",
      bottom: "bottom:56px",
      icon:
        '<svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">' +
        '<path d="M8 3C4 3 1.3 6 0 8c1.3 2 4 5 8 5s6.7-3 8-5c-1.3-2-4-5-8-5zm0 8.5A3.5 3.5 0 1 1 8 4.5a3.5 3.5 0 0 1 0 7zm0-1.5a2 2 0 1 0 0-4 2 2 0 0 0 0 4z"/>' +
        "</svg>",
      label: "Eelvaade",
    });
    addLink({
      id: "gh-badge",
      href: "https://github.com/jyrishestakov-design/sandra-site/commits/main",
      target: "_blank",
      title: "Vaata viimaseid salvestusi GitHubis",
      bottom: "bottom:14px",
      icon:
        '<svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">' +
        '<path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38' +
        "0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13" +
        "-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66" +
        ".07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15" +
        "-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27" +
        ".68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12" +
        ".51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48" +
        '0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/>' +
        "</svg>",
      label: "GitHub",
    });
  }

  addLinks();
  new MutationObserver(addLinks).observe(document.documentElement, {
    childList: true,
    subtree: true,
  });
})();
