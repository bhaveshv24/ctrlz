"""Deterministic, patch-only comparison of retry, history compensation and agent repair."""
import asyncio
import ast
from pathlib import Path
from .history import replace_sources, source_files
from .repository import editable, git


def diff_size(diff):
    return sum(1 for line in diff.splitlines() if line[:1] in {'+','-'} and not line.startswith(('+++','---')))


def choose(strategies):
    eligible=[s for s in strategies if s.get('eligible')]
    return min(eligible,key=lambda s:(s['diff_lines'],s['sandbox_runs'],s['id'])) if eligible else None


class CodeTournament:
    def __init__(self, store, incident_id, repo, worktree, sandbox, baseline, protected, check):
        self.store,self.incident_id,self.repo,self.worktree,self.sandbox=store,incident_id,repo,worktree,sandbox
        self.baseline,self.protected,self.check=baseline,protected,check
        self.head_sources=source_files(worktree,protected)
        self.strategies=[]

    def restore(self):
        git(['reset','--hard','HEAD'],self.worktree)
        replace_sources(self.worktree,self.head_sources,self.protected)
        if self.sandbox.profile!='python-pytest':(self.worktree/'node_modules').mkdir(exist_ok=True)

    async def run_tests(self, strategy):
        result=await asyncio.to_thread(self.sandbox.run)
        strategy['sandbox_runs']+=1
        self.store.record(self.incident_id,'strategy_tests',{'strategy':strategy['id'],'run':strategy['sandbox_runs'],**result})
        return result

    def qualify(self,result):
        checks,details=self.check(result)
        return all(checks.values()),checks,details

    async def retry(self):
        strategy={'id':'RETRY','eligible':False,'sandbox_runs':0,'diff_lines':0,'patch':'','reason':'Original failure persists'}
        self.strategies.append(strategy)
        consecutive=0
        for _ in range(2):
            result=await self.run_tests(strategy)
            passed,checks,details=self.qualify(result)
            consecutive=consecutive+1 if passed else 0
        strategy.update(eligible=consecutive==2,result=result,checks=checks,acceptance=details,reason='Two passing reruns after a failing baseline; flaky behavior, no source fix' if consecutive==2 else 'Baseline did not pass both reruns')
        return strategy

    def snapshot_sources(self,revision):
        names=git(['ls-tree','-r','--name-only',revision],self.repo).splitlines()
        return {name:git(['show',revision+':'+name],self.repo,raw=True) for name in names if editable(name) and name not in self.protected}

    async def compensate(self,metadata):
        strategy={'id':'COMPENSATE','eligible':False,'sandbox_runs':0,'diff_lines':0,'patch':'','reason':'No bounded source history available'}
        self.strategies.append(strategy)
        history=metadata.get('history',[])[-16:]
        if len(history)<2:return strategy
        try:
            async def probe(index):
                replace_sources(self.worktree,self.snapshot_sources(history[index]['snapshot_commit']),self.protected)
                result=await self.run_tests(strategy)
                passed,_,_=self.qualify(result)
                if result['exit_code'] not in {0,1,2} or not result['cases']:raise ValueError('Historical test environment did not produce valid acceptance evidence')
                return passed
            if not await probe(0):
                strategy['reason']='No passing lower bound in the 16-snapshot search window; history is inconclusive'
                return strategy
            low,high=0,len(history)-1
            while high-low>1 and strategy['sandbox_runs']<5:
                middle=(low+high)//2
                if await probe(middle):low=middle
                else:high=middle
            if high-low!=1:
                strategy['reason']='Bisect budget exhausted without adjacent good/bad snapshots'
                return strategy
            suspect=history[high]
            strategy['suspect_commit']=suspect
            strategy['boundary']={'good':history[low],'bad':suspect,'scope':'Observed good-to-bad boundary under current acceptance tests; monotonic history assumption'}
            self.restore()
            git(['revert','--no-commit',suspect['snapshot_commit']],self.worktree)
            names=git(['diff','--name-only','HEAD'],self.worktree).splitlines()
            if not names or len(names)>8 or any(not editable(n) or n in self.protected for n in names):
                raise ValueError('Revert would change tests/configuration or exceed eight product files')
            for name in names:
                target=self.worktree/name
                if target.exists():
                    if target.stat().st_size>256000:raise ValueError('Revert source exceeds bounds')
                    if target.suffix=='.py':ast.parse(target.read_text())
            patch=git(['diff','--no-ext-diff','--no-textconv','HEAD'],self.worktree)
            result=await self.run_tests(strategy)
            passed,checks,details=self.qualify(result)
            strategy.update(eligible=passed,result=result,checks=checks,acceptance=details,patch=patch,diff_lines=diff_size(patch),reason='Revert patch passed original immutable acceptance' if passed else 'Revert did not pass original immutable acceptance')
        except (ValueError,SyntaxError) as exc:
            strategy['reason']='Compensation unavailable: '+str(exc)[:300]
        finally:
            # All mutations are inside the disposable detached worktree.
            try:git(['revert','--abort'],self.worktree)
            except ValueError:pass
            self.restore()
        return strategy

    def agent(self,result,checks,details,patch,runs,reason=None):
        self.strategies.append({'id':'REPLAN','eligible':all(checks.values()) and bool(patch),'sandbox_runs':runs,'diff_lines':diff_size(patch),'patch':patch,'result':result,'checks':checks,'acceptance':details,'reason':reason or ('Agent patch passed original immutable acceptance' if all(checks.values()) else 'Agent did not produce a verified patch')})

    def record(self):
        winner=choose(self.strategies)
        public=[{k:v for k,v in s.items() if k not in {'patch','result'}} for s in self.strategies]
        self.store.record(self.incident_id,'tournament',{'results':public,'selected_strategy':winner['id'] if winner else None,'selection_rule':'Passing immutable original acceptance; smallest changed-line count, fewest strategy sandbox runs, stable ID'})
        self.store.update(self.incident_id,code_tournament=public,selected_code_strategy=winner['id'] if winner else None,suspect_commit=next((s.get('suspect_commit') for s in self.strategies if s['id']=='COMPENSATE'),None))
        return winner
