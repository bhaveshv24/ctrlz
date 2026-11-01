import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {expect,it} from 'vitest';
import Guide from './components/RepositoryCheckGuide';
it('never invents an error from a detected language alone',()=>{
 expect(renderToStaticMarkup(createElement(Guide,{profile:'python-pytest'}))).toBe('');
});
it('shows reproduction commands only with real failure evidence',()=>{
 const html=renderToStaticMarkup(createElement(Guide,{profile:'python-pytest',failures:[{id:'test_total',detail:'AssertionError: expected 12, got 10'}]}));
 expect(html).toContain('expected 12, got 10');expect(html).toContain('python -m pytest -q');
 expect(html).toContain('We reproduced these errors');
});
it('waits for completion baseline evidence and does not call passing tests a completed feature',()=>{
 expect(renderToStaticMarkup(createElement(Guide,{profile:'python-pytest',completion:true}))).toBe('');
 const html=renderToStaticMarkup(createElement(Guide,{profile:'python-pytest',completion:true,baselineRecorded:true,requirement:'Finish filters'}));
 expect(html).toContain('Baseline checked');expect(html).toContain('Finish filters');expect(html).not.toContain('We reproduced these errors');
 const after=renderToStaticMarkup(createElement(Guide,{profile:'python-pytest',completion:true,repaired:true}));
 expect(after).toContain('not that every requested feature is finished');
});
