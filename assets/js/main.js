document.addEventListener('DOMContentLoaded', () => {
  const items = Array.from(document.querySelectorAll('.portfolio-images figure:not(.portfolio-video) img'));
  if (!items.length) return;

  const lb = document.createElement('div');
  lb.className = 'lightbox';

  const img = document.createElement('img');
  const prevBtn = document.createElement('button');
  prevBtn.className = 'lightbox-nav lightbox-prev';
  prevBtn.setAttribute('aria-label', 'Eelmine pilt');
  prevBtn.innerHTML = '&#10094;';
  const nextBtn = document.createElement('button');
  nextBtn.className = 'lightbox-nav lightbox-next';
  nextBtn.setAttribute('aria-label', 'Järgmine pilt');
  nextBtn.innerHTML = '&#10095;';
  const playBtn = document.createElement('button');
  playBtn.className = 'lightbox-play';
  playBtn.setAttribute('aria-label', 'Esita slaidiseanss');
  playBtn.innerHTML = '&#9654;';

  lb.append(img, prevBtn, nextBtn, playBtn);
  document.body.appendChild(lb);

  let index = 0;
  let playing = null;

  function show(i) {
    index = (i + items.length) % items.length;
    img.src = items[index].src;
    img.alt = items[index].alt || '';
  }

  function stopPlay() {
    if (playing) {
      clearInterval(playing);
      playing = null;
      playBtn.innerHTML = '&#9654;';
    }
  }

  function open(i) {
    show(i);
    lb.classList.add('active');
  }

  function close() {
    lb.classList.remove('active');
    stopPlay();
  }

  items.forEach((el, i) => {
    el.addEventListener('click', () => open(i));
  });

  lb.addEventListener('click', close);

  [img, prevBtn, nextBtn, playBtn].forEach(el => {
    el.addEventListener('click', e => e.stopPropagation());
  });

  prevBtn.addEventListener('click', () => show(index - 1));
  nextBtn.addEventListener('click', () => show(index + 1));

  playBtn.addEventListener('click', () => {
    if (playing) {
      stopPlay();
    } else {
      playBtn.innerHTML = '&#10074;&#10074;';
      playing = setInterval(() => show(index + 1), 3000);
    }
  });

  document.addEventListener('keydown', e => {
    if (!lb.classList.contains('active')) return;
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowLeft') show(index - 1);
    else if (e.key === 'ArrowRight') show(index + 1);
  });
});
