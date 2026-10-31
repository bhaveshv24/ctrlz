"""Create local configuration once; never print secret values."""
import argparse
import secrets
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--campuspass', action='store_true', help='Configure the optional sibling demonstration')
args = parser.parse_args()
ctrlz = Path(__file__).resolve().parents[1]
ctrlz_env = ctrlz / '.env'
if not ctrlz_env.exists():
    content = (ctrlz / '.env.example').read_text().replace('replace-with-a-random-local-operator-token', secrets.token_urlsafe(32)).replace('replace-for-your-integrated-service', secrets.token_urlsafe(32))
    ctrlz_env.write_text(content)
    ctrlz_env.chmod(0o600)
if args.campuspass:
    campus = ctrlz.parent / 'campuspass'
    if not (campus/'backend').is_dir():
        raise SystemExit('Optional CampusPass checkout is absent; CtrlZ configuration is ready.')
    campus_env = campus/'.env'
    if not campus_env.exists():
        campus_env.write_text('RECOVERY_TOKEN='+secrets.token_urlsafe(32)+'\nDEMO_MODE=true\nDATABASE_URL=sqlite:///./campuspass.db\n')
        campus_env.chmod(0o600)
    settings = dict(line.split('=',1) for line in campus_env.read_text().splitlines() if '=' in line and not line.startswith('#'))
    content = ctrlz_env.read_text().replace('must-match-campuspass-recovery-token', settings.get('RECOVERY_TOKEN',''))
    ctrlz_env.write_text(content)
print('Local configuration ready. Set NVIDIA_API_KEY and NVIDIA_MODEL locally, then restart the API. No secret values were printed.')
