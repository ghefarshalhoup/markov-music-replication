import AnimatedScreen from '../components/AnimatedScreen.jsx';

export default function WelcomeConsent({ onAgree, onDecline }) {
  return (
    <AnimatedScreen label="Welcome">
      <span className="eyebrow">Listening study</span>
      <h1>Welcome, and thank you for taking part.</h1>
      <ul className="facts">
        <li><strong>What you will do.</strong> Listen to short piano melodies and answer three quick questions about each.</li>
        <li><strong>How long.</strong> About 10 minutes.</li>
        <li><strong>Anonymous.</strong> Your answers are stored under a number, not your name.</li>
        <li><strong>Voluntary.</strong> You can stop at any time, without giving a reason.</li>
      </ul>
      <p className="muted">There are no right or wrong answers. Please use headphones and go with your first impression.</p>
      <div className="actions">
        <button type="button" className="button button--primary" onClick={onAgree}>I agree &amp; continue</button>
        <button type="button" className="button button--quiet" onClick={onDecline}>I would rather not take part</button>
      </div>
    </AnimatedScreen>
  );
}
