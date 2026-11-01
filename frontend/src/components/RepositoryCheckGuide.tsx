import {useState} from 'react';
export default function RepositoryCheckGuide({profile, repaired = false, failures = [], completion = false, baselineRecorded = false, requirement = "", commands}: {commands?: {setup:string;test:string;basis:string}; profile: string; repaired?: boolean; failures?: {id:string; detail?:string}[]; completion?: boolean; baselineRecorded?: boolean; requirement?: string}) {
  const [copied,setCopied] = useState(false);
  const fallback = profile === 'python-pytest' ? 'python -m pytest -q' : profile === 'node-test' ? 'node --test' : profile === 'javascript-vitest' ? 'node node_modules/vitest/vitest.mjs run' : null;
  const command = commands ? commands.setup + "\n" + commands.test : fallback;
  if (!command || (!repaired && !failures.length && !(completion && baselineRecorded))) return null;
  return <section className="repository-check-guide" aria-label={repaired ? 'Check the repaired code yourself' : 'Reproduce the error yourself'}>
    <h3>{repaired ? (completion ? 'Your turn: verify the completed changes' : 'Your turn: verify the repair') : failures.length ? 'We reproduced these errors. See for yourself' : 'Baseline checked. See what currently works'}</h3>
    <p>{repaired ? 'Download and extract the repaired ZIP into a new folder. Open a terminal in the matching package inside repaired-repository, then run the same command.' : failures.length ? 'Analysis found the failing checks below. Open a terminal in your original project’s test package and run the command to reproduce them.' : 'The existing tests passed. Run the same baseline in your original project before comparing the requested completion.'}</p>
    {completion && requirement && <p><strong>Requested completion:</strong> {requirement}</p>}
    {!repaired && failures.slice(0,3).map(failure => <div key={failure.id}><strong>{failure.id}</strong>{failure.detail && <pre>{failure.detail}</pre>}</div>)}
    {commands && <p>Run from the inspected package directory. Detected setup: {commands.basis}. Setup commands below use a macOS/Linux shell.</p>}
    <pre><code>{command}</code></pre>
    <button type="button" className="button secondary" onClick={async()=>{try{await navigator.clipboard.writeText(command);setCopied(true);}catch{setCopied(false);}}}>{copied ? 'Command copied' : 'Copy test command'}</button>
    <p>{repaired ? completion ? 'Compare with your baseline, then check the requested features against the recorded requirement assessment. Passing existing tests proves regression coverage, not that every requested feature is finished.' : 'Compare with your original output. The repaired suite should pass; review any new failure before using the changes.' : completion ? 'Compare this output before choosing Complete project. Existing tests may pass even when functionality is unfinished; the requested work comes from your prompt and inspected source, not the language or test result alone.' : 'Compare your output with the recorded errors above, then choose Fix failing code. The command reproduces test failures; it does not establish their root cause by itself.'}</p>
    <small>Use the project’s documented environment and dependencies first. These commands run project code on your machine: only use them for source you trust. CtrlZ’s own verification uses an isolated runner.</small>
  </section>;
}
