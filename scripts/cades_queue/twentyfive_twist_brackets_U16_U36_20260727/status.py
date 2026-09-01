#!/usr/bin/env python3
import csv, os, re, subprocess
from collections import Counter, defaultdict
from pathlib import Path
BATCH=Path(r"/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/transition_search/twentyfive_twist_brackets_U16_U36_20260727")
COMPLETE_RE=re.compile(r"(?m)^status\s+COMPLETE\s*$")
def ok(p):
    p=Path(p)
    try: return p.is_file() and bool(COMPLETE_RE.search(p.read_text(errors="ignore")))
    except OSError: return False
rows=list(csv.DictReader((BATCH/"manifest.tsv").open(),delimiter="\t"))
complete=sum(ok(r["result"]) for r in rows)
by=defaultdict(lambda:[0,0])
for r in rows:
    key=(r["U"],r["V"]); by[key][0]+=int(ok(r["result"])); by[key][1]+=1
print(f"COMPLETE {complete}/{len(rows)} ({100*complete/len(rows):.2f}%)")
for (u,v),(n,t) in by.items(): print(f"U={u} V={v}: {n}/{t}")
out=subprocess.run(["squeue","-u",os.environ["USER"],"-h","-o","%j|%a|%T"],universal_newlines=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout
c=Counter()
for line in out.splitlines():
    j,a,s=[x.strip() for x in line.split("|")]
    if j in {"OBS25T","OBS25TR"}: c[(j,a,s)]+=1
print("ACTIVE", " ".join(f"{j}:{a}:{s}={n}" for (j,a,s),n in sorted(c.items())) or "none")
print("TEMPLATES",len(list((BATCH/"templates").glob("job_obs25t_*.sh"))))
