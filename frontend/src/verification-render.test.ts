import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {expect,it} from 'vitest';
import {CheckList} from './components/ui';
it('renders queued retries and older incomplete verification records without crashing',()=>{
 for(const checks of [undefined,null,{}]) {
  expect(renderToStaticMarkup(createElement(CheckList,{checks}))).toContain('Verification checks will appear');
 }
 expect(renderToStaticMarkup(createElement(CheckList,{checks:{candidate_tests:true}}))).toContain('Passed');
});
