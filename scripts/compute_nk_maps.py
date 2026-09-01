#!/usr/bin/env python3
"""Compute path-resolved n(k) from Lanczos removal spectral weights.

The current Gcalpath raw files only cover the 121-point Gamma-X-M-Gamma path for
these manuscript parameter sets, not the full Brillouin-zone mesh.  For each k,
we use the hole Green-function initial vector norm: per spin n_k = ||c_k|GS>||^2,
so the plotted spin-summed occupation is n(k)=2*nrm2_h^2.
"""
from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/Gcalpath/Lanczos_raw_data"
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
NUM = r"-?(?:\d+(?:\.\d*)?|\.\d+)"


def param_label(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else f"{v:g}"


def k_path(nn: int = 40):
    return [(i,0) for i in range(nn)] + [(nn,i) for i in range(nn)] + [(i,i) for i in range(nn,-1,-1)]


def x_centers(nn: int = 40):
    x=np.zeros(3*nn+1)
    for i in range(x.size):
        x[i]=i+1 if i<2*nn else x[2*nn-1]+1+(i-2*nn)*math.sqrt(2)
    return x


def read_nrm2(path: Path) -> float:
    for line in path.read_text(errors="replace").splitlines():
        if line.startswith("nrm2"):
            return float(line.split()[1])
    raise ValueError(f"nrm2 missing in {path}")


def nk_for_group(U: float, V: float, tp: float) -> tuple[np.ndarray, list[str]]:
    vals=[]; status=[]
    for kx,ky in k_path():
        path = DATA / f"L4x4Nup8Ndn8U{param_label(U)}V{param_label(V)}tp{param_label(tp)}f{kx}x{ky}Q0x0_Gh.dat"
        if not path.exists():
            vals.append(np.nan); status.append("missing_raw_data")
        else:
            nrm2=read_nrm2(path)
            vals.append(2.0*nrm2*nrm2); status.append("ok")
    return np.array(vals, dtype=float), status


def group_list():
    groups=[]
    for U,Vlist in [(8,[0,1,2,3,4]), (20,[0,2,4,6,8]), (40,[0,4,8,12,16])]:
        for V in Vlist:
            groups.append((float(U), float(V), 0.0))
    # t'=-0.25 V=0 diagnostic comparison where available.
    for U in [8,12,20,40]:
        groups.append((float(U),0.0,-0.25))
    return groups


def compute_metrics():
    x=x_centers(); rows=[]; cuts=[]
    for U,V,tp in group_list():
        nk,status=nk_for_group(U,V,tp)
        finite=np.isfinite(nk)
        if not finite.any():
            continue
        # nodal point on this path is (20,20), antinode X is (40,0).
        coords=k_path()
        nodal_idx=coords.index((20,20)) if (20,20) in coords else None
        x_idx=coords.index((40,0))
        nodal=nk[nodal_idx] if nodal_idx is not None else np.nan
        antinode=nk[x_idx]
        rows.append({
            "U":U,"V":V,"tp":tp,"eta_source":"hole_weight_from_Gh_raw_data",
            "finite_points":int(finite.sum()),"missing_points":int((~finite).sum()),
            "mean_nk_path":float(np.nanmean(nk)),"variance_nk_path":float(np.nanvar(nk)),
            "min_nk_path":float(np.nanmin(nk)),"max_nk_path":float(np.nanmax(nk)),
            "nodal_nk":float(nodal),"antinodal_X_nk":float(antinode),
            "nodal_minus_antinodal":float(nodal-antinode),
        })
        for i,((kx,ky),xx,val,st) in enumerate(zip(coords,x,nk,status)):
            cuts.append({"U":U,"V":V,"tp":tp,"k_index":i,"kx":kx,"ky":ky,"x_path":xx,"nk":val,"status":st})
    return rows,cuts


def write_csv(rows, cuts):
    RESULTS.mkdir(exist_ok=True)
    metrics_path=RESULTS/"nk_metrics.csv"
    cuts_path=RESULTS/"nk_path_cuts.csv"
    with metrics_path.open("w", newline="", encoding="utf-8") as h:
        w=csv.DictWriter(h, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    with cuts_path.open("w", newline="", encoding="utf-8") as h:
        w=csv.DictWriter(h, fieldnames=list(cuts[0].keys())); w.writeheader(); w.writerows(cuts)
    note=RESULTS/"nk_source_note.md"
    note.write_text("# n(k) source note\n\nThe current manuscript Gcalpath raw data contain high-symmetry-path Green-function files, not full Brillouin-zone n(k) maps. The spin-summed occupation used here is n(k)=2*nrm2_h^2 from the Gh Lanczos initial vector norm. Full 4x4 Brillouin-zone maps require additional observable measurements.\n", encoding="utf-8")
    return metrics_path,cuts_path,note


def plot(rows, cuts):
    FIGURES.mkdir(exist_ok=True)
    x=x_centers(); coords=k_path()
    by_key={(r["U"],r["V"],r["tp"]):r for r in rows}
    cuts_by_key={}
    for row in cuts:
        key=(row["U"],row["V"],row["tp"]); cuts_by_key.setdefault(key,[]).append(row)
    pdf=FIGURES/"nk_fluctuation_summary.pdf"; png=FIGURES/"nk_fluctuation_summary.png"
    with plt.rc_context({"font.family":"Arial","font.size":13,"axes.labelsize":15,"legend.fontsize":10}):
        fig,axes=plt.subplots(2,2,figsize=(9.6,6.8))
        colors=plt.cm.viridis(np.linspace(.15,.9,5))
        for ax,U,Vlist in [(axes[0,0],8,[0,1,2,3,4]),(axes[0,1],20,[0,2,4,6,8]),(axes[1,0],40,[0,4,8,12,16])]:
            for c,V in zip(colors,Vlist):
                key=(float(U),float(V),0.0)
                if key not in cuts_by_key: continue
                vals=np.array([float(r["nk"]) if str(r["nk"])!='nan' else np.nan for r in cuts_by_key[key]])
                ax.plot(x,vals,lw=2,color=c,label=rf"$V={V:g}$")
            ax.set_title(rf"$U={U},\ t'=0$")
            ax.set_xlim(x[0],x[-1]); ax.set_ylim(0,2)
            ax.set_xticks([x[0],x[40],x[80],x[120]]); ax.set_xticklabels([r"$\Gamma$","X","M",r"$\Gamma$"])
            ax.set_ylabel(r"$n(\mathbf{k})$"); ax.grid(alpha=.25); ax.legend(frameon=False,ncol=3)
        ax=axes[1,1]
        for U,marker in [(8,"o"),(20,"s"),(40,"^")]:
            vals=[r for r in rows if int(r["U"])==U and r["tp"]==0.0]
            vals=sorted(vals,key=lambda r:r["V"])
            ax.plot([r["V"]/r["U"] for r in vals],[r["variance_nk_path"] for r in vals],marker+"-",lw=2,label=rf"$U={U}$")
        ax.axvline(.25,ls="--",color="black",lw=1)
        ax.set_xlabel(r"$V/U$"); ax.set_ylabel(r"path variance of $n(\mathbf{k})$"); ax.grid(alpha=.25); ax.legend(frameon=False)
        fig.tight_layout(); fig.savefig(pdf,bbox_inches="tight"); fig.savefig(png,dpi=220,bbox_inches="tight"); plt.close(fig)
    return pdf,png


def main():
    rows,cuts=compute_metrics(); metrics,cuts_path,note=write_csv(rows,cuts); pdf,png=plot(rows,cuts)
    print(json.dumps({"metrics":str(metrics),"cuts":str(cuts_path),"note":str(note),"pdf":str(pdf),"png":str(png)},indent=2))

if __name__ == "__main__": main()
