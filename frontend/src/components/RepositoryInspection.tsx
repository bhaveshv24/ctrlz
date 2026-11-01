import { saveFile } from '../api';
export type InspectionReport = {
  version:number;commit:string;checked_at:number;summary:string;
  source:{state:string;files_checked:number;findings:{path:string;line:number;rule:string;message:string;confidence:string}[];syntax_errors:{path:string;line:number;message:string}[];limitations:string[]};
  dependencies:{state:string;packages_checked:number;findings:{package:string;version:string;advisory:string;url:string}[];coverage_gaps:string[];detail?:string;privacy:string};
  tests:{state:string;reason:string};health:{state:string;profile:string;test_files:number;warnings:string[];scope:string};
};
export default function RepositoryInspection({report:r}:{report:InspectionReport}) {
  const count=r.source.findings.length+r.source.syntax_errors.length+r.dependencies.findings.length;
  return <section className="inspection-report" aria-label="Repository inspection report">
    <h3>Inspection report</h3>
    <p>{count ? `${count} finding${count===1?'':'s'} to review.` : 'No findings in the checks that completed.'} {r.summary==='review_required'?'Some checks need attention or have incomplete coverage.':'Completed checks passed within their stated limits.'}</p>
    <dl className="inspection-checks">
      <div><dt>Source review</dt><dd>{r.source.files_checked} files checked</dd></div>
      <div><dt>Dependency advisories</dt><dd>{r.dependencies.packages_checked} resolved packages checked / {r.dependencies.state.replaceAll('_',' ')}</dd></div>
      <div><dt>Isolated tests</dt><dd>{r.tests.state.replaceAll('_',' ')}: {r.tests.reason}</dd></div>
      <div><dt>Repository readiness</dt><dd>{r.health.profile} / {r.health.test_files} acceptance files</dd></div>
    </dl>
    {r.source.syntax_errors.map((f,n)=><p key={'syntax'+n}><code>{f.path}:{f.line}</code>: {f.message}</p>)}
    {r.source.findings.map((f,n)=><details key={n}><summary>{f.rule.replaceAll('-',' ')} / {f.path}:{f.line}</summary><p>{f.message}</p><small>{f.confidence}</small></details>)}
    {r.dependencies.findings.map((f,n)=><p key={'dep'+n}><code>{f.package}@{f.version}</code>: <a href={f.url} target="_blank" rel="noreferrer">{f.advisory}</a></p>)}
    {r.dependencies.detail&&<p>{r.dependencies.detail}</p>}
    {[...r.dependencies.coverage_gaps,...r.health.warnings].map((gap,n)=><p key={'gap'+n}>{gap}</p>)}
    <details><summary>Check scope and limitations</summary><p>{r.health.scope}</p><p>{r.dependencies.privacy}</p>{r.source.limitations.map((v,n)=><p key={n}>{v}</p>)}<p>Snapshot commit: <code>{r.commit}</code></p></details>
    <button type="button" className="button secondary" onClick={()=>saveFile('ctrlz-inspection.json',JSON.stringify(r,null,2))}>Download inspection report</button>
  </section>;
}
