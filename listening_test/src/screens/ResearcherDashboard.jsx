import { useCallback, useEffect, useState } from 'react';
import AnimatedScreen from '../components/AnimatedScreen.jsx';
import { api, exportUrls } from '../services/api.js';
import { storage } from '../services/storage.js';
import { backupCsv, download, stamp } from '../services/csvExport.js';

function Stat({ value, label }) {
  return (
    <div className="stat">
      <span className="stat__value">{value ?? '–'}</span>
      <span className="stat__label">{label}</span>
    </div>
  );
}

export default function ResearcherDashboard({ exp }) {
  const { session, trialIndex, unsynced, syncError } = exp;
  const [state, setState] = useState(null);
  const [offline, setOffline] = useState(false);
  const [browser, setBrowser] = useState({ sessions: 0, trials: 0 });
  const [confirming, setConfirming] = useState(false);

  const refresh = useCallback(async () => {
    try { setState(await api.state()); setOffline(false); } catch { setOffline(true); }
    const [sessions, trials] = await Promise.all([storage.allSessions(), storage.allTrials()]);
    setBrowser({ sessions: sessions.length, trials: trials.length, waiting: trials.filter((t) => !t.synced).length });
  }, []);

  useEffect(() => { refresh(); }, [refresh, unsynced]);

  const backup = async (kind) => {
    const [sessions, trials] = await Promise.all([storage.allSessions(), storage.allTrials()]);
    if (kind === 'json') download(JSON.stringify({ exported_at: new Date().toISOString(), sessions, trials }, null, 1), `browser_backup_${stamp()}.json`, 'application/json');
    else download(backupCsv(sessions, trials), `browser_backup_answers_${stamp()}.csv`);
  };

  const inProgress = session && session.status === 'active';
  const mismatch = state && !offline && browser.waiting > 0;

  return (
    <AnimatedScreen wide label="Researcher dashboard">
      <header className="eyebrow-row">
        <span className="eyebrow">Researcher</span>
        <button type="button" className="link" onClick={exp.closeDashboard}>Close</button>
      </header>
      <h1>Dashboard</h1>

      {offline && <p className="notice notice--error">The local server is not reachable. Answers are kept in this browser and will be sent once it runs again.</p>}
      {syncError && <p className="notice notice--error">{syncError}</p>}
      {mismatch && (
        <p className="notice">
          {browser.waiting} answer(s) in this browser are not yet in the database.
          <button type="button" className="link" onClick={async () => { await exp.retrySync(); refresh(); }}>Send now</button>
        </p>
      )}

      <div className="stats">
        <Stat value={state?.completed} label="Completed participants" />
        <Stat value={state?.pilot} label="Pilot sessions" />
        <Stat value={state?.responses} label="Responses (incl. pilots)" />
        <Stat value={state ? `${state.group_counts['1']} / ${state.group_counts['2']}` : null} label="Group 1 / Group 2" />
      </div>

      <section className="panel">
        <h2>Current session</h2>
        {session ? (
          <>
            <p>
              <strong>{session.participant_id}</strong> · Group {session.group_no}{session.pilot ? ' · pilot' : ''} ·{' '}
              {session.status === 'active'
                ? `in progress (clip ${Math.min(trialIndex + 1, session.trial_order.length)} of ${session.trial_order.length})`
                : session.status}
            </p>
            {unsynced > 0 && <p className="muted small">{unsynced} item(s) waiting to be sent to the database.</p>}
            <div className="actions">
              {inProgress && <button type="button" className="button" onClick={exp.closeDashboard}>Resume session</button>}
              {inProgress && !confirming && <button type="button" className="button button--quiet" onClick={() => setConfirming(true)}>End this session…</button>}
              {inProgress && confirming && (
                <>
                  <span className="small">Mark {session.participant_id} as abandoned? Saved answers are kept.</span>
                  <button type="button" className="button button--danger" onClick={async () => { await exp.abandonCurrent(); setConfirming(false); refresh(); }}>Yes, end it</button>
                  <button type="button" className="button button--quiet" onClick={() => setConfirming(false)}>Cancel</button>
                </>
              )}
              {!inProgress && <button type="button" className="button button--primary" onClick={exp.nextParticipant}>Start next participant</button>}
            </div>
          </>
        ) : (
          <div className="actions">
            <span className="muted">No session in progress.</span>
            <button type="button" className="button button--primary" onClick={exp.nextParticipant}>New session</button>
          </div>
        )}
      </section>

      <section className="panel">
        <h2>Download results</h2>
        <p className="muted small">From the database ({state?.database ?? 'results/listening/listening.sqlite'}). The answers file includes conditions and has no names.</p>
        <div className="downloads">
          <a className="button button--primary" href={exportUrls.answers} download>Answers (CSV)</a>
          <a className="button" href={exportUrls.sessions} download>Sessions (CSV)</a>
          <a className="button" href={exportUrls.names} download>Names (CSV)</a>
        </div>
        <h3>Browser backup</h3>
        <p className="muted small">
          This browser also keeps {browser.trials} answer(s) from {browser.sessions} session(s). It lives only in this browser on this
          laptop. Download a copy before clearing browsing data.
        </p>
        <div className="downloads">
          <button type="button" className="button" onClick={() => backup('csv')}>Backup answers (CSV)</button>
          <button type="button" className="button" onClick={() => backup('json')}>Full backup (JSON)</button>
        </div>
      </section>
      <p className="muted small">Open this dashboard at any time with Ctrl + Shift + L.</p>
    </AnimatedScreen>
  );
}
