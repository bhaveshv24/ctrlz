import {useState} from 'react';
export default function RepositoryCheckGuide({profile, repaired = false, failures = []}: {profile: string; repaired?: boolean; failures?: {id:string; detail?:string}[]}) {
  const [copied,setCopied] = useState(false);
  const command = profile === 'python-pytest' ? 'python -m pytest -q' : profile === 'node-test' ? 'node --test' : profile === 'javascript-vitest' ? 'node node_modules/vitest/vitest.mjs run' : null;
  if (!command || (!repaired && !failures.length)) return null;
  return <section className="repository-check-guide" aria-label={repaired ? 'Check the repaired code yourself' : 'Reproduce the error yourself'}>
    <h3>{repaired ? 'Your turn: verify the repair' : 'We reproduced these errors. See for yourself'}</h3>
    <p>{repaired ? 'Download and extract the repaired ZIP into a new folder. Open a terminal in the matching package inside repaired-repository, then run the same command.' : 'Analysis found the failing checks below. Open a terminal in your original project’s test package and run the command to reproduce them.'}</p>
    {!repaired && failures.slice(0,3).map(failure => <div key={failure.id}><strong>{failure.id}</strong>{failure.detail && <pre>{failure.detail}</pre>}</div>)}
    <pre><code>{command}</code></pre>
    <button type="button" className="button secondary" onClick={async()=>{try{await navigator.clipboard.writeText(command);setCopied(true);}catch{setCopied(false);}}}>{copied ? 'Command copied' : 'Copy test command'}</button>
    <p>{repaired ? 'Compare with your original output. The repaired suite should pass; review any new failure before using the changes.' : 'Compare your output with the recorded errors above, then choose Fix failing code. The command reproduces test failures; it does not establish their root cause by itself.'}</p>
    <small>Use the project’s documented environment and dependencies first. These commands run project code on your machine: only use them for source you trust. CtrlZ’s own verification uses an isolated runner.</small>
  </section>;
}
