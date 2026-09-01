#!/usr/bin/python3.11
import csv, math, re, statistics, sys
from collections import defaultdict
from pathlib import Path
BATCH=Path(r"/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/fig4_cnn/fullobs_25twist_fig4_cnn_20260820")
OUT=BATCH/"analysis"
COMPLETE_RE=re.compile(r"(?m)^status\s+COMPLETE\s*$")
rows=list(csv.DictReader((BATCH/"manifest.tsv").open(), delimiter="\t"))
required=["E0","<ni_upni_dn>","<mCDW2_pipi>","<C1_NN>","<nn_NN>","<Kinetic_per_site>"]
parsed=[]
for row in rows:
    path=Path(row["result"])
    text=path.read_text(errors="ignore") if path.is_file() else ""
    if not COMPLETE_RE.search(text):
        print(f"Not ready: {path}", file=sys.stderr); sys.exit(2)
    values={}
    for line in text.splitlines():
        parts=line.split(None,1)
        if len(parts)==2: values[parts[0]]=parts[1]
    missing=[key for key in required if key not in values]
    if missing: raise SystemExit(f"Missing {missing} in {path}")
    parsed.append({
        "index":int(row["index"]), "U":int(row["U"]), "V":float(row["V"]),
        "V_over_U":float(row["V_over_U"]), "twist_index":int(row["twist_index"]),
        "kx":int(row["kx"]), "ky":int(row["ky"]), "seed":int(row["seed"]),
        "E0":float(values["E0"]), "D_site":float(values["<ni_upni_dn>"]),
        "mCDW2_pipi":float(values["<mCDW2_pipi>"]), "C1_NN":float(values["<C1_NN>"]),
        "nn_NN":float(values["<nn_NN>"]), "kinetic_per_site":float(values["<Kinetic_per_site>"]),
        "status":"COMPLETE", "result":row["result"],
    })
OUT.mkdir(exist_ok=True)
with (OUT/"fig4_cnn_25twist_observables.csv").open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(parsed[0])); w.writeheader(); w.writerows(parsed)
groups=defaultdict(list)
for row in parsed: groups[(row["U"],row["V"])].append(row)
summary=[]
for (U,V), group in sorted(groups.items()):
    if len(group)!=25: raise SystemExit(f"Expected 25 twists at U={U} V={V}, found {len(group)}")
    C=[r["C1_NN"] for r in group]
    weights=[1 if r["kx"]==r["ky"] else 2 for r in group]
    Cmean=statistics.fmean(C)
    Csym=sum(w*x for w,x in zip(weights,C))/sum(weights)
    factor=(2*U-V)/(U-V)
    summary.append({
        "U":U,"V":V,"V_over_U":V/U,"expected_phase":"Mott","complete_twists":25,
        "C1_NN_panel_mean":Cmean,"C1_NN_panel_min":min(C),"C1_NN_panel_max":max(C),
        "C1_NN_panel_spread":max(C)-min(C),"C1_NN_panel_population_std":statistics.pstdev(C),
        "C1_NN_symmetry_weighted_diagnostic":Csym,
        "C1_NN_estimator_difference":Csym-Cmean,
        "s_NN_prediction":1+factor*(2*Cmean-0.5),
        "s_NN_prediction_symmetry_weighted_diagnostic":1+factor*(2*Csym-0.5),
        "D_site_panel_mean":statistics.fmean(r["D_site"] for r in group),
        "mCDW2_pipi_panel_mean":statistics.fmean(r["mCDW2_pipi"] for r in group),
        "nn_NN_panel_mean":statistics.fmean(r["nn_NN"] for r in group),
        "kinetic_per_site_panel_mean":statistics.fmean(r["kinetic_per_site"] for r in group),
        "panel_method":"unweighted arithmetic mean of deterministic maximin 25-twist panel",
        "twist_spread_is_standard_error":False,
    })
with (OUT/"fig4_cnn_25twist_summary.csv").open("w",newline="") as f:
    w=csv.DictWriter(f,fieldnames=list(summary[0])); w.writeheader(); w.writerows(summary)
for row in summary:
    print("U={U} V={V:g} C_NN={C1_NN_panel_mean:.12f} spread={C1_NN_panel_spread:.3e} s_pred={s_NN_prediction:.9f}".format(**row))
