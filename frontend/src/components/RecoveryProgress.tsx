import type {CSSProperties} from 'react';
type Stage = {name: string; recorded: boolean; failed: boolean};
export default function RecoveryProgress({stages, active}: {stages: Stage[]; active: boolean}) {
  const recorded = stages.filter(stage => stage.recorded).length;
  const failed = stages.some(stage => stage.failed);
  return <section className={`recovery-progress ${active ? 'is-active' : ''} ${failed ? 'has-failure' : ''}`} aria-label="Recovery progress">
    <div className="recovery-progress-heading"><strong>{active ? 'Recovery in progress' : failed ? 'Recovery needs review' : 'Recorded recovery stages'}</strong><span>{recorded} of {stages.length} stages recorded</span></div>
    <div className="recovery-progress-track" role="progressbar" aria-label="Recorded recovery stages" aria-valuemin={0} aria-valuemax={stages.length} aria-valuenow={recorded} aria-valuetext={`${recorded} of ${stages.length} stages recorded${active ? '; recovery is running' : ''}`}>
      <div className="recovery-progress-fill" style={{'--progress': stages.length ? recorded / stages.length : 0} as CSSProperties} />
      {active && <div className="recovery-progress-motion" />}
    </div>
    <ol className="recovery-progress-stages">{stages.map(stage => <li key={stage.name} className={stage.failed ? 'failed' : stage.recorded ? 'recorded' : ''}>{stage.name}<span>{stage.failed ? 'Failed' : stage.recorded ? 'Recorded' : 'Pending'}</span></li>)}</ol>
  </section>;
}
