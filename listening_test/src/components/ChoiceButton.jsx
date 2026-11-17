import { answerPulse } from '../animations/microInteractions.js';

// A large selectable option. Every option looks and reacts the same way when chosen.
export default function ChoiceButton({ selected, onSelect, children, large = false, disabled = false, describedBy }) {
  return (
    <button
      type="button"
      className={`choice${large ? ' choice--large' : ''}${selected ? ' is-selected' : ''}`}
      aria-pressed={selected}
      aria-describedby={describedBy}
      disabled={disabled}
      onClick={(e) => { answerPulse(e.currentTarget); onSelect(); }}
    >
      {children}
    </button>
  );
}
