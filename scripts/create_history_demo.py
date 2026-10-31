"""Create a local-only, disclosed regression fixture for the repair tournament."""
import uuid
from pathlib import Path
from ctrlz.repository import git
root=Path(__file__).resolve().parents[1]
repo=root/'imports'/('history-demo-'+uuid.uuid4().hex[:8]);repo.mkdir(parents=True)
git(['init','-b','main'],repo)
(repo/'amounts.py').write_text('def total(a, b):\n    return a + b\n')
(repo/'test_amounts.py').write_text('from amounts import total\ndef test_total():\n    assert total(200, 350) == 550\ndef test_zero():\n    assert total(0, 0) == 0\n')
def commit(message):
    git(['add','.'],repo)
    git(['-c','user.name=CtrlZ Demo','-c','user.email=demo@localhost','commit','-m',message],repo)
commit('Working amount calculation and acceptance tests')
(repo/'amounts.py').write_text('def total(a, b):\n    return a - b\n');commit('Disclosed injected arithmetic regression')
(repo/'README.md').write_text('# Local controlled regression\nThis is a synthetic fixture, not an upstream defect.\n');commit('Document the fixture')
print('Local fixture created (no remote):')
print(repo)
print('Import this server folder in Repository repair. Requirements: Fix total amount calculation without changing the existing acceptance tests.')
