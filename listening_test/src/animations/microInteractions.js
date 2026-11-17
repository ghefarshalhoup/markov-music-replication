import mojs from '@mojs/core';

// mo.js effects inside a screen. Animate.css handles moving between screens; these only confirm
// actions. Each is short (<= 600 ms), never blocks anything and is skipped with reduced motion.

const SAGE = '#92B3A7';
const INK = '#202C2B';

const reduced = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

function centre(el) {
  const r = el.getBoundingClientRect();
  return { left: r.left + r.width / 2 + window.scrollX, top: r.top + r.height / 2 + window.scrollY, r };
}

function fire(make) {
  if (reduced()) return;
  try {
    const anim = make();
    anim.play();
    setTimeout(() => anim.el?.remove?.(), 1200);
  } catch {
    /* motion is decoration only */
  }
}

/** Playback started: one soft ring expanding from the play button. */
export function playRing(el) {
  if (!el) return;
  const { left, top, r } = centre(el);
  const base = r.width / 2;
  fire(() => new mojs.Shape({
    parent: document.body, left, top, shape: 'circle', fill: 'none',
    stroke: SAGE, strokeWidth: { 6: 0 }, radius: { [base]: base + 34 }, opacity: { 0.9: 0 },
    duration: 600, easing: 'cubic.out', isForce3d: true,
  }));
}

/** An answer registered: the same tiny pulse for every option, whatever its value. */
export function answerPulse(el) {
  if (!el) return;
  const { left, top, r } = centre(el);
  const base = Math.min(r.width, r.height) / 2;
  fire(() => new mojs.Shape({
    parent: document.body, left, top, shape: 'circle', fill: 'none',
    stroke: INK, strokeWidth: { 2: 0 }, radius: { [base]: base + 10 }, opacity: { 0.35: 0 },
    duration: 320, easing: 'quad.out',
  }));
}

/** The end of the test: a short, quiet burst around the check mark. */
export function completionBurst(el) {
  if (!el) return;
  const { left, top, r } = centre(el);
  const base = r.width / 2;
  if (reduced()) return;
  try {
    const ring = new mojs.Shape({
      parent: document.body, left, top, shape: 'circle', fill: 'none', stroke: SAGE,
      strokeWidth: { 8: 0 }, radius: { [base]: base + 40 }, opacity: { 0.8: 0 }, duration: 700, easing: 'cubic.out',
    });
    const burst = new mojs.Burst({
      parent: document.body, left, top, radius: { [base + 6]: base + 46 }, count: 10, degree: 360,
      children: { shape: 'circle', radius: { 3: 0 }, fill: [SAGE, INK], duration: 650, easing: 'quad.out' },
    });
    new mojs.Timeline().add(ring, burst).play();
    setTimeout(() => { ring.el?.remove?.(); burst.el?.remove?.(); }, 1500);
  } catch {
    /* decoration only */
  }
}
