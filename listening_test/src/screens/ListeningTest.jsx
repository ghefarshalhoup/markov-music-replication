import { useEffect, useRef, useState } from 'react';
import AnimatedScreen from '../components/AnimatedScreen.jsx';
import AudioPlayer from '../components/AudioPlayer.jsx';
import ChoiceButton from '../components/ChoiceButton.jsx';
import ProgressBar from '../components/ProgressBar.jsx';
import RatingScale from '../components/RatingScale.jsx';
import { useAudioPlayer } from '../hooks/useAudioPlayer.js';
import { QUESTIONS, isAnswered } from '../services/experimentEngine.js';

function Trial({ clipId, number, total, onSubmit }) {
  const player = useAudioPlayer(`/clips/${clipId}.mp3`);
  const [answers, setAnswers] = useState({ liking: null, ending: null, attribution: null });
  const [busy, setBusy] = useState(false);
  const unlockedAt = useRef(null);

  useEffect(() => {
    if (player.completed && unlockedAt.current === null) unlockedAt.current = performance.now();
  }, [player.completed]);

  const set = (k) => (v) => setAnswers((a) => ({ ...a, [k]: v }));
  const ready = player.completed && isAnswered(answers) && !busy;

  const next = async () => {
    if (!ready) return;
    setBusy(true);
    await onSubmit(answers, Math.max(0, player.plays - 1), performance.now() - unlockedAt.current);
  };

  return (
    <AnimatedScreen wide label={`Clip ${number} of ${total}`}>
      <ProgressBar current={number} total={total} />
      <AudioPlayer player={player} hint={player.status === 'playing' || player.status === 'paused' ? 'Listening…' : 'Press play to listen.'} />

      {player.completed ? (
        <section className="questions animate__animated animate__fadeIn" aria-label="Questions">
          <RatingScale {...QUESTIONS.liking} value={answers.liking} onChange={set('liking')} />
          <RatingScale {...QUESTIONS.ending} value={answers.ending} onChange={set('ending')} />
          <fieldset className="question">
            <legend className="question__prompt">{QUESTIONS.attribution.prompt}</legend>
            <div className="pair">
              {QUESTIONS.attribution.options.map((o) => (
                <ChoiceButton key={o.value} large selected={answers.attribution === o.value} onSelect={() => set('attribution')(o.value)}>
                  {o.label}
                </ChoiceButton>
              ))}
            </div>
          </fieldset>
          <div className="actions actions--end">
            <button type="button" className="button button--primary" disabled={!ready} onClick={next}>
              {number === total ? 'Finish' : 'Next clip'}
            </button>
          </div>
        </section>
      ) : (
        <p className="waiting" aria-live="polite">The questions appear when the clip has finished.</p>
      )}
    </AnimatedScreen>
  );
}

export default function ListeningTest({ session, index, onSubmit }) {
  const order = session.trial_order;
  // the key resets all per-clip state, so nothing carries over from the previous clip
  return <Trial key={`${session.session_id}-${index}`} clipId={order[index]} number={index + 1} total={order.length} onSubmit={onSubmit} />;
}
