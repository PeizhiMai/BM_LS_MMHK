#!/usr/bin/env python3
"""Audit eta=0.05 Green-function-zero branch tracking choices.

Compares the current root CSV branch against several alternative fixed-eta
choices using the stored candidate roots and rho_G spectra:
  - local minimum-rho candidate;
  - local nearest-to-asymptotic-reference candidate;
  - smooth dynamic-program branches with varied continuity penalties;
  - reversed-path smooth dynamic-program branch.

Outputs a robustness CSV and a candidate-root audit PDF.
"""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FINITE_DIR = ROOT / "data/Gcalpath/luttinger_surface_eta0p05_other_parameter_sets"
V0_DIR = ROOT / "data/Gcalpath/luttinger_surface_eta0p05"
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
AUDIT_CASES = [(8, 1), (8, 2), (20, 4), (20, 6), (40, 8), (40, 12)]
S_V_ASYM = 8.0 / 7.0


def vlabel(x: float) -> str:
    return f"{x:g}"


def epsilon_from_k(kx: np.ndarray, ky: np.ndarray) -> np.ndarray:
    return -2.0 * (np.cos(np.pi * kx / 40.0) + np.cos(np.pi * ky / 40.0))


def parse_candidates(s: object) -> list[float]:
    if not isinstance(s, str) or not s.strip():
        return []
    vals = []
    for part in s.split(";"):
        try:
            vals.append(float(part))
        except ValueError:
            pass
    return vals


def interp_rho(omega_grid: np.ndarray, rho_row: np.ndarray, omega: float) -> float:
    if not np.isfinite(omega):
        return math.nan
    return float(np.interp(omega, omega_grid, rho_row))


def load_group(U: float, V: float) -> tuple[pd.DataFrame, dict[str, np.ndarray]]:
    csv_path = FINITE_DIR / f"rhoG_LS_U{vlabel(U)}_V{vlabel(V)}_tp0_eta0p05_roots.csv"
    npz_path = FINITE_DIR / f"rhoG_LS_U{vlabel(U)}_V{vlabel(V)}_tp0_eta0p05_spectra_and_roots.npz"
    if not csv_path.exists() or not npz_path.exists():
        raise FileNotFoundError(f"Missing root/spectra for U={U}, V={V}: {csv_path}, {npz_path}")
    df = pd.read_csv(csv_path).sort_values("k_index")
    z = np.load(npz_path, allow_pickle=True)
    arrays = {k: np.asarray(z[k]) for k in z.files}
    z.close()
    return df, arrays


def uonly_scale(U: float) -> float:
    path = RESULTS / "ls_noninteracting_scale_summary_eta0p05.csv"
    if path.exists():
        df = pd.read_csv(path)
        sub = df[(df["tp"].astype(float).eq(0.0)) & (df["U"].astype(float).eq(float(U)))]
        if len(sub):
            return float(-sub.iloc[0]["scale_fixed_tp"])
    return 1.4


def reference_curve(df: pd.DataFrame, U: float, V: float) -> np.ndarray:
    eps = epsilon_from_k(df["kx"].to_numpy(float), df["ky"].to_numpy(float))
    if U > 0 and V / U < 0.25:
        s = uonly_scale(U) / max(1e-9, (1.0 - 0.82 * V / U))
    elif U > 0 and V / U > 0.25:
        s = S_V_ASYM + 0.178 * (U / (4.0 * V)) ** 2
    elif U > 0:
        s = max(uonly_scale(U), S_V_ASYM)
    else:
        s = S_V_ASYM
    return -s * eps


def candidate_matrix(df: pd.DataFrame, arrays: dict[str, np.ndarray]) -> tuple[list[list[float]], list[list[float]]]:
    omega_grid = arrays["omega"].astype(float)
    rho = arrays["rho_G"].astype(float)
    all_cands: list[list[float]] = []
    all_rhos: list[list[float]] = []
    for row_idx, row in df.reset_index(drop=True).iterrows():
        cands = parse_candidates(row.get("candidate_omega_roots", ""))
        if not cands and row.get("root_status") == "clean" and pd.notna(row.get("omega_root")):
            cands = [float(row["omega_root"])]
        all_cands.append(cands)
        all_rhos.append([interp_rho(omega_grid, rho[row_idx], c) for c in cands])
    return all_cands, all_rhos


def local_branch(cands: list[list[float]], scores: list[list[float]]) -> np.ndarray:
    out = []
    for cs, ss in zip(cands, scores):
        if not cs:
            out.append(math.nan)
        else:
            idx = int(np.nanargmin(np.asarray(ss, dtype=float)))
            out.append(float(cs[idx]))
    return np.asarray(out, dtype=float)


def nearest_reference_branch(cands: list[list[float]], ref: np.ndarray) -> np.ndarray:
    out = []
    for cs, rr in zip(cands, ref):
        if not cs or not np.isfinite(rr):
            out.append(math.nan)
        else:
            idx = int(np.argmin(np.abs(np.asarray(cs, dtype=float) - rr)))
            out.append(float(cs[idx]))
    return np.asarray(out, dtype=float)


def dp_branch(cands: list[list[float]], rhos: list[list[float]], smooth_weight: float, reverse: bool = False) -> np.ndarray:
    n = len(cands)
    order = list(range(n - 1, -1, -1)) if reverse else list(range(n))
    # robust smooth scale from all candidates/current range
    flat = np.array([c for cs in cands for c in cs], dtype=float)
    smooth_scale = max(1.0, float(np.nanpercentile(flat, 90) - np.nanpercentile(flat, 10)) / max(8.0, n / 8.0)) if flat.size else 1.0
    costs: list[np.ndarray] = []
    parents: list[np.ndarray] = []
    prev_cost = None
    prev_vals = None
    for pos, idx in enumerate(order):
        vals = np.asarray(cands[idx], dtype=float)
        if vals.size == 0:
            vals = np.array([math.nan])
        rho_vals = np.asarray(rhos[idx] if cands[idx] else [math.nan], dtype=float)
        rho_norm = rho_vals / np.nanmedian(rho_vals[np.isfinite(rho_vals)]) if np.isfinite(rho_vals).any() and np.nanmedian(rho_vals[np.isfinite(rho_vals)]) > 0 else np.zeros_like(vals)
        if pos == 0 or prev_cost is None or prev_vals is None:
            cost = np.nan_to_num(rho_norm, nan=1.0)
            parent = np.full(vals.size, -1, dtype=int)
        else:
            cost = np.empty(vals.size)
            parent = np.empty(vals.size, dtype=int)
            for j, val in enumerate(vals):
                trans = smooth_weight * ((val - prev_vals) / smooth_scale) ** 2
                tot = np.nan_to_num(prev_cost + trans, nan=1.0e12, posinf=1.0e12, neginf=1.0e12)
                parent[j] = int(np.argmin(tot))
                cost[j] = float(tot[parent[j]] + np.nan_to_num(rho_norm[j], nan=1.0))
        costs.append(cost)
        parents.append(parent)
        prev_cost, prev_vals = cost, vals
    chosen_rev = [0] * len(order)
    chosen_rev[-1] = int(np.nanargmin(costs[-1]))
    for pos in range(len(order) - 1, 0, -1):
        chosen_rev[pos - 1] = int(parents[pos][chosen_rev[pos]])
    branch = np.full(n, np.nan)
    for pos, idx in enumerate(order):
        vals = np.asarray(cands[idx], dtype=float)
        if vals.size:
            branch[idx] = float(vals[chosen_rev[pos]])
    return branch


def fit_scale(df: pd.DataFrame, omega: np.ndarray) -> tuple[float, float, float, float]:
    mask = np.isfinite(omega)
    eps = epsilon_from_k(df["kx"].to_numpy(float), df["ky"].to_numpy(float))
    if mask.sum() < 3:
        return math.nan, math.nan, math.nan, math.nan
    A = np.vstack([eps[mask], np.ones(mask.sum())]).T
    slope, offset = np.linalg.lstsq(A, omega[mask], rcond=None)[0]
    fit = slope * eps[mask] + offset
    rmse = float(np.sqrt(np.mean((omega[mask] - fit) ** 2)))
    bw = float(np.nanmax(omega[mask]) - np.nanmin(omega[mask]))
    return float(-slope), float(offset), rmse, bw


def audit_group(U: float, V: float) -> tuple[pd.DataFrame, dict[str, np.ndarray], list[list[float]]]:
    df, arrays = load_group(U, V)
    cands, rhos = candidate_matrix(df, arrays)
    ref = reference_curve(df, U, V)
    branches = {
        "current_csv": df["omega_root"].to_numpy(float),
        "local_min_rho": local_branch(cands, rhos),
        "local_nearest_reference": nearest_reference_branch(cands, ref),
        "dp_smooth_0p25": dp_branch(cands, rhos, 0.25, reverse=False),
        "dp_smooth_1": dp_branch(cands, rhos, 1.0, reverse=False),
        "dp_smooth_4": dp_branch(cands, rhos, 4.0, reverse=False),
        "dp_reverse_smooth_1": dp_branch(cands, rhos, 1.0, reverse=True),
    }
    rows = []
    current = branches["current_csv"]
    for name, omega in branches.items():
        s, off, rmse, bw = fit_scale(df, omega)
        diff = omega - current
        rows.append({
            "U": U,
            "V": V,
            "V_over_U": V / U if U else math.nan,
            "branch_rule": name,
            "scale_s_positive": s,
            "fit_offset": off,
            "fit_rmse": rmse,
            "bandwidth": bw,
            "accepted_points": int(np.isfinite(omega).sum()),
            "rms_difference_vs_current": float(np.sqrt(np.nanmean(diff**2))) if np.isfinite(diff).any() else math.nan,
            "max_abs_difference_vs_current": float(np.nanmax(np.abs(diff))) if np.isfinite(diff).any() else math.nan,
            "candidate_roots_max": int(pd.to_numeric(df["candidate_roots"], errors="coerce").max()),
            "candidate_roots_mean": float(pd.to_numeric(df["candidate_roots"], errors="coerce").mean()),
        })
    return pd.DataFrame(rows), branches, cands


def plot_group(pdf: PdfPages, U: float, V: float, branches: dict[str, np.ndarray], cands: list[list[float]], df: pd.DataFrame) -> None:
    x = df["x_path"].to_numpy(float)
    fig, ax = plt.subplots(figsize=(8.0, 4.7))
    for xi, cs in zip(x, cands):
        if cs:
            ax.scatter([xi] * len(cs), cs, s=8, color="0.65", alpha=0.65, linewidths=0)
    ax.plot(x, branches["current_csv"], color="white", lw=4.0, zorder=3)
    ax.plot(x, branches["current_csv"], color="black", lw=2.0, label="current CSV", zorder=4)
    ax.plot(x, branches["local_min_rho"], color="#1f77b4", lw=1.2, label="local min rho")
    ax.plot(x, branches["local_nearest_reference"], color="#ff7f0e", lw=1.2, label="nearest reference")
    ax.plot(x, branches["dp_smooth_1"], color="#2ca02c", lw=1.2, label="DP smooth")
    ax.plot(x, branches["dp_reverse_smooth_1"], color="#d62728", lw=1.2, ls="--", label="DP reverse")
    ax.axhline(0, color="0.85", lw=0.8)
    ax.set_title(f"Candidate zero roots and branch audit: U={U:g}, V={V:g}, eta=0.05")
    ax.set_xlabel(r"$\Gamma-X-M-\Gamma$ path coordinate")
    ax.set_ylabel(r"$\omega_{\mathrm{GZ}}(\mathbf{k})/t$")
    ax.legend(loc="best", fontsize=8, ncol=2)
    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cases", nargs="*", default=[f"{U},{V}" for U, V in AUDIT_CASES], help="Cases as U,V")
    p.add_argument("--out", type=Path, default=RESULTS / "zero_branch_robustness_eta0p05.csv")
    p.add_argument("--fig", type=Path, default=FIGURES / "zero_branch_candidate_audit_eta0p05.pdf")
    args = p.parse_args()

    all_rows = []
    args.fig.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(args.fig) as pdf:
        for item in args.cases:
            U_s, V_s = item.split(",")
            U = float(U_s); V = float(V_s)
            try:
                rows, branches, cands = audit_group(U, V)
                df, _ = load_group(U, V)
            except FileNotFoundError as exc:
                all_rows.append(pd.DataFrame([{"U": U, "V": V, "branch_rule": "all", "status": str(exc)}]))
                continue
            rows["status"] = "computed"
            all_rows.append(rows)
            plot_group(pdf, U, V, branches, cands, df)
    out_df = pd.concat(all_rows, ignore_index=True) if all_rows else pd.DataFrame()
    # Qualitative robustness flag per U,V: all non-current rules within 15% of current scale.
    flags = []
    for (U, V), sub in out_df[out_df["status"].eq("computed")].groupby(["U", "V"]):
        cur = sub.loc[sub["branch_rule"].eq("current_csv"), "scale_s_positive"]
        if len(cur) and np.isfinite(cur.iloc[0]):
            rel = np.abs(sub["scale_s_positive"] - cur.iloc[0]) / max(abs(cur.iloc[0]), 1e-12)
            robust = bool((rel.fillna(np.inf) <= 0.15).all())
        else:
            robust = False
        flags.append({"U": U, "V": V, "branch_scale_robust_15pct": robust})
    if flags:
        out_df = out_df.merge(pd.DataFrame(flags), on=["U", "V"], how="left")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(args.out, index=False)
    print(f"Wrote {args.out} with {len(out_df)} rows")
    print(f"Wrote {args.fig}")


if __name__ == "__main__":
    main()
