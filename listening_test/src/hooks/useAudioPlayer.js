import { useCallback, useEffect, useRef, useState } from 'react';

// One clip. `completed` turns true only on the audio's own "ended" event, so the questions can
// never unlock from a partial play. There is no seeking. A play from the start counts as a play;
// resuming after a pause does not.

const INITIAL = { status: 'loading', progress: 0, duration: 0, completed: false, plays: 0, error: null };

export function useAudioPlayer(src) {
  const audio = useRef(null);
  const [state, setState] = useState(INITIAL);

  useEffect(() => {
    setState(INITIAL);
    if (!src) return undefined;
    const a = new Audio();
    a.preload = 'auto';
    audio.current = a;
    const update = (patch) => setState((s) => ({ ...s, ...(typeof patch === 'function' ? patch(s) : patch) }));
    const handlers = {
      loadedmetadata: () => update({ duration: a.duration }),
      canplay: () => update((s) => (s.status === 'loading' ? { status: 'ready' } : {})),
      timeupdate: () => update({ progress: a.duration ? a.currentTime / a.duration : 0 }),
      playing: () => update({ status: 'playing' }),
      pause: () => update((s) => (s.status === 'playing' && !a.ended ? { status: 'paused' } : {})),
      ended: () => update({ status: 'ended', progress: 1, completed: true }),
      error: () => update({ status: 'error', error: 'This clip could not be loaded.' }),
    };
    Object.entries(handlers).forEach(([event, fn]) => a.addEventListener(event, fn));
    a.src = src;
    return () => {
      Object.entries(handlers).forEach(([event, fn]) => a.removeEventListener(event, fn));
      a.pause();
      a.removeAttribute('src');
      a.load();
      audio.current = null;
    };
  }, [src]);

  const toggle = useCallback(async () => {
    const a = audio.current;
    if (!a) return;
    if (!a.paused && !a.ended) { a.pause(); return; }
    const fromStart = a.ended || a.currentTime === 0;
    if (a.ended) a.currentTime = 0;
    try {
      await a.play();
      if (fromStart) setState((s) => ({ ...s, plays: s.plays + 1, error: null }));
    } catch (e) {
      setState((s) => ({ ...s, status: 'error', error: 'Playback did not start. Please try again.' }));
    }
  }, []);

  const retry = useCallback(() => {
    const a = audio.current;
    if (!a) return;
    setState((s) => ({ ...s, status: 'loading', error: null }));
    a.load();
  }, []);

  return { ...state, toggle, retry };
}
