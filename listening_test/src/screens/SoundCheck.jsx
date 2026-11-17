import AnimatedScreen from '../components/AnimatedScreen.jsx';
import AudioPlayer from '../components/AudioPlayer.jsx';
import { useAudioPlayer } from '../hooks/useAudioPlayer.js';

export default function SoundCheck({ clipId, onDone }) {
  const player = useAudioPlayer(clipId ? `/clips/${clipId}.mp3` : null);
  return (
    <AnimatedScreen label="Sound check">
      <span className="eyebrow">Sound check</span>
      <h1>Set a comfortable volume.</h1>
      <p className="lead">Play this short example and adjust your volume. It is only for practice and is not part of the study.</p>
      <AudioPlayer player={player} hint="Press play to listen." />
      <div className="actions">
        <button type="button" className="button button--primary" disabled={!player.completed} onClick={onDone}>Continue</button>
        {!player.completed && <span className="muted small">Continue becomes available after the example has finished.</span>}
      </div>
    </AnimatedScreen>
  );
}
