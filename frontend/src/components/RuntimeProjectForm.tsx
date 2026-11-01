import { useState } from 'react';
import { api, type Project, type RuntimeDeployment } from '../api';
import { emptyDeployment, runtimeProject, updatePrimarySource, nextDeployment } from '../runtime-projects';
import { Dialog } from './ui';

export default function RuntimeProjectForm({project, token, busy, onClose, onBack, onSubmit, submitError = ""}: {
  submitError?: string; project: Project | null; token: string; busy: boolean; onClose: () => void;
  onBack: () => void; onSubmit: (project: unknown) => Promise<void>;
}) {
  const [step,setStep]=useState(0),[id,setId]=useState(project?.id || ''),[name,setName]=useState(project?.name || ''),
    [repo,setRepo]=useState(project?.repository_monitoring?.github_url || ''),[ref,setRef]=useState(project?.repository_monitoring?.preferred_ref || ''),
    [deployments,setDeployments]=useState<RuntimeDeployment[]>(project?.repository_monitoring?.deployments || [emptyDeployment(1)]),
    [enabled,setEnabled]=useState(project?.enabled ?? false),[test,setTest]=useState<unknown>(null),[testing,setTesting]=useState(false),[error,setError]=useState('');
  const draft=()=>({...project, ...runtimeProject(id,name,repo,deployments,enabled,ref)});
  const update=(index: number, change: Partial<RuntimeDeployment>)=>{setDeployments(old=>old.map((d,n)=>n===index?{...d,...change}:d));setTest(null);};
  return <Dialog title="Repository + Deployment Monitoring" onClose={onClose} busy={busy || testing}>
    <p className="dialog-copy">Connect source, identify deployments, then configure telemetry. Recommendations are read-only and require review.</p>
    <ol className="operation-list"><li>Repository</li><li>Deployments and telemetry</li><li>Test and enable</li></ol>
    <form onSubmit={e=>{e.preventDefault();if(step<2)setStep(step+1);else void onSubmit(draft());}}>
      {step===0 && <>
        <label>Project name<input required maxLength={100} value={name} onChange={e=>setName(e.target.value)}/></label>
        <label>Project ID<input required pattern="[a-z][a-z0-9_-]{0,40}" disabled={!!project} value={id} onChange={e=>setId(e.target.value)}/></label>
        <label>GitHub repository<input required placeholder="https://github.com/owner/repository" value={repo} onChange={e=>{setRepo(e.target.value);setTest(null);}}/></label>
        <details><summary>Optional repository preference</summary><label>Branch preference<input value={ref} onChange={e=>setRef(e.target.value)}/><small>Advisory only. Diagnosis uses the deployed commit; it never substitutes this branch.</small></label></details>
      </>}
      {step===1 && <>
        {deployments.map((d,n)=><fieldset className="card" key={n}><legend>Deployment {n+1}</legend>
          <label>Deployment ID<input required pattern="[a-zA-Z0-9][a-zA-Z0-9_.-]{0,99}" value={d.id} onChange={e=>update(n,{id:e.target.value})}/></label>
          <label>Platform<select value={d.platform} onChange={e=>update(n,{platform:e.target.value as RuntimeDeployment['platform'],sources:updatePrimarySource(d,'generic-events')})}>
            <option value="vps">VPS / server · log collector</option><option value="docker">Docker · exported application logs</option><option value="local">Local · log collector</option><option value="vercel">Vercel</option><option value="aws">AWS · generic collector only</option>
          </select></label>
          <label>{d.platform==='vercel'?'Vercel project ID':'Service identifier'}<input required value={d.service_id} onChange={e=>update(n,{service_id:e.target.value})}/></label>
          <label>Environment<input required value={d.environment} onChange={e=>update(n,{environment:e.target.value})}/></label>
          <label>Telemetry source<select value={d.sources[0].connector} onChange={e=>update(n,{sources:updatePrimarySource(d,e.target.value as 'generic-events'|'vercel-drain')})}>
            <option value="generic-events">Authenticated structured events / JSON log collector</option>
            {d.platform==='vercel' && <option value="vercel-drain">Signed Vercel Log Drain · eligible paid plan + public HTTPS receiver</option>}
          </select></label>
          <label>Actual deployment reference (optional)<input value={d.deployment_ref || ''} onChange={e=>update(n,{deployment_ref:e.target.value || null})}/></label>
          <label>Deployed commit SHA (optional)<input pattern="[0-9a-f]{40}" placeholder="Full 40-character SHA; unknown if unavailable" value={d.commit_sha || ''} onChange={e=>update(n,{commit_sha:e.target.value || null})}/></label>
          <details><summary>Advanced source hints</summary><label>Repository-relative source files (one per line, optional)<textarea rows={3} value={(d.source_paths || []).join('\n')} onChange={e=>update(n,{source_paths:e.target.value.split('\n').map(v=>v.trim()).filter(Boolean)})}/><small>Used only when telemetry lacks stack frames. These are operator hints, never claimed as observed failing lines.</small></label></details>
          <label>Application URL (optional)<input type="url" value={d.application_url || ''} onChange={e=>update(n,{application_url:e.target.value || null})}/><small>Informational only. No custom health endpoint is required.</small></label>
          {d.platform==='vercel' && <label>Vercel team ID (optional)<input value={d.vercel_team_id || ''} onChange={e=>update(n,{vercel_team_id:e.target.value || null})}/></label>}
          {d.sources.slice(1).map((s,index)=><label key={index}>Independent reconciliation source ID<input value={s.id} onChange={e=>update(n,{sources:d.sources.map((old,i)=>i===index+1?{...old,id:e.target.value}:old)})}/></label>)}
          {d.sources.length<2&&<button type="button" className="button secondary" onClick={()=>update(n,{sources:[...d.sources,{id:'reconciliation',connector:'generic-events'}]})}>Add independent workflow reconciliation source</button>}
          {deployments.length>1 && <button type="button" className="inline-link" onClick={()=>{setDeployments(old=>old.filter((_,i)=>i!==n));setTest(null);}}>Remove this deployment</button>}
        </fieldset>)}
        <button className="button secondary" type="button" disabled={deployments.length>=12} onClick={()=>{setDeployments(old=>[...old,nextDeployment(old)]);setTest(null);}}>Add deployment / environment</button>
        <p className="subtle">Native CloudWatch and OTLP ingestion are not implemented. Structured-event forwarding works across hosts. Browser exceptions require client-side collection.</p>
      </>}
      {step===2 && <>
        <p>{repo} · {deployments.length} deployment(s). Capabilities: runtime evidence, exact-revision source analysis, AI diagnosis and reviewable recommendations. Execution is disabled.</p>
        <button type="button" className="button secondary" disabled={testing} onClick={async()=>{setTesting(true);setError('');try{setTest(await api('/runtime-projects/test',token,draft()));}catch(e){setError((e as Error).message);}finally{setTesting(false);}}}>{testing?'Testing…':'Test repository and provider metadata'}</button>
        {test!=null && <pre>{JSON.stringify(test,null,2)}</pre>}
        <p className="dialog-copy">After saving, provision each telemetry source on its project card. Credentials stay on the server. No data means unknown health, even after this connection test.</p>
        <label className="checkbox-label"><input type="checkbox" checked={enabled} onChange={e=>setEnabled(e.target.checked)}/>Enable monitoring and authenticated event ingestion</label>
        <details><summary>Optional next step: AI Workflow Audit</summary><p>After saving, choose “AI Workflow Audit · optional” on this project card to analyze silent failures, review completion rules, and generate a verified instrumentation patch. Existing runtime monitoring does not require this audit.</p></details>
      </>}
      {(error || submitError) && <p role="alert">{error || submitError}</p>}
      <div className="dialog-actions"><button className="button secondary" type="button" onClick={()=>step?setStep(step-1):onBack()}>Back</button><button className="button primary" disabled={busy || testing}>{step<2?'Next':'Save monitoring project'}</button></div>
    </form>
  </Dialog>;
}
