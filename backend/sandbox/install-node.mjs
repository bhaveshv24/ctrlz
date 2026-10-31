import fs from 'node:fs';
import {spawnSync} from 'node:child_process';
for (const name of ['package.json','package-lock.json']) fs.copyFileSync('/manifests/'+name,'/deps/'+name);
const result=spawnSync('npm',['ci','--ignore-scripts','--no-audit','--no-fund','--cache=/tmp/npm-cache','--registry=https://registry.npmjs.org'],{cwd:'/deps',stdio:'inherit'});
process.exit(result.status??1);
