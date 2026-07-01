document.addEventListener('DOMContentLoaded', () => {
  const lb = document.createElement('div');
  lb.className = 'lightbox';
  const img = document.createElement('img');
  lb.appendChild(img);
  document.body.appendChild(lb);
  document.querySelectorAll('.portfolio-images img').forEach(el => {
    el.addEventListener('click', () => { img.src = el.src; lb.classList.add('active'); });
  });
  lb.addEventListener('click', () => lb.classList.remove('active'));
  document.addEventListener('keydown', e => { if (e.key === 'Escape') lb.classList.remove('active'); });
});
