import { useState } from 'react';
import { ArrowRight, FolderGit2, GitBranch, Radio, Settings, ShieldCheck, Sparkles } from 'lucide-react';
import { api, type ProjectSignal, type Project } from '../api';
import { coverageLabel } from '../runtime-projects';
import { Badge } from './ui';
import { stamp } from '../presentation';
import WorkflowAudit from './WorkflowAudit';

export default function RuntimeProjectCard({signal,token,onManage,onIncidents}: {signal:ProjectSignal;token:string;onManage:(p:Project)=>void;onIncidents:()=>void}) {
  const [message,setMessage]=useState(''),[busy,setBusy]=useState(false);
  const [workflowAudit,setWorkflowAudit]=useState(false);
  return <section className="card project-panel runtime-project-panel">
    <header className="runtime-project-header">
      <div className="runtime-project-identity">
        <span className="project-symbol"><FolderGit2 size={21} aria-hidden="true" /></span>
        <div><h2>{signal.project.name}</h2><p className="runtime-repository">{signal.project.repository_monitoring?.github_url}</p></div>
      </div>
      <Badge state={signal.state}>{coverageLabel(signal.state)}</Badge>
    </header>
    <div className="runtime-deployments">
      {(signal.runtime_coverage || []).map(c=><section className="runtime-deployment" key={c.deployment.id} aria-label={'Deployment '+c.deployment.id}>
        <div className="runtime-deployment-heading"><h3><Radio size={15} aria-hidden="true" />{c.deployment.id}</h3><span className="runtime-environment">{c.deployment.platform} / {c.deployment.environment}</span></div>
        <p className="runtime-service">{c.deployment.application_url || c.deployment.service_id}</p>
        <dl className="runtime-deployment-details">
          <div><dt>Deployment reference</dt><dd>{c.deployment.deployment_ref || 'Not provided'}</dd></div>
          <div><dt><GitBranch size={12} aria-hidden="true" />Configured revision</dt><dd><code title={c.deployment.commit_sha || undefined}>{c.deployment.commit_sha || 'Unknown; will not substitute main'}</code></dd></div>
          <div><dt>Evidence status</dt><dd>{coverageLabel(c.state)}</dd></div>
          <div><dt>Last evidence</dt><dd>{c.last_received?stamp(c.last_received):'None received'}</dd></div>
        </dl>
        <dl className="runtime-evidence-counts">
          <div><dd>{c.event_count}</dd><dt>Retained events</dt></div>
          <div><dd>{c.error_count}</dd><dt>Observed errors</dt></div>
          <div><dd>{c.open_incidents ?? 0}</dd><dt>Open incidents</dt></div>
        </dl>
        <div className="runtime-sources">
          <h4>Telemetry sources</h4>
          <p className="runtime-source-help">Set up each collector with its server-side credential.</p>
          {c.deployment.sources.map(s=><div className="runtime-source-row" key={s.id}>
            <div><strong>{s.id}</strong><span>{s.connector}</span></div>
            <button className="button secondary" disabled={busy} aria-label={'Set up source '+s.id+' for '+c.deployment.id} onClick={async()=>{setBusy(true);try{const result=await api<{credential_file:string;receiver_path:string}>('/projects/'+signal.project.id+'/runtime/sources/provision',token,{deployment_id:c.deployment.id,source_id:s.id});setMessage('Receiver: '+result.receiver_path+'\nServer-side credential file: '+result.credential_file+'\nConfigure the collector on the server. No secret was returned to this browser.');}catch(e){setMessage((e as Error).message);}finally{setBusy(false);}}}>Set up source<ArrowRight size={13} aria-hidden="true" /></button>
          </div>)}
        </div>
      </section>)}
    </div>
    {message && <pre className="runtime-setup-message" role="status">{message}</pre>}
    <div className="runtime-audit-entry">
      <div><h3><Sparkles size={15} aria-hidden="true" />Find silent workflow failures</h3><p>Review source evidence and proposed monitoring rules.</p></div>
      <button className="button secondary" onClick={()=>setWorkflowAudit(true)}>AI Workflow Audit / optional</button>
    </div>
    {workflowAudit&&<WorkflowAudit project={signal.project} token={token} onClose={()=>setWorkflowAudit(false)}/>}
    <footer className="runtime-project-footer">
      <p className="runtime-capabilities"><ShieldCheck size={14} aria-hidden="true" />Read-only diagnosis / source correlation / human review. No deployment execution.</p>
      <div className="project-actions"><button className="button secondary" onClick={()=>onManage(signal.project)}><Settings size={14} aria-hidden="true" />Project settings</button><button className="inline-link" onClick={onIncidents}>View runtime incidents<ArrowRight size={14} aria-hidden="true" /></button></div>
    </footer>
  </section>;
}
