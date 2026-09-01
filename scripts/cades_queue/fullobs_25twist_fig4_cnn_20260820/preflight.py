#!/usr/bin/python3.11
import csv, hashlib, json, os, re, subprocess, sys
from collections import Counter, defaultdict
from pathlib import Path
BATCH=Path(r"/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_25twist_fig4_cnn_20260820")
BASE=Path(r"/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs")
PINNED_SOLVER=Path(r"/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_25twist_fig4_cnn_20260820/pinned_solver/Hubbard_sym_testobs_UV.x")
PINNED_SOURCE=Path(r"/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_25twist_fig4_cnn_20260820/pinned_solver/Hubbard_sym_testobs_UV.cc")
PINNED_QBASIS=Path(r"/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_25twist_fig4_cnn_20260820/pinned_solver/libqbasis.so")
EXPECTED_SOLVER="b85cefa08615ff2bffd46690990c68b4d1297de7a8b11046ebd6c1c29bdd8c0b"
EXPECTED_SOURCE="f68ecd93e2dee07012d7fda6521fe617775f637fede1da7f3f0cb27a92e6ce73"
EXPECTED_QBASIS="be10e2a72679b2214735c1e71f55dfc331e395a41a0866ecde35b090ca21ba85"
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()
rows=list(csv.DictReader((BATCH/"manifest.tsv").open(),delimiter="\t"))
assert len(rows)==300, len(rows)
assert len({r["index"] for r in rows})==300
assert len({r["seed"] for r in rows})==300
assert len({r["result"] for r in rows})==300
groups=Counter((r["U"],r["V"]) for r in rows)
assert len(groups)==12 and set(groups.values())=={25}, groups
assert sha(PINNED_SOLVER)==EXPECTED_SOLVER
assert sha(PINNED_SOURCE)==EXPECTED_SOURCE
assert sha(PINNED_QBASIS)==EXPECTED_QBASIS
assert (BATCH/"PINNED_SHA256SUMS").read_text()==f"{EXPECTED_SOLVER}  pinned_solver/Hubbard_sym_testobs_UV.x\n{EXPECTED_SOURCE}  pinned_solver/Hubbard_sym_testobs_UV.cc\n{EXPECTED_QBASIS}  pinned_solver/libqbasis.so\n"
templates=list((BATCH/"templates").glob("job_f4cnn25_*.sh"))
for path in templates:
    text=path.read_text()
    assert "#SBATCH -A __ACCOUNT__" in text
    assert "#SBATCH -J F4CNN25" in text
    assert "#SBATCH --mem=100G" in text and "#SBATCH -t 08:00:00" in text
    assert EXPECTED_SOLVER in text
    p=subprocess.run(["bash","-n",str(path)],capture_output=True,text=True)
    if p.returncode: raise SystemExit(f"bash -n failed for {path}: {p.stderr}")
for helper in ["submit_fill.sh","submit_next.sh"]:
    p=subprocess.run(["bash","-n",str(BATCH/helper)],capture_output=True,text=True)
    if p.returncode: raise SystemExit(f"bash -n failed for {helper}: {p.stderr}")
complete=0; incomplete=[]
rx=re.compile(r"(?m)^status\s+COMPLETE\s*$")
for row in rows:
    p=Path(row["result"])
    if not p.exists(): continue
    if p.is_file() and rx.search(p.read_text(errors="ignore")): complete+=1
    else: incomplete.append(str(p))
if incomplete: raise SystemExit("Conflicting incomplete target files:\n"+"\n".join(incomplete))
out=subprocess.run(["squeue","-h","-r","-u",os.environ["USER"],"-o","%j|%a|%T"],capture_output=True,text=True).stdout
active=[line for line in out.splitlines() if line.split("|",1)[0].strip() in {"F4CNN25","F4CNN25R"}]
if active: raise SystemExit("This batch job name is already active:\n"+"\n".join(active))
acct=Counter()
for line in out.splitlines():
    f=[x.strip() for x in line.split("|")]
    if len(f)==3: acct[(f[1],f[2])]+=1
print("PREFLIGHT PASS")
print(f"manifest={len(rows)} templates={len(templates)} complete_reused={complete}")
print("active user jobs:", " ".join(f"{a}:{s}={n}" for (a,s),n in sorted(acct.items())) or "none")
print("submission remains DISARMED unless F4CNN25_CONFIRM_SUBMIT=YES")
