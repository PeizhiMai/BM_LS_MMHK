#!/usr/bin/env python3
import csv, re, sys
from collections import defaultdict
from pathlib import Path
BATCH=Path(r"/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/transition_search/five_twist_U16_U36_20260726")
OUT=BATCH/"analysis"
OUT.mkdir(exist_ok=True)
COMPLETE_RE=re.compile(r"(?m)^status\s+COMPLETE\s*$")
rows=list(csv.DictReader((BATCH/"manifest.tsv").open(),delimiter="\t"))
parsed=[]; missing=[]
for r in rows:
    p=Path(r["result"])
    text=p.read_text(errors="ignore") if p.is_file() else ""
    if not COMPLETE_RE.search(text): missing.append(r); continue
    vals={}
    for line in text.splitlines():
        parts=line.split()
        if len(parts)>=2: vals[parts[0]]=parts[1]
    def val(k): return float(vals[k])
    D=val("<ni_upni_dn>")
    parsed.append({
      "U":int(r["U"]),"V":float(r["V"]),"kx":int(r["kx"]),"ky":int(r["ky"]),
      "E0":val("E0"),"double_occupancy":D,"mCDW2_pipi":val("<mCDW2_pipi>"),
      "C1_NN":val("<C1_NN>"),"nn_NN":val("<nn_NN>"),
      "kinetic_per_site":val("<Kinetic_per_site>"),"phase":"charge" if D>0.25 else "Mott",
      "status":"COMPLETE","result":r["result"]
    })
if missing:
    print(f"Not ready: {len(missing)}/{len(rows)} outputs are not COMPLETE",file=sys.stderr)
    sys.exit(2)
fields=list(parsed[0])
with (OUT/"five_twist_transition_observables_U16_U36.csv").open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(parsed)
groups=defaultdict(list)
for r in parsed: groups[(r["U"],r["V"])].append(r)
summary=[]
for U in sorted({r["U"] for r in parsed}):
    states=[]
    for (u,V),rr in sorted(groups.items()):
        if u!=U: continue
        phases={x["phase"] for x in rr}
        state=next(iter(phases)) if len(phases)==1 and len(rr)==5 else "mixed"
        states.append((V,state,rr))
    mott=[V for V,s,_ in states if s=="Mott"]
    charge=[V for V,s,_ in states if s=="charge"]
    VM=max(mott) if mott else None; VC=min(charge) if charge else None
    valid=VM is not None and VC is not None and VM<VC
    summary.append({
      "U":U,"V_Mott":VM,"V_charge":VC,
      "V_c_midpoint":(VM+VC)/2 if valid else None,
      "V_c_halfwidth":(VC-VM)/2 if valid else None,
      "V_c_over_U":(VM+VC)/(2*U) if valid else None,
      "V_c_over_U_halfwidth":(VC-VM)/(2*U) if valid else None,
      "bracket_width":VC-VM if valid else None,
      "all_five_twists_agree":all(s!="mixed" for _,s,_ in states),
      "status":"bracketed" if valid else "needs_extension_or_review"
    })
with (OUT/"five_twist_transition_brackets_U16_U36.csv").open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(summary[0])); w.writeheader(); w.writerows(summary)
for r in summary: print(r)
