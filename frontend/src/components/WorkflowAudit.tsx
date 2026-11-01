import { useCallback, useEffect, useRef, useState } from 'react';
import { api, API, saveBlob, type Project } from '../api';
import { Dialog, Badge } from './ui';

type Rule = {instrumentation_driver?:string;id:string;name:string;description:string;evidence:{path:string;line:number}[];start_condition:string;completion_condition:string;deadline_seconds:number;technique:string;classification:string;allowed_fields:string[];hooks:{fields:Record<string,string>}[];existing_signals:string[];missing_signals:string[];uncertainties:string[];privacy:string;overhead:string;permissions:string[];independent_verification:string;coverage_limits:string[]};
type Proposal = {revision_review?:{revision:string;previous_revision:string;observer_sha256:string};id:string;audit_id:string;deployment_id:string;source_id:string;environment:string;revision:string;status:string;provenance:string;rule:Rule;proposal_hash:string;approval?:{hash:string;actor:string;timestamp:number};patch?:{diff:string;changed_files:string[];source_digest:string;instrumentation_digest:string};verification?:{passed:boolean;checks:Record<string,boolean>;baseline?:{cases:unknown[]};candidate?:{cases:unknown[]};instrumentation?:{cases:unknown[]};limitations:string[]};activation?:{revision:string};monitoring_warning?:string;error?:string;detail?:string;monitoring?:{counts:Record<string,number>;incomplete:unknown[]}};
type Audit = {id:string;status:string;summary?:string;error?:string;detail?:string;limitations?:string[];provider?:string;model?:string};
type Data = {audits:Audit[];proposals:Proposal[]};

export default function WorkflowAudit({project,token,onClose}:{project:Project;token:string;onClose:()=>void}) {
  const deployments=project.repository_monitoring!.deployments;
  const [deployment,setDeployment]=useState(deployments[0].id),[data,setData]=useState<Data>({audits:[],proposals:[]}),[busy,setBusy]=useState(false),[error,setError]=useState(''),[file,setFile]=useState<File|null>(null),[connectionError,setConnectionError]=useState('');
  const requestVersion = useRef(0);
  const reload = useCallback(async () => {
    const version = ++requestVersion.current;
    const result = await api<Data>('/projects/'+project.id+'/workflow-audits',token).catch(error => {
      if (version === requestVersion.current) throw error;
      return null;
    });
    if (!result || version !== requestVersion.current) return;
    setData(result); setConnectionError('');
  }, [project.id, token]);
  useEffect(() => {
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try { await reload(); }
      catch (error) { if (!disposed) setConnectionError((error as Error).message); }
      finally { if (!disposed) timer = setTimeout(poll, 3000); }
    };
    void poll();
    return () => { disposed = true; clearTimeout(timer); requestVersion.current++; };
  }, [reload]);
  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError('');
    try {
      await fn();
      await reload().catch(error => setConnectionError((error as Error).message));
      return true;
    } catch (error) { setError((error as Error).message); return false; }
    finally { setBusy(false); }
  };
  const selected=deployments.find(d=>d.id===deployment) || deployments[0];
  useEffect(() => { if (!deployments.some(d => d.id === deployment)) setDeployment(deployments[0].id); }, [deployments, deployment]);
  return <Dialog title="AI Workflow Audit" onClose={onClose} busy={busy}>
    <p>Discover silent-failure gaps, review completion rules, then generate an observability-only patch. Nothing is committed or deployed.</p>
    <label>Deployment / environment<select value={deployment} onChange={e=>setDeployment(e.target.value)}>{deployments.map(d=><option key={d.id} value={d.id}>{d.id} · {d.environment}</option>)}</select></label>
    <details><summary>Optional supplied source snapshot</summary><p>ZIP source is inert and content-pinned. Repository identity and deployed Git revision remain unverified. Secrets, databases and generated dependencies are excluded.</p><input aria-label="Source snapshot ZIP" type="file" accept=".zip" onChange={e=>setFile(e.target.files?.[0]||null)}/></details>
    <button className="button primary" disabled={busy} onClick={()=>act(async()=>{
      const target={deployment_id:deployment,source_id:selected.sources[0].id};
      if(!file)return api('/projects/'+project.id+'/workflow-audits',token,target);
      const response=await fetch(API+'/projects/'+project.id+'/workflow-audits/snapshot?'+new URLSearchParams(target),{signal:AbortSignal.timeout(90000),method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/zip'},body:file});
      if(!response.ok)throw Error('Source audit request rejected: HTTP '+response.status);
    })}>Analyze workflows for silent failures</button>
    {error&&<p role="alert">{error}</p>}{connectionError&&<p role="status">Connection interrupted; retrying: {connectionError}</p>}
    {data.audits.slice(0,1).map(a=><section className="card" key={a.id}><Badge state={a.status}/><p>{a.summary||'Audit progress: '+a.status}</p><p>{a.provider} · {a.model}</p>{a.error&&<p role="alert">{a.error}: {a.detail}</p>}{a.limitations?.map((v,n)=><p key={n}>{v}</p>)}</section>)}
    {data.audits.length>1&&<details><summary>Previous audit attempts ({data.audits.length-1})</summary>{data.audits.slice(1).map(a=><section className="card" key={a.id}><Badge state={a.status}/><p>{a.id}</p><p>{a.summary||a.error}</p><p>{a.detail}</p></section>)}</details>}
    {data.proposals.map(p=><WorkflowProposal key={p.id} proposal={p} project={project} token={token} busy={busy} act={act}/>)}
  </Dialog>;
}

export function WorkflowProposal({proposal:p,project,token,busy,act}:{proposal:Proposal;project:Project;token:string;busy:boolean;act:(fn:()=>Promise<unknown>)=>Promise<boolean>}) {
  const [editing,setEditing]=useState(false),[completion,setCompletion]=useState(p.rule.completion_condition),[deadline,setDeadline]=useState(p.rule.deadline_seconds),[technique,setTechnique]=useState(p.rule.technique),[fields,setFields]=useState(p.rule.allowed_fields),[revision,setRevision]=useState(''),[reconciler,setReconciler]=useState(''),[dependencies,setDependencies]=useState(false);
  useEffect(()=>{setCompletion(p.rule.completion_condition);setDeadline(p.rule.deadline_seconds);setTechnique(p.rule.technique);setFields(p.rule.allowed_fields);setEditing(false);},[p.proposal_hash]);
  const target=project.repository_monitoring!.deployments.find(d=>d.id===p.deployment_id);
  const decide=(decision:string,rule?:Rule)=>act(()=>api('/workflow-proposals/'+p.id+'/decision',token,{proposal_hash:p.proposal_hash,decision,...(rule?{rule}:{})}));
  const download=(kind:string)=>act(async()=>{const r=await fetch(API+'/workflow-proposals/'+p.id+'/artifacts/'+kind,{signal:AbortSignal.timeout(90000),headers:{Authorization:'Bearer '+token}});if(!r.ok)throw Error('Artifact download failed');saveBlob(kind==='patch'?'instrumentation.patch':'instrumented-source.zip', await r.blob());});
  return <article className="card"><h2>{p.rule.name}</h2><Badge state={p.status}/><p>{p.rule.description}</p><p>{p.deployment_id} · {p.environment} · <code>{p.revision}</code></p><p>{p.provenance}</p>
    {['monitoring_active','deployment_observed','monitoring_degraded'].includes(p.status)&&<details><summary>Review a new deployed revision</summary><p>For the trusted CampusPass observer only: verifies unchanged observer bytes, factory attachment and durable models, then invalidates the old approval. No code is generated or deployed.</p><label>New deployed Git SHA<input value={revision} onChange={e=>setRevision(e.target.value)} placeholder="40-character deployed commit"/></label><button className="button secondary" disabled={busy||!/^[0-9a-f]{40}$/.test(revision)} onClick={()=>act(()=>api('/workflow-proposals/'+p.id+'/revision-review',token,{revision}))}>Verify revision and request renewed review</button></details>}
    <p>Evidence: {p.rule.evidence.map(e=>e.path+':'+e.line).join(', ')}</p><p>Gap: {p.rule.classification}</p><p>Instrumentation strategy: {p.rule.instrumentation_driver||'function_hooks'}</p><p>Start: {p.rule.start_condition}</p><p>Completion: {p.rule.completion_condition}</p><p>Proposed deadline: {p.rule.deadline_seconds}s · Technique: {p.rule.technique}</p>
    <details><summary>Signals, privacy, overhead and uncertainty</summary><p>Existing: {p.rule.existing_signals.join('; ')||'None established'}</p><p>Missing: {p.rule.missing_signals.join('; ')}</p><p>{p.rule.privacy}</p><p>Allowed fields: {p.rule.allowed_fields.join(', ')}</p><p>{p.rule.overhead}</p><p>Permissions: {p.rule.permissions.join('; ')}</p><p>Independent verification: {p.rule.independent_verification}</p>{[...p.rule.uncertainties,...p.rule.coverage_limits].map((v,n)=><p key={n}>{v}</p>)}</details>
    {p.error&&<p role="alert">{p.error}: {p.detail}</p>}
    {p.approval&&<p>Monitoring-only approval: {p.approval.actor} · {new Date(p.approval.timestamp*1000).toISOString()} · <code>{p.approval.hash}</code>. No recovery or deployment is authorized.</p>}
    {!['generating','monitoring_active','deployment_observed'].includes(p.status)&&<div className="project-actions"><button className="button primary" disabled={busy} onClick={()=>decide('approve')}>Approve monitoring rule</button><button className="button secondary" disabled={busy} onClick={()=>decide('reject')}>Reject rule</button><button className="inline-link" onClick={()=>setEditing(!editing)}>Edit monitoring rule</button></div>}
    {editing&&<section><label>Expected completion<textarea value={completion} onChange={e=>setCompletion(e.target.value)}/></label><label>Maximum completion time (seconds)<input type="number" min={1} max={86400} value={deadline} onChange={e=>setDeadline(Number(e.target.value))}/></label><label>Monitoring technique<select value={technique} onChange={e=>setTechnique(e.target.value)}>{['existing_telemetry','zero_code','read_only_reconciliation','instrumentation','insufficient'].map(x=><option key={x}>{x}</option>)}</select></label>
      {['instance_id','resource_id','request_id','trace_id','user_id','parent_id'].map(field=><label className="checkbox-label" key={field}><input type="checkbox" checked={fields.includes(field)} disabled={field==='instance_id'} onChange={e=>setFields(old=>e.target.checked?[...old,field]:old.filter(x=>x!==field))}/>{field}</label>)}
      <button className="button secondary" disabled={busy} onClick={()=>decide('edit',{...p.rule,completion_condition:completion,deadline_seconds:deadline,technique,allowed_fields:fields,hooks:p.rule.hooks.map(h=>({...h,fields:Object.fromEntries(Object.entries(h.fields).filter(([k])=>fields.includes(k)))}))}).then(ok=>{if(ok)setEditing(false);})}>Save edits · invalidates approval</button></section>}
    {p.status==='approved'&&p.rule.technique==='instrumentation'&&<><label className="checkbox-label"><input type="checkbox" checked={dependencies} onChange={e=>setDependencies(e.target.checked)}/>Separately authorize declared dependency setup inside Docker (networked package download; tests remain offline)</label><button className="button primary" disabled={busy} onClick={()=>act(()=>api('/workflow-proposals/'+p.id+'/generate',token,{approval_hash:p.approval!.hash,install_dependencies:dependencies}))}>Generate and verify instrumentation</button></>}
    {p.patch&&<details open><summary>Review instrumentation diff · {p.patch.changed_files.join(', ')}</summary><pre>{p.patch.diff}</pre><button className="button secondary" onClick={()=>download('patch')}>Download patch</button><button className="button secondary" onClick={()=>download('source')}>Download instrumented source</button></details>}
    {p.verification&&<section><h3>Actual isolated verification</h3><p>{p.verification.passed?'Tests passed; awaiting developer review/deployment':'Verification failed; do not deploy'}</p><pre>{JSON.stringify(p.verification.checks,null,2)}</pre><p>Baseline: {p.verification.baseline?.cases.length} cases · Candidate original tests: {p.verification.candidate?.cases.length} · With instrumentation tests: {p.verification.instrumentation?.cases.length}</p>{p.verification.limitations.map((v,n)=><p key={n}>{v}</p>)}</section>}
    {target && (p.status==='awaiting_deployment'||p.status==='approved'&&['existing_telemetry','read_only_reconciliation'].includes(p.rule.technique))&&<section><h3>Deployment guidance</h3><p>{p.revision_review?'The deployed CampusPass observer was verified unchanged. No new patch was generated. Configure CTRLZ_WORKFLOW_ENABLED=true, the approved CTRLZ_DEPLOYED_REVISION and the two private telemetry receivers using the hosted demo guide. Preserve source credentials and the pseudonym key.':p.rule.instrumentation_driver==='campuspass_committed_session'?'Review and deploy the trusted observer patch yourself. Configure CTRLZ_WORKFLOW_ENABLED=true and CTRLZ_DEPLOYED_REVISION plus its private receiver credentials using the hosted demo guide.':p.patch?'Review and deploy the patch yourself. Configure CTRLZ_OBSERVE_ENABLED=1 and CTRLZ_OBSERVE_REVISION.':'Configure the approved existing telemetry/read-only source using the exact approved proposal hash as artifact_digest.'} Never put source credentials in client code.</p><p>Lifecycle delivery is best-effort. An independent authorized checker performs one indexed read only when CtrlZ dispatches an overdue operation. Completed operations cancel checks.</p><label>Actually deployed revision<input value={revision} placeholder={target.platform==='local'?(p.patch?'sha256:'+p.patch.source_digest:p.revision):'Full deployed Git commit SHA'} onChange={e=>setRevision(e.target.value)}/></label><label>Independent reconciliation source<select value={reconciler} onChange={e=>setReconciler(e.target.value)}><option value="">None · missing completions remain uncertain</option>{target.sources.filter(s=>s.id!==p.source_id).map(s=><option key={s.id}>{s.id}</option>)}</select></label><button className="button primary" disabled={busy||!revision} onClick={()=>act(()=>api('/workflow-proposals/'+p.id+'/activate',token,{approval_hash:p.approval!.hash,revision,artifact_digest:p.patch?.instrumentation_digest||p.proposal_hash,reconciliation_source_id:reconciler||null,check_mode:reconciler?'deadline_targeted':'snapshot'}))}>Record deployed version · wait for telemetry</button></section>}
    {!target && <p role="status">This deployment is no longer configured. Its recorded evidence remains available; restore the deployment before activation.</p>}
    {p.activation&&<p>Bound deployed revision: {p.activation.revision}. Instrumentation is active only after matching authenticated telemetry is received.</p>}
    {p.monitoring_warning&&<p role="status">{p.monitoring_warning}</p>}
    {p.monitoring&&<details><summary>Workflow coverage and incomplete operations</summary><pre>{JSON.stringify(p.monitoring,null,2)}</pre></details>}
  </article>;
}
