import { useCallback, useEffect, useRef, useState } from 'react';
import { api, OfflineError, RejectedError } from '../services/api.js';
import { storage } from '../services/storage.js';
import { buildTrial, mergeSession, nextTrialIndex, stageOf } from '../services/experimentEngine.js';

// The experiment's state machine. Screens: loading, setup, welcome, experience, soundcheck, trial,
// complete, declined, dashboard.
// Everything recorded goes to IndexedDB first, then to the server (SQLite). The IndexedDB copy of the
// session holds a list of steps not yet sent ("pending"); trials carry a synced flag.

const FIELD = { consent: 'consent_at', soundcheck: 'soundcheck_at' };
let eventCounter = 0;

async function removePending(id, eventId) {
  const s = await storage.getSession(id);
  if (!s) return;
  await storage.saveSession({ ...s, pending: (s.pending || []).filter((e) => e.id !== eventId) });
}

export function useExperiment() {
  const [screen, setScreen] = useState('loading');
  const [session, setSession] = useState(null);
  const [trialIndex, setTrialIndex] = useState(0);
  const [unsynced, setUnsynced] = useState(0);
  const [syncError, setSyncError] = useState(null);
  const [error, setError] = useState(null);
  const returnTo = useRef('setup');
  const syncing = useRef(null);
  const again = useRef(false);

  // --- sending what is waiting -------------------------------------------------------------------------
  // Order: consent / experience / sound-check events, then trials in order, then completion.
  const runSync = useCallback(async (id) => {
    let sess = await storage.getSession(id);
    if (!sess) return null;
    let problem = null;
    try {
      const sendEvents = async (which) => {
        const current = await storage.getSession(id);
        for (const ev of (current.pending || []).filter(which)) {
          try {
            await api.event(id, ev.type, ev.value);
          } catch (e) {
            if (!(e instanceof RejectedError)) throw e;
            problem = `The server refused "${ev.type}": ${e.message}`;
          }
          await removePending(id, ev.id);
        }
      };
      await sendEvents((e) => e.type !== 'complete');
      const trials = (await storage.getTrials(id)).filter((t) => !t.synced && !t.rejected)
        .sort((a, b) => a.trial_index - b.trial_index);
      for (const t of trials) {
        const { synced, rejected, ...payload } = t;
        try {
          await api.saveTrial(id, payload);
          await storage.markSynced(id, t.trial_index);
        } catch (e) {
          if (!(e instanceof RejectedError)) throw e;
          await storage.markRejected(id, t.trial_index, e.message);   // kept locally, not retried forever
          problem = `Trial ${t.trial_index + 1} was refused by the server: ${e.message}`;
        }
      }
      await sendEvents((e) => e.type === 'complete');
    } catch (e) {
      problem = e instanceof OfflineError ? `${e.message} Answers are kept in this browser until it is back.` : String(e.message || e);
    }
    setSyncError(problem);
    sess = await storage.getSession(id);
    const waiting = (await storage.getTrials(id)).filter((t) => !t.synced && !t.rejected).length;
    setUnsynced(waiting + (sess.pending || []).length);
    return sess;
  }, []);

  const sync = useCallback((id) => {
    if (!id) return Promise.resolve(null);
    if (syncing.current) { again.current = true; return syncing.current; }
    syncing.current = (async () => {
      let result;
      try {
        do { again.current = false; result = await runSync(id); } while (again.current);
      } finally {
        syncing.current = null;
      }
      return result;
    })();
    return syncing.current;
  }, [runSync]);

  // --- recording a step ----------------------------------------------------------------------------------
  const record = useCallback(async (id, type, value = null) => {
    const base = await storage.getSession(id);
    eventCounter += 1;
    const updated = { ...base, pending: [...(base.pending || []), { id: `${Date.now()}-${eventCounter}`, type, value }] };
    if (type === 'experience') updated.experience = value;
    if (FIELD[type]) updated[FIELD[type]] = updated[FIELD[type]] || new Date().toISOString();
    if (type === 'complete') { updated.status = 'completed'; updated.completed_at = new Date().toISOString(); }
    if (type === 'abandon') updated.status = 'abandoned';
    await storage.saveSession(updated);
    setSession(updated);
    const answered = (await storage.getTrials(id)).length;
    setScreen(stageOf(updated, answered));
    sync(id);
    return updated;
  }, [sync]);

  // --- recovery after a refresh ----------------------------------------------------------------------
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const id = await storage.getActive();
        if (!id) { setScreen('setup'); return; }
        const local = await storage.getSession(id);
        let remote = null;
        try { remote = await api.getSession(id); } catch { remote = null; }
        const merged = mergeSession(local, remote);
        if (!merged) { await storage.clearActive(); setScreen('setup'); return; }
        delete merged.trials;
        await storage.saveSession(merged);
        for (const t of remote?.trials || []) {             // answers the server has but this browser lost
          await storage.saveTrial({ ...t, session_id: id, synced: true });
          await storage.markSynced(id, t.trial_index);
        }
        const after = (await sync(id)) || merged;
        const answered = (await storage.getTrials(id)).map((t) => t.trial_index);
        if (cancelled) return;
        setSession(after);
        setTrialIndex(nextTrialIndex(after.trial_order, answered));
        const stage = stageOf(after, answered.length);
        if (stage === 'complete' && after.status !== 'completed') await record(id, 'complete');
        else setScreen(stage);
      } catch (e) {
        setError(`Could not restore the session: ${e.message}`);
        setScreen('setup');
      }
    })();
    return () => { cancelled = true; };
  }, [sync, record]);

  // --- participant steps -------------------------------------------------------------------------------
  const startSession = useCallback(async ({ group, pilot, name }) => {
    setError(null);
    try {
      const created = await api.createSession(group, pilot, name);
      const sess = { ...created, pending: [] };
      delete sess.trials;
      await storage.saveSession(sess);
      await storage.setActive(sess.session_id);
      setSession(sess);
      setTrialIndex(0);
      setUnsynced(0);
      setSyncError(null);
      setScreen('welcome');
    } catch (e) {
      setError(e instanceof OfflineError
        ? 'The local server is not running. Start it with: python listening_test/serve.py'
        : e.message);
    }
  }, []);

  const consent = () => record(session.session_id, 'consent');
  const decline = () => record(session.session_id, 'abandon');
  const chooseExperience = (value) => record(session.session_id, 'experience', value);
  const finishSoundCheck = () => record(session.session_id, 'soundcheck');

  const submitTrial = useCallback(async (answers, replays, responseMs) => {
    const trial = buildTrial(session, trialIndex, answers, replays, responseMs);
    await storage.saveTrial(trial);                 // safe in the browser before anything else happens
    const next = trialIndex + 1;
    if (next >= session.trial_order.length) {
      await record(session.session_id, 'complete'); // sync sends the trials first, then the completion
    } else {
      setTrialIndex(next);
      sync(session.session_id);
    }
  }, [session, trialIndex, sync, record]);

  // --- researcher --------------------------------------------------------------------------------------
  const openDashboard = useCallback(() => {
    setScreen((s) => {
      if (s !== 'dashboard') returnTo.current = s === 'loading' ? 'setup' : s;
      return 'dashboard';
    });
  }, []);
  const closeDashboard = () => setScreen(returnTo.current);

  const nextParticipant = async () => {
    if (session && session.status === 'active') return;   // the dashboard asks to end it first
    await storage.clearActive();
    setSession(null);
    setTrialIndex(0);
    setUnsynced(0);
    setSyncError(null);
    returnTo.current = 'setup';
    setScreen('setup');
  };

  const abandonCurrent = async () => {
    if (!session) return;
    await record(session.session_id, 'abandon');
    returnTo.current = 'declined';
    setScreen('dashboard');
  };

  const retrySync = () => (session ? sync(session.session_id) : Promise.resolve());

  return {
    screen, session, trialIndex, unsynced, syncError, error,
    startSession, consent, decline, chooseExperience, finishSoundCheck, submitTrial,
    openDashboard, closeDashboard, nextParticipant, abandonCurrent, retrySync,
  };
}
