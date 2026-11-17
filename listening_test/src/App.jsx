import { useEffect } from 'react';
import { useExperiment } from './hooks/useExperiment.js';
import ResearcherSetup from './screens/ResearcherSetup.jsx';
import WelcomeConsent from './screens/WelcomeConsent.jsx';
import MusicalExperience from './screens/MusicalExperience.jsx';
import SoundCheck from './screens/SoundCheck.jsx';
import ListeningTest from './screens/ListeningTest.jsx';
import Completion from './screens/Completion.jsx';
import ResearcherDashboard from './screens/ResearcherDashboard.jsx';

export default function App() {
  const exp = useExperiment();
  const { screen, session, openDashboard } = exp;

  // The researcher's shortcut. Participants are never shown a link to it.
  useEffect(() => {
    const onKey = (e) => {
      if (e.ctrlKey && e.shiftKey && (e.key === 'L' || e.key === 'l')) {
        e.preventDefault();
        openDashboard();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [openDashboard]);

  // Warn before leaving in the middle of a session (answers are safe, but the current clip restarts).
  useEffect(() => {
    if (!session || session.status !== 'active') return undefined;
    const warn = (e) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [session]);

  let content;
  switch (screen) {
    case 'setup':
      content = <ResearcherSetup onStart={exp.startSession} error={exp.error} onDashboard={openDashboard} />;
      break;
    case 'welcome':
      content = <WelcomeConsent onAgree={exp.consent} onDecline={exp.decline} />;
      break;
    case 'experience':
      content = <MusicalExperience onChoose={exp.chooseExperience} />;
      break;
    case 'soundcheck':
      content = <SoundCheck clipId={session.practice} onDone={exp.finishSoundCheck} />;
      break;
    case 'trial':
      content = <ListeningTest session={session} index={exp.trialIndex} onSubmit={exp.submitTrial} />;
      break;
    case 'complete':
      content = <Completion />;
      break;
    case 'declined':
      content = <Completion declined />;
      break;
    case 'dashboard':
      content = <ResearcherDashboard exp={exp} />;
      break;
    default:
      content = <main className="screen" aria-busy="true"><p className="muted">Loading…</p></main>;
  }

  return (
    <div className="app">
      <div className="brand" aria-hidden="true"><span className="brand__dot" />Listening Study</div>
      {content}
    </div>
  );
}
