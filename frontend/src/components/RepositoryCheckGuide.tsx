import {useState} from 'react';
export default function RepositoryCheckGuide({profile, repaired = false}: {profile: string; repaired?: boolean}) {
  const [copied,setCopied] = useState(false);
  const command = profile === 'python-pytest' ? 'python -m pytest -q' : profile === 'node-test' ? 'node --test' : profile === 'javascript-vitest' ? 'node node_modules/vitest/vitest.mjs run' : null;
  if (!command) return null;
  return <section className="repository-check-guide" aria-label={repaired ? 'Check the repaired code yourself' : 'Reproduce the error yourself'}>
    <h3>{repaired ? 'Your turn: verify the repair' : 'First, see the failure yourself'}</h3>
    <p>{repaired ? 'Download and extract the repaired ZIP into a new folder. Open a terminal in the matching package inside repaired-repository, then run the same command.' : 'Open a terminal in your original project’s test package. Run this command to see the failures CtrlZ will investigate.'}</p>
    <pre><code>{command}</code></pre>
    <button type="button" className="button secondary" onClick={async()=>{try{await navigator.clipboard.writeText(command);setCopied(true);}catch{setCopied(false);}}}>{copied ? 'Command copied' : 'Copy test command'}</button>
    <p>{repaired ? 'Compare with your original output. The repaired suite should pass; review any new failure before using the changes.' : 'Keep the output for comparison. If tests already pass, that does not prove the project is complete or free of bugs.'}</p>
    <small>Use the project’s documented environment and dependencies first. These commands run project code on your machine: only use them for source you trust. CtrlZ’s own verification uses an isolated runner.</small>
  </section>;
}
