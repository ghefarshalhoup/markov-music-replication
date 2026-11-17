import { useId } from 'react';
import { answerPulse } from '../animations/microInteractions.js';

// Five equal buttons, labelled only at the two ends. Arrow keys move along the scale.
export default function RatingScale({ prompt, low, high, value, onChange }) {
  const id = useId();
  const keys = (e, n) => {
    const next = e.key === 'ArrowRight' || e.key === 'ArrowUp' ? n + 1 : e.key === 'ArrowLeft' || e.key === 'ArrowDown' ? n - 1 : null;
    if (next && next >= 1 && next <= 5) {
      e.preventDefault();
      const btn = e.currentTarget.parentElement.children[next - 1];
      btn.focus();
      answerPulse(btn);
      onChange(next);
    }
  };
  return (
    <fieldset className="question">
      <legend className="question__prompt" id={`${id}-q`}>{prompt}</legend>
      <div className="scale" role="radiogroup" aria-labelledby={`${id}-q`}>
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={value === n}
            aria-label={`${n}${n === 1 ? ` (${low})` : n === 5 ? ` (${high})` : ''}`}
            tabIndex={value ? (value === n ? 0 : -1) : n === 1 ? 0 : -1}
            className={`scale__point${value === n ? ' is-selected' : ''}`}
            onClick={(e) => { answerPulse(e.currentTarget); onChange(n); }}
            onKeyDown={(e) => keys(e, n)}
          >
            {n}
          </button>
        ))}
      </div>
      <div className="scale__ends" aria-hidden="true"><span>{low}</span><span>{high}</span></div>
    </fieldset>
  );
}
