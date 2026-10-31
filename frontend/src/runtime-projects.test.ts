import { expect, it, vi } from 'vitest';
import type { ReactNode } from 'react';
vi.mock('./components/ui', async importOriginal => ({...await importOriginal<typeof import('./components/ui')>(), Dialog: ({children}: {children: ReactNode}) => createElement('section', null, children)}));
import { renderToStaticMarkup } from 'react-dom/server';
import { coverageLabel, emptyDeployment, runtimeProject } from './runtime-projects';
import RuntimeProjectForm from './components/RuntimeProjectForm';
import RuntimeProjectCard from './components/RuntimeProjectCard';
import RuntimeIncident from './components/RuntimeIncident';
import ProjectDialog from './components/ProjectDialog';
import type { Receipt } from './api';
import { createElement } from 'react';
const deployment={...emptyDeployment(1),service_id:'api',environment:'staging'};
const project=runtimeProject('runtime','Runtime','https://github.com/owner/repo',[deployment]);
it('creates a distinct read-only project with no fake backend URL',()=>{
 expect(project.project_type).toBe('repository-deployment');expect(project.base_url).toBeNull();expect(project.adapter).toBe('runtime-v1');expect(project.contract.allowed).toEqual([]);expect(project.enabled).toBe(false);
});
it('keeps multiple deployment environments separate',()=>{
 const other={...deployment,id:'production',environment:'production'};expect(runtimeProject('runtime','Runtime','owner/repo',[deployment,other]).repository_monitoring?.deployments.map(d=>d.environment)).toEqual(['staging','production']);
});
it('does not describe empty telemetry or receiving telemetry as proven health',()=>{
 expect(coverageLabel('no_recent_events')).toContain('health unknown');expect(coverageLabel('observing')).toContain('health unknown');expect(coverageLabel('incomplete_configuration')).toContain('setup');
});
it('preserves generic HTTP and CampusPass choices alongside new onboarding',()=>{
 const html=renderToStaticMarkup(createElement(ProjectDialog,{project:'new',busy:false,onClose:()=>{},onSubmit:async()=>{}}));
 expect(html).toContain('Generic HTTP service');expect(html).toContain('CampusPass');expect(html).toContain('Repository + Deployment Monitoring');
});
it('renders structured onboarding without requiring a backend origin',()=>{
 const html=renderToStaticMarkup(createElement(RuntimeProjectForm,{project:null,token:'',busy:false,onClose:()=>{},onBack:()=>{},onSubmit:async()=>{}}));
 expect(html).toContain('GitHub repository');expect(html).not.toContain('Backend origin');expect(html).not.toContain('textarea');
});
it('project coverage shows deployment, revision uncertainty and evidence freshness',()=>{
 const html=renderToStaticMarkup(createElement(RuntimeProjectCard,{signal:{project,state:'no_recent_events',latest:null,history:[],runtime_coverage:[{deployment,state:'no_recent_events',credentials_configured:true,last_received:null,last_event_at:null,event_count:0,error_count:0,measured_affected_users:null,execution_permitted:false}]},token:'',onManage:()=>{},onIncidents:()=>{}}));
 expect(html).toContain('staging');expect(html).toContain('None received');expect(html).toContain('Unknown; will not substitute main');expect(html).toContain('No deployment execution');
});
it('runtime incident separates observed evidence, AI hypothesis and unverified recovery',()=>{
 const receipt:Receipt={schema_version:1,integrity:{algorithm:'sha256',snapshot_digest:'test',scope:'test fixture'},success:false,reasoning_provider:'explicit test fixture',events:[],incident:{id:'runtime',project_id:'runtime',kind:'runtime',resource:'fingerprint',status:'awaiting_review',created:1,updated:2,runtime_samples:[{deployment_id:'staging',environment:'staging',error_type:'TypeError',message:'bad input'}],source_evidence:{state:'exact_github_revision',commit_sha:'a'.repeat(40),files:[{path:'src/app.py',line:7,context:'raise ValueError()',source:'https://github.com/owner/repo/blob/'+('a'.repeat(40))+'/src/app.py',provenance:'GitHub REST exact commit'}]}}};
 const html=renderToStaticMarkup(createElement(RuntimeIncident,{receipt,token:'',onBack:()=>{},onChange:async()=>{}}));
 expect(html).toContain('Read-only investigation');expect(html).toContain('AI hypothesis');expect(html).toContain('src/app.py');expect(html).toContain('no reliable user IDs');expect(html).not.toContain('Recovery verified');
});

it('rejects a prior incident receipt during navigation even when project and candidate IDs match', async()=>{
 const {receiptMatchesIncident}=await import('./presentation');
 const prior={incident:{id:'previous-incident',project_id:'same-project',selected:{id:'same-candidate'}}} as Receipt;
 expect(receiptMatchesIncident(prior,'new-incident')).toBe(false);
 expect(receiptMatchesIncident(prior,'previous-incident')).toBe(true);
 expect(receiptMatchesIncident(null,'new-incident')).toBe(false);
});
