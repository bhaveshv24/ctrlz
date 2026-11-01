import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import {expect,it} from 'vitest';
import RecoveryProgress from './components/RecoveryProgress';
it('shows event-based progress and animates only during active work',()=>{
 const stages=[{name:'Detect',recorded:true,failed:false},{name:'Verify',recorded:false,failed:false}];
 const active=renderToStaticMarkup(createElement(RecoveryProgress,{stages,active:true}));
 expect(active).toContain('aria-valuenow="1"');expect(active).toContain('aria-valuemax="2"');expect(active).toContain('recovery-progress-motion');
 const stopped=renderToStaticMarkup(createElement(RecoveryProgress,{stages,active:false}));
 expect(stopped).not.toContain('recovery-progress-motion');expect(stopped).toContain('Pending');
});
