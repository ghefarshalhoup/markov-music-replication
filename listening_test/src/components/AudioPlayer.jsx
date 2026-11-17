import { useRef } from 'react';
import { playRing } from '../animations/microInteractions.js';

const R = 46;
const C = 2 * Math.PI * R;

function Icon({ status }) {
  if (status === 'playing') {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="5" width="4" height="14" rx="1.2" /><rect x="14" y="5" width="4" height="14" rx="1.2" /></svg>;
  }
  if (status === 'ended') {
    return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5a7 7 0 1 1-6.6 4.7" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" /><path d="M4.2 4.5v5.2h5.2" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" /></svg>;
  }
  return <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13l10.5-6.5z" /></svg>;
}

function time(s) {
  if (!Number.isFinite(s)) return '0:00';
  const m = Math.floor(s / 60);
  return `${m}:${String(Math.floor(s % 60)).padStart(2, '0')}`;
}

// The large round play button with its progress ring.
export default function AudioPlayer({ player, hint }) {
  const button = useRef(null);
  const { status, progress, duration, error } = player;
  const label = status === 'playing' ? 'Pause' : status === 'ended' ? 'Play again' : status === 'paused' ? 'Resume' : 'Play';

  const press = () => {
    if (status !== 'playing') playRing(button.current);
    player.toggle();
  };

  return (
    <div className="player">
      <button
        ref={button}
        type="button"
        className={`player__button is-${status}`}
        onClick={press}
        disabled={status === 'loading' || status === 'error'}
        aria-label={label}
      >
        <svg className="player__ring" viewBox="0 0 100 100" aria-hidden="true">
          <circle cx="50" cy="50" r={R} className="player__ring-track" />
          <circle cx="50" cy="50" r={R} className="player__ring-fill" style={{ strokeDasharray: C, strokeDashoffset: C * (1 - progress) }} />
        </svg>
        <span className="player__icon"><Icon status={status} /></span>
      </button>
      <div className="player__meta" aria-live="polite">
        {status === 'error' ? (
          <span className="player__error">{error} <button type="button" className="link" onClick={player.retry}>Try again</button></span>
        ) : status === 'loading' ? (
          <span>Loading…</span>
        ) : (
          <>
            <span className="player__time">{time(progress * duration)} / {time(duration)}</span>
            <span className="player__hint">{status === 'ended' ? 'You can listen again at any time.' : hint}</span>
          </>
        )}
      </div>
    </div>
  );
}
