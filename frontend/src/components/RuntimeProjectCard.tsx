import { useState } from 'react';
import { api, type ProjectSignal, type Project } from '../api';
import { coverageLabel } from '../runtime-projects';
import { Badge } from './ui';
import { stamp } from '../presentation';
export default function RuntimeProjectCard({signal,token,onManage,onIncidents}: {signal:ProjectSignal;token:string;onManage:(p:Project)=>void;onIncidents:()=>void}) {
  const [message,setMessage]=useState(''),[busy,setBusy]=useState(false);
  return <section className="card project-panel"><span className="eyebrow">REPOSITORY + DEPLOYMENT MONITORING</span><h2>{signal.project.name}</h2><p>{signal.project.repository_monitoring?.github_url}</p>
    <Badge state={signal.state}>{coverageLabel(signal.state)}</Badge>
    {(signal.runtime_coverage || []).map(c=><section className="card" key={c.deployment.id}>
      <h3>{c.deployment.id} · {c.deployment.platform} · {c.deployment.environment}</h3>
      <p>{c.deployment.application_url || c.deployment.service_id}</p><p>Deployment: {c.deployment.deployment_ref || 'Unknown'}</p><p>Configured revision: <code>{c.deployment.commit_sha || 'Unknown; will not substitute main'}</code></p>
      <p>{coverageLabel(c.state)}</p><p>Last evidence: {c.last_received?stamp(c.last_received):'None received'}</p><p>{c.event_count} retained events · {c.error_count} observed errors · {c.open_incidents ?? 0} open incidents</p>
      <p>Read-only diagnosis · source correlation · human review. No deployment execution.</p>
      {c.deployment.sources.map(s=><div key={s.id}><p>Source: {s.id} · {s.connector}</p><button className="button secondary" disabled={busy} onClick={async()=>{setBusy(true);try{const result=await api<{credential_file:string;receiver_path:string}>('/projects/'+signal.project.id+'/runtime/sources/provision',token,{deployment_id:c.deployment.id,source_id:s.id});setMessage('Receiver: '+result.receiver_path+'\nServer-side credential file: '+result.credential_file+'\nConfigure the collector on the server. No secret was returned to this browser.');}catch(e){setMessage((e as Error).message);}finally{setBusy(false);}}}>Provision source credential</button></div>)}
    </section>)}
    {message && <pre role="status">{message}</pre>}
    <div className="project-actions"><button className="button secondary" onClick={()=>onManage(signal.project)}>Project settings</button><button className="inline-link" onClick={onIncidents}>View runtime incidents</button></div>
  </section>;
}
