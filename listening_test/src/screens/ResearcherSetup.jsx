import { useEffect, useState } from 'react';
import AnimatedScreen from '../components/AnimatedScreen.jsx';
import { api } from '../services/api.js';

export default function ResearcherSetup({ onStart, error, onDashboard }) {
  const [state, setState] = useState(null);
  const [offline, setOffline] = useState(false);
  const [name, setName] = useState('');
  const [pilot, setPilot] = useState(false);
  const [group, setGroup] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.state()
      .then((s) => { setState(s); setGroup(s.next_group); })
      .catch(() => setOffline(true));
  }, []);

  const missing = state?.missing_audio?.length > 0;
  const nextId = state ? (pilot ? state.next_id.pilot : state.next_id.real) : '…';
  const start = async (e) => {
    e.preventDefault();
    setBusy(true);
    await onStart({ group, pilot, name });
    setBusy(false);
  };

  return (
    <AnimatedScreen label="Researcher setup">
      <header className="eyebrow-row">
        <span className="eyebrow">Researcher</span>
        <button type="button" className="link" onClick={onDashboard}>Dashboard</button>
      </header>
      <h1>New session</h1>
      <p className="lead">Prepare the session, press Start, then hand the laptop to the participant.</p>

      {offline && <p className="notice notice--error">The local server is not running. Start it with <code>python listening_test/serve.py</code> and reload this page.</p>}
      {missing && <p className="notice notice--error">Audio files missing: {state.missing_audio.join(', ')}. Run <code>scripts/make_listening_clips.py</code>.</p>}
      {error && <p className="notice notice--error" role="alert">{error}</p>}

      <form className="form" onSubmit={start}>
        <div className="field">
          <span className="field__label">Participant ID</span>
          <span className="pid">{nextId}</span>
          <span className="field__help">Assigned automatically. Only this ID is stored with the answers.</span>
        </div>

        <label className="field">
          <span className="field__label">Name <span className="muted">(optional)</span></span>
          <input type="text" value={name} onChange={(e) => setName(e.target.value)} autoComplete="off" placeholder="For your own records" />
          <span className="field__help">Kept in a separate file (names.sqlite), never in the research data.</span>
        </label>

        <div className="field">
          <span className="field__label" id="group-label">Group</span>
          <div className="segmented" role="radiogroup" aria-labelledby="group-label">
            {[1, 2].map((g) => (
              <button key={g} type="button" role="radio" aria-checked={group === g}
                className={`segmented__option${group === g ? ' is-selected' : ''}`} onClick={() => setGroup(g)}>
                Group {g}
              </button>
            ))}
          </div>
          {state && (
            <span className="field__help">
              Suggested: Group {state.next_group} (so far {state.group_counts['1']} in group 1, {state.group_counts['2']} in group 2).
            </span>
          )}
        </div>

        <label className="toggle">
          <input type="checkbox" checked={pilot} onChange={(e) => setPilot(e.target.checked)} />
          <span className="toggle__track" aria-hidden="true"><span className="toggle__thumb" /></span>
          <span>
            <span className="field__label">Pilot / practice session</span>
            <span className="field__help">Marked as pilot (ID starts with T) and left out of the main analysis.</span>
          </span>
        </label>

        <button className="button button--primary button--block" type="submit" disabled={!state || missing || !group || busy}>
          {busy ? 'Starting…' : 'Start experiment'}
        </button>
      </form>
    </AnimatedScreen>
  );
}
