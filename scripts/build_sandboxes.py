"""Build the two isolated test runtimes; no repository code runs on the host."""
import subprocess
from pathlib import Path
root = Path(__file__).resolve().parents[1]
for dockerfile, image in [('Dockerfile.sandbox','ctrlz-sandbox:local'),('Dockerfile.node-sandbox','ctrlz-node-sandbox:local')]:
    subprocess.run(['docker','build','-f',str(root/'backend'/dockerfile),'-t',image,str(root/'backend')],check=True)
