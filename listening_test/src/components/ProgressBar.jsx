export default function ProgressBar({ current, total }) {
  const share = total ? current / total : 0;
  return (
    <div className="progress" aria-label={`Clip ${current} of ${total}`}>
      <span className="progress__label">Clip {current} of {total}</span>
      <div className="progress__track" role="progressbar" aria-valuemin={1} aria-valuemax={total} aria-valuenow={current}>
        <div className="progress__fill" style={{ transform: `scaleX(${share})` }} />
      </div>
    </div>
  );
}
