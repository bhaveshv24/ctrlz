import { useState } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api, downloadBrief, saveFile, type Receipt } from '../api';
import { Badge } from './ui';
import { navigate } from '../navigation';
import { eventSummary, stamp } from '../presentation';
export default function RuntimeIncident({receipt,token,onBack,onChange}: {receipt:Receipt;token:string;onBack:()=>void;onChange:()=>Promise<void>}) {
  const [tab,setTab]=useState('Evidence'),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const i=receipt.incident, sample=i.runtime_samples?.[0], source=i.source_evidence;
  const act=async(fn:()=>Promise<unknown>)=>{setBusy(true);setError('');try{await fn();await onChange().catch(()=>setError("Action completed, but the latest view could not load. Refresh before taking another action."));}catch(e){setError((e as Error).message);}finally{setBusy(false);}};
  return <div className="runtime-incident-detail">
    <button className="back-button" onClick={onBack}>All incidents</button>
    <div className="page-title incident-title"><div><span className="eyebrow">RUNTIME INCIDENT / {i.id.slice(0,8)}</span><h1>Observed failure. Reviewable response.</h1><p>{i.project_id} · {sample?.deployment_id || 'Deployment unknown'} · {sample?.environment || 'Environment unknown'}</p></div><Badge state={i.status}/></div>
    <div className="alert information"><strong>Read-only investigation.</strong> Recommendations have not executed. Production recovery and regression tests are not verified.</div>
    {i.error && <p className="alert warning">{i.error}</p>}{error && <p role="alert">{error}</p>}
    <div className="workspace-tabs" role="tablist" aria-label="Runtime incident views">{['Evidence','Recommendations','Flight recorder','Receipt'].map(t=><button role="tab" aria-selected={tab===t} key={t} onClick={()=>setTab(t)}>{t}</button>)}</div>
    <section className={"runtime-view runtime-view-"+tab.toLowerCase().replaceAll(" ","-")} role="tabpanel">
      {tab==='Evidence' && <>
        {i.workflow_evidence&&<section className="card"><h2>Approved workflow · affected operation</h2><button className="button secondary" disabled={busy} onClick={()=>act(async()=>{const projects=await api<{id:string;adapter?:string;enabled:boolean;base_url:string|null}[]>('/projects',token);const target=projects.find(p=>p.adapter==='campuspass-v1'&&p.enabled&&p.base_url===String(i.runtime_samples?.[0]?.application_url||''));const id=target?.id||window.prompt('Existing recovery project ID for this same CampusPass deployment');if(!id)return;const r=await api<{incident_id:string}>('/incidents/'+i.id+'/workflow-recovery',token,{project_id:id});window.location.hash='#incident/'+r.incident_id;})}>Investigate affected order recovery · approval still required</button><p>Workflow: {String(i.workflow_evidence.approved_rule.name)}</p><p>Instance: {i.workflow_evidence.instance_id} · Resource: {i.workflow_evidence.resource_id||'Unknown'}</p><p>User association: {i.workflow_evidence.user_id||'Unknown'} · {i.workflow_evidence.identity}</p><p>Observed: {i.workflow_evidence.observation}</p><p>Deployed revision: {i.workflow_evidence.revision}</p><p>Audited source: {i.workflow_evidence.source_revision} · {i.workflow_evidence.source_provenance}</p><p>Expected completion: {String(i.workflow_evidence.approved_rule.completion_condition)}</p><pre>{JSON.stringify(i.workflow_evidence.last_evidence,null,2)}</pre></section>}
        <section className="card"><h2>Observed runtime evidence</h2><p>{i.runtime_summary?.events || 0} events · Affected users: {i.runtime_summary?.affected_users ?? 'Unknown; no reliable user IDs'}</p><p>{i.runtime_summary?.identity_coverage}</p>
          {i.runtime_samples?.map((e,n)=><details key={n} open={n===0}><summary>{String(e.severity)} · {String(e.error_type || 'Runtime failure')} · {String(e.route || 'Route unknown')}</summary><pre>{JSON.stringify(e,null,2)}</pre></details>)}
        </section>
        <section className="card"><h2>Deployed source evidence</h2><p>Mapping: {source?.state || 'Investigation pending'}</p><p>Revision: <code>{source?.commit_sha || 'Unknown; current main was not substituted'}</code></p>
          {source?.uncertainties?.map((u,n)=><p key={n}>{u}</p>)}
          {source?.files?.map(f=><details key={f.path} open><summary>{f.path}:{f.line ?? 'failing line unknown'}</summary><p>{f.provenance} · {f.location_evidence}</p><a href={f.source} target="_blank" rel="noreferrer">Source reference at this revision</a><pre>{f.context}</pre></details>)}
        </section>
        <section className="card"><h2>AI hypothesis</h2><p>Hypothesis based on recorded evidence; no test reproduction has been run.</p><div className="markdown"><Markdown remarkPlugins={[remarkGfm]} skipHtml>{i.diagnosis || 'Diagnosis pending; unavailable providers are reported honestly.'}</Markdown></div>
          {i.runtime_assessment?.uncertainties.map((u,n)=><p key={n}>{u}</p>)}
        </section>
      </>}
      {tab==='Recommendations' && <>
        <p>Human review records a decision about the exact recommendation, deployment, revision and evidence. It grants no execution permission.</p>
        {i.runtime_recommendations?.map(r=><article className="card" key={r.id}><span className="eyebrow">{r.category.replaceAll('_',' ')}</span><h2>{r.summary}</h2><p>{r.rationale}</p><p>Evidence: {r.evidence_ids.join(', ')}</p><p>Target: {String(sample?.deployment_id)} · {String(sample?.environment)} · {source?.commit_sha || 'Unknown revision'}</p>{r.proposed_change && <pre>{r.proposed_change}</pre>}
          <h3>Required verification</h3><ol>{r.verification_plan.map((v,n)=><li key={n}>{v}</li>)}</ol><h3>Risks</h3>{r.risks.map((risk,n)=><p key={n}>{risk}</p>)}
          <p>{r.review_policy?.reason}</p>
          {i.status==='awaiting_review' && <div className="project-actions"><button className="button primary" disabled={busy || r.review_policy?.reviewable===false} onClick={()=>act(()=>api('/incidents/'+i.id+'/recommendations/review',token,{recommendation_id:r.id,review_hash:r.review_hash,decision:'accept'}))}>Accept recommendation · no execution</button><button className="button secondary" disabled={busy || r.review_policy?.reviewable===false} onClick={()=>act(()=>api('/incidents/'+i.id+'/recommendations/review',token,{recommendation_id:r.id,review_hash:r.review_hash,decision:'decline'}))}>Decline recommendation</button></div>}
        </article>)}
        {i.recommendation_review && <p role="status">Review recorded: {i.recommendation_review.decision}. No operation executed; recovery remains unverified.</p>}
        <section className="card"><h2>Investigate code fix</h2><p>Download sanitized evidence, then import the matching deployed revision in the existing Repository repair workflow. Paste the relevant context and confirm expected behavior. Its normal sandbox and immutable acceptance checks still apply.</p>
          <button className="button secondary" onClick={()=>act(async()=>saveFile('runtime-repair-context-'+i.id+'.json',JSON.stringify(await api('/incidents/'+i.id+'/repair-context',token),null,2)))}>Download repair context</button>
          <button className="inline-link" onClick={()=>navigate('continuity')}>Open Repository repair</button>
        </section>
      </>}
      {tab==='Flight recorder' && <section className="card recorder">{receipt.events.map(e=><details className="flight-event" key={e.id}><summary>#{e.id} · {e.stage} · {stamp(e.timestamp)} · {eventSummary(e)}</summary><pre>{JSON.stringify(e.payload,null,2)}</pre></details>)}</section>}
      {tab==='Receipt' && <section className="card receipt-card"><h2>Runtime investigation receipt</h2><p>Incident: {i.id}</p><p>Provider: {receipt.reasoning_provider} · {receipt.model || 'Model not recorded'}</p><p>State: {i.status}. Recovery verified: No. A reviewed recommendation is not an executed recovery.</p><p>{receipt.integrity?.snapshot_digest}</p><button className="button primary" onClick={()=>saveFile('ctrlz-'+i.id+'.json',JSON.stringify(receipt,null,2))}>Download JSON</button><button className="button secondary" onClick={()=>act(()=>downloadBrief(i.id,token))}>Download readable brief</button></section>}
    </section>
    {['blocked','escalated','awaiting_review','recommendation_reviewed'].includes(i.status) && <button className="button secondary" disabled={busy} onClick={()=>act(()=>api('/incidents/'+i.id+'/retry',token,{}))}>Reinvestigate with current evidence</button>}
  </div>;
}
