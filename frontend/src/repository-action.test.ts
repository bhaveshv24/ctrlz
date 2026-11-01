import {expect,it} from 'vitest';
import {repositoryAction} from './repository-action';
it('allows first inspection and retry without Docker or a supported test profile',()=>{
  for (const mode of ['repair','complete'] as const) {
    expect(repositoryAction(mode,null,false,false)).toMatchObject({label:'Inspect repository',disabled:false,startsChanges:false});
    expect(repositoryAction(mode,null,false,false,true)).toMatchObject({label:'Retry inspection',disabled:false});
    expect(repositoryAction(mode,'blocked',false,true)).toMatchObject({label:'Inspect again',disabled:false});
  }
});
it('only starts source changes with the right baseline and a runner',()=>{
  expect(repositoryAction('repair','healthy',true,true)).toMatchObject({startsChanges:false,label:'Inspect again'});
  expect(repositoryAction('repair','failing',true,true)).toMatchObject({startsChanges:true,label:'Fix failing code',disabled:false});
  expect(repositoryAction('complete','healthy',true,true)).toMatchObject({startsChanges:true,label:'Complete project',disabled:false});
  expect(repositoryAction('repair','failing',false,true).disabled).toBe(true);
});
