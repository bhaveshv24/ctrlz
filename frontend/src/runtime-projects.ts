import type { Project, RuntimeDeployment } from './api';
export const emptyDeployment = (index: number): RuntimeDeployment => ({
  id: 'deployment-' + index, platform: 'vps', service_id: '', environment: 'staging',
  application_url: null, deployment_ref: null, commit_sha: null,
  sources: [{id: 'logs', connector: 'generic-events'}],
});
export function runtimeProject(id: string, name: string, github_url: string, deployments: RuntimeDeployment[], enabled = false, preferred_ref?: string): Project {
  return {id, name, project_type: 'repository-deployment', adapter: 'runtime-v1', base_url: null, enabled, demo_enabled: false,
    contract: {allowed: [], approval_required: [], max_actions: 3, invariants: ['no_destructive_operations','idempotent_mutations']},
    repository_monitoring: {github_url, preferred_ref: preferred_ref || null, deployments}};
}
export const coverageLabel = (state: string) => ({
  observing: 'Receiving telemetry · health unknown', no_recent_events: 'No recent telemetry · health unknown',
  incomplete_configuration: 'Source credentials need setup', error_detected: 'Runtime errors observed', paused: 'Monitoring disabled',
}[state] || 'Connection unknown');
