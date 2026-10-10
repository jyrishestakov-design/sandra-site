// Avalehe taustavideod: mängivad järjest ja sulanduvad üksteiseks (crossfade).
// Seaded tulevad data/home.yaml failist (admin: "Avaleht").
(function () {
  const hero = document.querySelector('.hero');
  if (!hero) return;
  const vids = Array.from(hero.querySelectorAll('.hero-video'));
  const btn = hero.querySelector('.hero-toggle');
  const fade = parseFloat(hero.dataset.fade) || 1.2;
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  let cur = 0, paused = reduce, switching = false, visible = true;

  function setBtn() {
    btn.setAttribute('aria-pressed', paused ? 'true' : 'false');
    btn.classList.toggle('is-paused', paused);
    const en = document.documentElement.lang === 'en';
    btn.setAttribute('aria-label', paused ? (en ? 'Play video' : 'Esita video') : (en ? 'Pause video' : 'Peata video'));
  }
  function playCur() {
    if (paused || !visible) return;
    const p = vids[cur].play();
    if (p && p.catch) p.catch(() => { paused = true; setBtn(); });
  }
  function next() {
    if (vids.length < 2 || switching) return;
    switching = true;
    const prev = vids[cur];
    cur = (cur + 1) % vids.length;
    const v = vids[cur];
    v.currentTime = 0;
    playCur();
    v.classList.add('is-active');
    prev.classList.remove('is-active');
    setTimeout(() => { prev.pause(); switching = false; }, fade * 1000 + 50);
  }
  vids.forEach((v) => {
    v.addEventListener('timeupdate', () => {
      if (v !== vids[cur] || !v.duration) return;
      if (v.duration - v.currentTime <= fade) next();
    });
    v.addEventListener('ended', () => {
      if (vids.length > 1) next(); else { v.currentTime = 0; playCur(); }
    });
  });
  btn.addEventListener('click', () => {
    paused = !paused;
    setBtn();
    if (paused) vids.forEach((v) => v.pause()); else playCur();
  });
  // Peata, kui avaleht pole nähtav (kerimisel allapoole või teises kaardis).
  if ('IntersectionObserver' in window) {
    new IntersectionObserver((es) => {
      visible = es[0].isIntersecting;
      if (visible) playCur(); else vids[cur].pause();
    }).observe(hero);
  }
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) vids[cur].pause(); else playCur();
  });
  setBtn();
  playCur();
})();
