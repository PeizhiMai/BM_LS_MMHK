#!/usr/bin/python3.11
import os, subprocess, sys
from pathlib import Path
BATCH=Path(r"/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_25twist_fig4_cnn_20260820")
account=sys.argv[1] if len(sys.argv)>1 else "ccsd"
if account not in {"ccsd","cnms"}: raise SystemExit("account must be ccsd or cnms")
cap=int(os.environ.get("F4CNN25_"+account.upper()+"_USER_CAP","150"))
out=subprocess.run(["squeue","-h","-r","-u",os.environ["USER"],"-o","%a"],text=True,capture_output=True,check=True).stdout
current=sum(line.strip()==account for line in out.splitlines())
templates=sorted((BATCH/"templates").glob("job_f4cnn25_*.sh"))
slots=max(0,cap-current)
n=min(slots,len(templates))
print(f"DRY RUN ONLY: account={account} current_user_jobs={current} cap={cap} open_slots={slots} templates={len(templates)} would_submit={n}")
for path in templates[:n]: print("WOULD_RENDER_AND_SBATCH", path)
