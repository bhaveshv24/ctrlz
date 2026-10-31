import { createElement, type ReactNode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { expect, it, vi } from 'vitest';
vi.mock('./components/ui',async original=>({...await original<typeof import('./components/ui')>(),Dialog:({children}:{children:ReactNode})=>createElement('section',null,children)}));
import WorkflowAudit,{ WorkflowProposal } from './components/WorkflowAudit';
import RuntimeIncident from './components/RuntimeIncident';
import {runtimeProject,emptyDeployment} from './runtime-projects';
import type { Receipt } from './api';

const project=runtimeProject('documents','Documents','https://github.com/example/documents',[{...emptyDeployment(1),id:'local',service_id:'documents',platform:'local',environment:'staging',sources:[{id:'app',connector:'generic-events'},{id:'state',connector:'generic-events'}]}]);
const proposal:Parameters<typeof WorkflowProposal>[0]['proposal']={id:'proposal',audit_id:'audit',deployment_id:'local',source_id:'app',environment:'staging',revision:'sha256:'+'a'.repeat(64),status:'proposed',provenance:'Uploaded source; Git identity unverified',proposal_hash:'b'.repeat(64),
  rule:{id:'processing',name:'Document processing',description:'A submitted document should complete.',evidence:[{path:'jobs.py',line:20}],start_condition:'Durable job created',completion_condition:'Same job completed',deadline_seconds:30,technique:'instrumentation',classification:'suspected_gap',allowed_fields:['instance_id','resource_id'],hooks:[],existing_signals:['jobs table'],missing_signals:['completion lifecycle'],uncertainties:['Deadline needs review'],privacy:'No bodies or email',overhead:'Bounded queue',permissions:['read-only selected jobs'],independent_verification:'Independent state snapshot',coverage_limits:['Best-effort logs']}};
const render=(p=proposal)=>renderToStaticMarkup(createElement(WorkflowProposal,{proposal:p,project,token:'',busy:false,act:async()=>{}}));

it('offers an optional structured source audit without custom API configuration',()=>{
  const html=renderToStaticMarkup(createElement(WorkflowAudit,{project,token:'',onClose:()=>{}}));
  expect(html).toContain('Analyze workflows for silent failures');expect(html).toContain('Source snapshot ZIP');expect(html).toContain('Nothing is committed or deployed');
});
it('shows evidence, reviewed deadline, privacy scope and source uncertainty before approval',()=>{
  const html=render();expect(html).toContain('jobs.py:20');expect(html).toContain('30s');expect(html).toContain('No bodies or email');expect(html).toContain('Git identity unverified');expect(html).toContain('Approve monitoring rule');expect(html).not.toContain('Generate and verify instrumentation');
});
it('offers generation only after approval and separates dependency permission',()=>{
  const html=render({...proposal,status:'approved',approval:{hash:'c'.repeat(64),actor:'operator',timestamp:1}});
  expect(html).toContain('Generate and verify instrumentation');expect(html).toContain('Separately authorize declared dependency setup');
});
it('distinguishes passing verification and awaiting deployment from active monitoring',()=>{
  const html=render({...proposal,status:'awaiting_deployment',patch:{diff:'+@observe',changed_files:['jobs.py'],source_digest:'d'.repeat(64),instrumentation_digest:'e'.repeat(64)},verification:{passed:true,checks:{original_tests_immutable:true},baseline:{cases:[1,2]},candidate:{cases:[1,2]},instrumentation:{cases:[1,2,3,4,5,6]},limitations:['Tests are not mathematical proof']}});
  expect(html).toContain('Download patch');expect(html).toContain('Actually deployed revision');expect(html).toContain('wait for telemetry');expect(html).toContain('Tests are not mathematical proof');expect(html).not.toContain('monitoring_active');
});
it('workflow incident scopes the affected resource and preserves unknown identity',()=>{
  const receipt:Receipt={schema_version:1,success:false,reasoning_provider:'explicit SSR test fixture',integrity:{algorithm:'sha256',snapshot_digest:'test',scope:'test'},events:[],incident:{id:'one-job',project_id:'documents',kind:'runtime',resource:'fingerprint',status:'awaiting_review',created:1,updated:1,workflow_evidence:{proposal_id:'proposal',approved_rule:{name:'Document processing',completion_condition:'Same job completed'},instance_id:'job-1',resource_id:'document-1',user_id:null,identity:'unknown',observation:'authoritative overdue incomplete',revision:'sha256:source',source_revision:'sha256:baseline',source_provenance:'local test snapshot',last_evidence:{}}}};
  const html=renderToStaticMarkup(createElement(RuntimeIncident,{receipt,token:'',onBack:()=>{},onChange:async()=>{}}));
  expect(html).toContain('job-1');expect(html).toContain('document-1');expect(html).toContain('User association: Unknown');expect(html).toContain('authoritative overdue incomplete');expect(html).toContain('Recommendations have not executed');
});
