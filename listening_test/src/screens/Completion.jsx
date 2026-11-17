import { useEffect, useRef } from 'react';
import AnimatedScreen from '../components/AnimatedScreen.jsx';
import { completionBurst } from '../animations/microInteractions.js';

export default function Completion({ declined = false }) {
  const icon = useRef(null);
  useEffect(() => {
    if (declined) return undefined;
    const t = setTimeout(() => completionBurst(icon.current), 250);
    return () => clearTimeout(t);
  }, [declined]);
  return (
    <AnimatedScreen label="Thank you">
      <div className="done">
        <span className="done__icon" ref={icon} aria-hidden="true">
          <svg viewBox="0 0 24 24"><path d="M6 12.5l4 4 8-9" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </span>
        <h1>{declined ? 'Thank you.' : 'Thank you for listening.'}</h1>
        {!declined && <p className="lead">Your responses have been saved.</p>}
        <p className="lead">Please return the laptop to the researcher.</p>
      </div>
    </AnimatedScreen>
  );
}
