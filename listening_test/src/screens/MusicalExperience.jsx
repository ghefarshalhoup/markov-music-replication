import { useState } from 'react';
import AnimatedScreen from '../components/AnimatedScreen.jsx';
import ChoiceButton from '../components/ChoiceButton.jsx';
import { EXPERIENCE_OPTIONS } from '../services/experimentEngine.js';

export default function MusicalExperience({ onChoose }) {
  const [value, setValue] = useState(null);
  return (
    <AnimatedScreen label="Musical experience">
      <span className="eyebrow">Before we start</span>
      <h1 id="exp-q">How would you describe your musical experience?</h1>
      <div className="stack" role="group" aria-labelledby="exp-q">
        {EXPERIENCE_OPTIONS.map((o) => (
          <ChoiceButton key={o.value} large selected={value === o.value} onSelect={() => setValue(o.value)}>{o.label}</ChoiceButton>
        ))}
      </div>
      <div className="actions">
        <button type="button" className="button button--primary" disabled={!value} onClick={() => onChoose(value)}>Continue</button>
      </div>
    </AnimatedScreen>
  );
}
