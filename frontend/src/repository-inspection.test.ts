import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {expect,it} from 'vitest';
import RepositoryInspection,{type InspectionReport} from './components/RepositoryInspection';

it('shows source findings alongside passing tests and unavailable dependency checks',()=>{
  const report:InspectionReport={version:1,commit:'a'.repeat(40),checked_at:1,summary:'review_required',
    source:{state:'findings',files_checked:3,findings:[{path:'app.py',line:4,rule:'dynamic-code',message:'Review untrusted input',confidence:'Potential risk'}],syntax_errors:[],limitations:['Targeted checks only']},
    dependencies:{state:'unavailable',packages_checked:0,findings:[],coverage_gaps:[],detail:'Service unavailable',privacy:'Package names and versions only'},
    tests:{state:'healthy',reason:'Existing tests passed'},health:{state:'attention_needed',profile:'Python',test_files:1,warnings:[],scope:'Not a security guarantee'}};
  const html=renderToStaticMarkup(createElement(RepositoryInspection,{report}));
  expect(html).toContain('app.py:4');expect(html).toContain('Existing tests passed');
  expect(html).toContain('Service unavailable');expect(html).toContain('Not a security guarantee');
  expect(html).toContain('Download inspection report');
});
