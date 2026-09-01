#!/usr/bin/python3.11
import csv, os, re, subprocess
from collections import Counter, defaultdict
from pathlib import Path
BATCH=Path(r"/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_25twist_fig4_cnn_20260820")
COMPLETE_RE=re.compile(r"(?m)^status\s+COMPLETE\s*$")
def state(path):
    path=Path(path)
    try:
        if not path.exists(): return "missing"
        if path.is_file() and COMPLETE_RE.search(path.read_text(errors="ignore")): return "complete"
        return "incomplete"
    except OSError: return "unreadable"
rows=list(csv.DictReader((BATCH/"manifest.tsv").open(), delimiter="\t"))
counts=Counter(state(r["result"]) for r in rows)
print("TOTAL", len(rows), " ".join(f"{k}={v}" for k,v in sorted(counts.items())))
groups=defaultdict(Counter)
for row in rows: groups[(row["U"],row["V"])][state(row["result"])]+=1
for (U,V), c in groups.items():
    print(f"U={U} V={V}: complete={c['complete']}/25 incomplete={c['incomplete']} missing={c['missing']}")
out=subprocess.run(["squeue","-h","-r","-u",os.environ["USER"],"-o","%i|%j|%a|%T|%M|%l|%R"], text=True, capture_output=True).stdout
active=[]
for line in out.splitlines():
    fields=[x.strip() for x in line.split("|")]
    if len(fields)==7 and fields[1] in {"F4CNN25","F4CNN25R"}: active.append(fields)
ac=Counter((r[1],r[2],r[3]) for r in active)
print("ACTIVE", " ".join(f"{j}:{a}:{s}={n}" for (j,a,s),n in sorted(ac.items())) or "none")
print("TEMPLATES", len(list((BATCH/"templates").glob("job_f4cnn25_*.sh"))))
print("SUBMITTED_SCRIPTS", len(list((BATCH/"submitted").glob("job_f4cnn25_*_ccsd.sh"))) + len(list((BATCH/"submitted").glob("job_f4cnn25_*_cnms.sh"))))
