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
