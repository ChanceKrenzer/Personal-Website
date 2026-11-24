// Motion on the page: the short muted clips on the project pages and the
// slow turn of the 3D model on the home page.
//
// The markup ships every <video> with controls and preload="none", so nothing
// downloads up front, and without JavaScript (or for anyone who has asked their
// system for less motion) each clip is just a poster with a play button.
// Otherwise this turns them into silent looping pictures that only load and
// play while they're on screen.
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;

if (reduceMotion) {
  document.querySelectorAll('model-viewer[auto-rotate]').forEach(m => m.removeAttribute('auto-rotate'));
} else if ('IntersectionObserver' in window) {
  const observer = new IntersectionObserver(entries => {
    for (const { target, isIntersecting } of entries) {
      // NotAllowedError means the browser blocked autoplay, so hand the clip
      // back to the visitor. Any other rejection is just a pause() cutting off
      // a play() that hadn't started yet.
      if (isIntersecting) target.play().catch(err => { if (err.name === 'NotAllowedError') target.controls = true; });
      else target.pause();
    }
  }, { rootMargin: '200px 0px' });

  document.querySelectorAll('video[muted][loop]').forEach(v => { v.controls = false; observer.observe(v); });
}

// The home page's 3D model doubles as a link to the write-up. A click that
// barely moves opens it, while a drag turns the model as usual.
document.querySelectorAll('model-viewer[data-href]').forEach(m => {
  let start = null;
  m.addEventListener('pointerdown', e => { start = [e.clientX, e.clientY]; });
  m.addEventListener('pointerup', e => {
    if (start && Math.hypot(e.clientX - start[0], e.clientY - start[1]) < 6) location.href = m.dataset.href;
    start = null;
  });
});
