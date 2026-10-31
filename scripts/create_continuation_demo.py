"""Create an explicitly imported, committed fixture from the real legacy worker defect."""
import argparse
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--campuspass", type=Path, default=Path("../campuspass"))
parser.add_argument("--destination", type=Path, default=Path("imports/worker-continuation"))
args = parser.parse_args()
source = args.campuspass / "backend/campuspass/ticket_reference.py"
target = args.destination.resolve()
if target.exists():
    raise SystemExit("Destination already exists; choose a new empty path")
(target / "src").mkdir(parents=True)
(target / "tests").mkdir()
(target / "src/ticket_reference.py").write_text(source.read_text())
(target / "tests/test_reference.py").write_text('''import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ticket_reference import legacy_reference

def test_uuid_order_reference():
    value = "a3bb189e-8bf9-3888-9912-ace4e6543002"
    assert legacy_reference(value) == "CP-" + value.replace("-", "").upper()

def test_deterministic_and_distinct():
    first = "a3bb189e-8bf9-3888-9912-ace4e6543002"
    second = "b3bb189e-8bf9-3888-9912-ace4e6543002"
    assert legacy_reference(first) == legacy_reference(first)
    assert legacy_reference(first) != legacy_reference(second)
''')
(target / "requirements.md").write_text("Fix src/ticket_reference.py so legacy_reference accepts a UUID order ID and returns CP- followed by uppercase UUID characters without hyphens. Preserve deterministic, distinct references. Do not change tests.")
for command in (["git", "init"], ["git", "add", "."], ["git", "-c", "user.name=CtrlZ Demo", "-c", "user.email=demo@localhost", "commit", "-m", "Import unfinished ticket reference feature"]):
    subprocess.run(command, cwd=target, check=True)
print(f"Import repository: {target}")
print((target / "requirements.md").read_text())
