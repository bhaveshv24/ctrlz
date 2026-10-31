import argparse
import os
import httpx

parser = argparse.ArgumentParser()
parser.add_argument("--ctrlz", default="http://127.0.0.1:8000")
parser.add_argument("--campuspass", default="http://localhost:8001", help="Use http://campuspass-api:8001 when CtrlZ runs in Compose")
args = parser.parse_args()
response = httpx.post(args.ctrlz + "/projects", headers={"X-Operator-Token": os.environ.get("CTRLZ_OPERATOR_TOKEN", "")}, json={"id": "campuspass", "name": "CampusPass", "base_url": args.campuspass, "adapter": "campuspass-v1", "token_env": "CAMPUSPASS_RECOVERY_TOKEN", "contract": {"allowed": ["restore_checkout", "resume_worker", "retry_order"], "approval_required": ["resume_worker"]}})
response.raise_for_status()
print(response.json())
