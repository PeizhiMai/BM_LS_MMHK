#!/usr/bin/env python3
"""Recompute eta=0.05 finite-V zero-dispersion metrics and join diagnostics.

The script discovers available root CSVs under the eta=0.05 finite-V directory,
compares each curve to the same-U V=0 reference, and writes updated metric tables.
It also records which priority refined points are still missing locally.
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
FINITE_DIR = ROOT / "data/Gcalpath/luttinger_surface_eta0p05_other_parameter_sets"
V0_DIR = ROOT / "data/Gcalpath/luttinger_surface_eta0p05"
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
PRIORITY_POINTS = [(20, 4.5), (20, 5.0), (20, 5.5), (40, 9.0), (40, 10.0), (40, 11.0), (80, 16.0), (80, 20.0), (80, 24.0)]


def vlabel(v: float) -> str:
    return f"{v:g}"


def load_roots(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["U"] = df["U"].astype(float)
    df["V"] = df["V"].astype(float)
    df["tp"] = df["tp"].astype(float)
    df["eta"] = df["eta"].astype(float)
    return df.sort_values("k_index")


def v0_reference(U: float) -> pd.DataFrame | None:
    path = V0_DIR / f"luttinger_tp0_U{vlabel(U)}_eta0p05_curves.csv"
    if not path.exists() and float(U).is_integer():
        path = V0_DIR / f"luttinger_tp0_U{int(U)}_eta0p05_curves.csv"
    if not path.exists():
        return None
    return load_roots(path)


def metrics_for_curve(df: pd.DataFrame, ref: pd.DataFrame | None) -> dict[str, object]:
    U = float(df["U"].iloc[0]); V = float(df["V"].iloc[0]); tp = float(df["tp"].iloc[0])
    accepted = df["root_status"].eq("clean") & np.isfinite(df["omega_root"])
    y = df.loc[accepted, "omega_root"].to_numpy(float)
    kidx = df.loc[accepted, "k_index"].to_numpy(int)
    out: dict[str, object] = {
        "U": U,
        "V": V,
        "V_over_U": V / U if U else math.nan,
        "tp": tp,
        "eta": float(df["eta"].iloc[0]),
        "accepted_root_count": int(accepted.sum()),
        "missing_raw_rows": int(df["root_status"].eq("missing_raw_data").sum()),
        "max_candidate_roots": int(pd.to_numeric(df.get("candidate_roots", pd.Series([0])), errors="coerce").max()),
        "mean_candidate_roots": float(pd.to_numeric(df.get("candidate_roots", pd.Series([np.nan])), errors="coerce").mean()),
        "root_multiplicity_change_count": int((pd.to_numeric(df.get("candidate_roots", pd.Series([1]*len(df))), errors="coerce").fillna(1).diff().fillna(0) != 0).sum()),
        "status_counts": str(df["root_status"].value_counts().to_dict()),
        "missing_k_indices": ";".join(str(int(x)) for x in df.loc[df["root_status"].eq("missing_raw_data"), "k_index"]),
        "source_csv": str(Path(df.attrs.get("source_csv", "")).as_posix()),
    }
    if y.size:
        out.update({
            "bandwidth": float(np.nanmax(y) - np.nanmin(y)),
            "root_min": float(np.nanmin(y)),
            "root_max": float(np.nanmax(y)),
            "mean_abs_root": float(np.nanmean(np.abs(y))),
            "max_neighbor_jump": float(np.nanmax(np.abs(np.diff(y)))) if y.size > 1 else 0.0,
        })
    else:
        out.update({"bandwidth": math.nan, "root_min": math.nan, "root_max": math.nan, "mean_abs_root": math.nan, "max_neighbor_jump": math.nan})
    if V == 0 or ref is None:
        out.update({"scale_vs_V0": 1.0 if V == 0 else math.nan, "offset_vs_V0": 0.0 if V == 0 else math.nan, "rms_shift_vs_V0": 0.0 if V == 0 else math.nan, "max_abs_shift_vs_V0": 0.0 if V == 0 else math.nan, "shape_rmse_after_rescale_vs_V0": 0.0 if V == 0 else math.nan, "corr_vs_V0": 1.0 if V == 0 else math.nan})
    else:
        ref_clean = ref[ref["root_status"].eq("clean") & np.isfinite(ref["omega_root"])]
        ref_map = dict(zip(ref_clean["k_index"].astype(int), ref_clean["omega_root"].astype(float)))
        pairs = [(ref_map[int(i)], yy) for i, yy in zip(kidx, y) if int(i) in ref_map]
        if len(pairs) >= 3:
            x = np.array([p[0] for p in pairs], dtype=float)
            yy = np.array([p[1] for p in pairs], dtype=float)
            A = np.vstack([x, np.ones_like(x)]).T
            scale, offset = np.linalg.lstsq(A, yy, rcond=None)[0]
            fit = scale * x + offset
            shift = yy - x
            corr = float(np.corrcoef(x, yy)[0, 1]) if np.std(x) > 0 and np.std(yy) > 0 else math.nan
            out.update({
                "scale_vs_V0": float(scale),
                "offset_vs_V0": float(offset),
                "rms_shift_vs_V0": float(np.sqrt(np.mean(shift**2))),
                "max_abs_shift_vs_V0": float(np.max(np.abs(shift))),
                "shape_rmse_after_rescale_vs_V0": float(np.sqrt(np.mean((yy - fit)**2))),
                "corr_vs_V0": corr,
            })
        else:
            out.update({"scale_vs_V0": math.nan, "offset_vs_V0": math.nan, "rms_shift_vs_V0": math.nan, "max_abs_shift_vs_V0": math.nan, "shape_rmse_after_rescale_vs_V0": math.nan, "corr_vs_V0": math.nan})
    return out


def root_csv_for(U: float, V: float) -> Path:
    return FINITE_DIR / f"rhoG_LS_U{vlabel(U)}_V{vlabel(V)}_tp0_eta0p05_roots.csv"


def plot_diagnostics_summary(metrics: pd.DataFrame, out_pdf: Path) -> None:
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    out_png = out_pdf.with_suffix(".png")
    finite = metrics[(metrics["U"] > 0) & (metrics["V"] >= 0)].copy()
    colors = {8.0: "#1f77b4", 20.0: "#ff7f0e", 40.0: "#2ca02c", 80.0: "#d62728"}
    fig, axes = plt.subplots(3, 1, figsize=(7.2, 8.2), sharex=False, gridspec_kw={"height_ratios": [1.2, 1.0, 0.8]})

    ax = axes[0]
    for U, sub in finite.groupby("U"):
        sub = sub.sort_values("V_over_U")
        y = sub["scale_vs_V0"].to_numpy(float)
        ax.plot(sub["V_over_U"], y, "o-", color=colors.get(float(U), None), label=rf"$U={U:g}$")
    ax.axvline(0.25, color="k", ls="--", lw=1.0)
    ax.set_ylabel(r"scale vs. $V=0$")
    ax.set_xlabel(r"$V/U$")
    ax.set_xlim(-0.02, 0.52)
    ax.set_title(r"Finite-$V$ Green-function-zero dispersion diagnostics ($\eta=0.05$)")
    ax.legend(ncol=4, fontsize=8)
    ax.grid(alpha=0.25)

    ax = axes[1]
    if "spectral_gap_proxy" in finite.columns:
        for U, sub in finite[finite["V"] > 0].groupby("U"):
            sub = sub.sort_values("V_over_U")
            ax.plot(sub["V_over_U"], sub["spectral_gap_proxy"], "s-", color=colors.get(float(U), None), label=rf"$U={U:g}$")
    ax.axvline(0.25, color="k", ls="--", lw=1.0)
    ax.set_ylabel("spectral gap proxy")
    ax.set_xlabel(r"$V/U$")
    ax.set_xlim(-0.02, 0.52)
    ax.text(0.01, 0.95, r"$\rho_G$ threshold proxy, not a true charge gap", transform=ax.transAxes, va="top", fontsize=8)
    ax.grid(alpha=0.25)

    ax = axes[2]
    diagnostics = [
        ("sector scan", "sector_gap_status"),
        (r"$\Delta_c$", "charge_gap_status"),
        (r"$S_c(\pi,\pi)$", "S_c_pi_pi_status"),
    ]
    finite_pos = finite[finite["V"] > 0].sort_values(["U", "V"])
    xs = np.arange(len(finite_pos))
    for j, (label, col) in enumerate(diagnostics):
        available = []
        for _, row in finite_pos.iterrows():
            status = str(row.get(col, ""))
            available.append(not status.startswith("not_available"))
        ax.scatter(xs, np.full_like(xs, j, dtype=float), c=["#2ca02c" if a else "0.65" for a in available], s=55, marker="s")
    ax.set_yticks(range(len(diagnostics)), [d[0] for d in diagnostics])
    ax.set_xticks(xs, [f"{int(r.U)},{r.V:g}" for _, r in finite_pos.iterrows()], rotation=60, ha="right", fontsize=7)
    ax.set_xlabel(r"$(U,V)$")
    ax.set_ylim(-0.6, len(diagnostics) - 0.4)
    ax.text(0.01, 0.95, "green = true diagnostic available; gray = unavailable in current data", transform=ax.transAxes, va="top", fontsize=8)
    ax.grid(axis="x", alpha=0.15)

    fig.tight_layout()
    fig.savefig(out_pdf)
    fig.savefig(out_png, dpi=200)
    plt.close(fig)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--finite-dir", type=Path, default=FINITE_DIR)
    p.add_argument("--diagnostics", type=Path, default=RESULTS / "finite_v_charge_diagnostics.csv")
    p.add_argument("--out", type=Path, default=RESULTS / "finite_v_ls_transition_metrics.csv")
    p.add_argument("--availability-out", type=Path, default=RESULTS / "refined_finite_v_data_availability.csv")
    p.add_argument("--summary-out", type=Path, default=RESULTS / "finite_v_zero_dispersion_claim_status.json")
    p.add_argument("--fig-out", type=Path, default=FIGURES / "finite_v_zero_dispersion_diagnostics_eta0p05.pdf")
    args = p.parse_args()

    rows = []
    # Include V=0 reference rows for U values that already have finite-V scans.
    finite_paths = sorted(args.finite_dir.glob("rhoG_LS_U*_V*_tp0_eta0p05_roots.csv"))
    finite_Us = sorted({float(re.search(r"U(?P<U>\d+(?:\.\d+)?)_V", path.name).group("U")) for path in finite_paths})
    for U in finite_Us:
        ref = v0_reference(U)
        if ref is not None:
            ref.attrs["source_csv"] = str((V0_DIR / f"luttinger_tp0_U{vlabel(U)}_eta0p05_curves.csv").relative_to(ROOT))
            rows.append(metrics_for_curve(ref, ref))
    for path in finite_paths:
        df = load_roots(path)
        df.attrs["source_csv"] = str(path.relative_to(ROOT))
        ref = v0_reference(float(df["U"].iloc[0]))
        rows.append(metrics_for_curve(df, ref))

    metrics = pd.DataFrame(rows).sort_values(["U", "V", "tp"])
    if args.diagnostics.exists():
        diag = pd.read_csv(args.diagnostics)
        keep = [c for c in diag.columns if c not in {"source_path"}]
        metrics = metrics.merge(diag[keep], on=["U", "V", "tp", "V_over_U"], how="left", suffixes=("", "_diag"))
    else:
        metrics["diagnostics_complete"] = False

    args.out.parent.mkdir(parents=True, exist_ok=True)
    metrics.to_csv(args.out, index=False)
    plot_diagnostics_summary(metrics, args.fig_out)

    avail_rows = []
    for U, V in PRIORITY_POINTS:
        path = root_csv_for(U, V)
        avail_rows.append({
            "U": U,
            "V": V,
            "V_over_U": V / U if U else math.nan,
            "priority": 1 if U in {20, 40} else 2,
            "root_csv": str(path.relative_to(ROOT)),
            "available": path.exists(),
            "status": "available" if path.exists() else "missing_refined_root_csv_or_raw_data",
        })
    avail = pd.DataFrame(avail_rows)
    avail.to_csv(args.availability_out, index=False)

    # Conservative claim status: require all priority-1 refined points and true diagnostics.
    priority1_complete = bool(avail.loc[avail["priority"].eq(1), "available"].all())
    used_finite = metrics[(metrics["V"] > 0) & (metrics["U"] > 0)]
    diagnostics_complete = bool(len(used_finite) and used_finite.get("diagnostics_complete", pd.Series([False])).fillna(False).all())
    claim_status = {
        "eta": 0.05,
        "priority1_refined_points_complete": priority1_complete,
        "charge_diagnostics_complete_for_finite_points": diagnostics_complete,
        "recommended_claim_language": (
            "finite-V zero-dispersion scale reversal validated against refined grid and charge diagnostics"
            if priority1_complete and diagnostics_complete
            else "finite-V zero-dispersion scale crossover/anomaly near the classical V/U=1/4 scale; refined data and true charge diagnostics pending"
        ),
        "metrics_csv": str(args.out.relative_to(ROOT)),
        "availability_csv": str(args.availability_out.relative_to(ROOT)),
    }
    args.summary_out.write_text(json.dumps(claim_status, indent=2) + "\n")
    print(f"Wrote {args.out} with {len(metrics)} rows")
    print(f"Wrote {args.fig_out}")
    print(f"Wrote {args.availability_out}")
    print(f"Wrote {args.summary_out}: {claim_status['recommended_claim_language']}")


if __name__ == "__main__":
    main()
