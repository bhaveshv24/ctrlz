export function repositoryAction(mode: 'repair' | 'complete', status: 'failing' | 'healthy' | 'blocked' | null, executionEnabled: boolean, supported: boolean, failedInspection = false) {
  const startsChanges = status === 'failing' || (mode === 'complete' && status === 'healthy');
  return {
    startsChanges,
    disabled: startsChanges && (!executionEnabled || !supported),
    label: startsChanges ? (mode === 'complete' ? 'Complete project' : 'Fix failing code') : failedInspection ? 'Retry inspection' : status ? 'Inspect again' : 'Inspect repository',
  };
}
