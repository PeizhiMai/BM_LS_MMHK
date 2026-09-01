#!/usr/bin/env python3
"""Analyze the eta=0.05 zero-dispersion scale rule including additional2 data.

The fitted convention is

    omega_GZ(k) ~= -s(U,V) * epsilon_0(k) + offset,
    epsilon_0(k) = -2[cos(kx)+cos(ky)].

Outputs:
  results/additional2_zero_dispersion_scale_fits_eta0p05.csv
  results/additional2_large_uv_scale_rule_fit_eta0p05.csv
  results/additional2_large_uv_scale_rule_summary_eta0p05.json
  figures/large_uv_scale_rule/additional2_large_uv_scale_rule_eta0p05.{pdf,png}
"""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures" / "large_uv_scale_rule"

ETA = 0.05
S_V_ASYM = 8.0 / 7.0
S_U_HEISENBERG_4X4 = 1.4035604012
R_CRIT = 0.25


def eps0_from_path(kx: pd.Series, ky: pd.Series) -> np.ndarray:
    delta = math.pi / 40.0
    return -2.0 * (np.cos(kx.to_numpy(float) * delta) + np.cos(ky.to_numpy(float) * delta))


def parse_uv_from_name(path: Path) -> tuple[float, float] | None:
    name = path.name
    m = re.search(r"U(?P<U>-?\d+(?:\.\d+)?)_V(?P<V>-?\d+(?:\.\d+)?)_", name)
    if m:
        return float(m.group("U")), float(m.group("V"))
    m = re.search(r"U(?P<U>-?\d+(?:\.\d+)?)_eta0p05_curves", name)
    if m:
        return float(m.group("U")), 0.0
    return None


def root_csvs() -> list[Path]:
    dirs = [
        ROOT / "data/Gcalpath/luttinger_surface_eta0p05",
        ROOT / "data/Gcalpath/luttinger_surface_eta0p05_U0_finiteV",
        ROOT / "data/Gcalpath/luttinger_surface_eta0p05_other_parameter_sets",
    ]
    paths: list[Path] = []
    for directory in dirs:
        if directory.exists():
            paths.extend(sorted(directory.glob("*_curves.csv")))
            paths.extend(sorted(directory.glob("*_roots.csv")))
    return paths


def fit_scale(path: Path) -> dict[str, object] | None:
    uv = parse_uv_from_name(path)
    if uv is None or "tpn25" in path.name:
        return None
    U, V = uv
    df = pd.read_csv(path)
    if "tp" in df.columns and not np.isclose(float(pd.to_numeric(df["tp"], errors="coerce").dropna().iloc[0]), 0.0):
        return None
    roots = pd.to_numeric(df["omega_root"], errors="coerce")
    status_ok = df["root_status"].eq("clean") if "root_status" in df.columns else pd.Series(True, index=df.index)
    mask = status_ok & np.isfinite(roots)
    if int(mask.sum()) < 20:
        return None
    eps = eps0_from_path(df.loc[mask, "kx"], df.loc[mask, "ky"])
    y = roots.loc[mask].to_numpy(float)
    A = np.column_stack([eps, np.ones_like(eps)])
    scale_a, offset = np.linalg.lstsq(A, y, rcond=None)[0]
    pred = scale_a * eps + offset
    resid = y - pred
    return {
        "U": U,
        "V": V,
        "r": V / U if U else np.nan,
        "scale_a": float(scale_a),
        "s": float(-scale_a),
        "offset": float(offset),
        "rmse": float(np.sqrt(np.mean(resid**2))),
        "max_abs": float(np.max(np.abs(resid))),
        "accepted_root_count": int(mask.sum()),
        "source_csv": str(path.relative_to(ROOT)),
    }


def fit_lambda(mott: pd.DataFrame) -> tuple[float, float]:
    r = mott["r"].to_numpy(float)
    y = (mott["s"] / mott["s_uonly"]).to_numpy(float)
    grid = np.linspace(0.0, 1.5, 15001)
    mse = np.array([np.mean((y - 1.0 / (1.0 - lam * r)) ** 2) for lam in grid])
    idx = int(np.argmin(mse))
    return float(grid[idx]), float(np.sqrt(mse[idx]))


def fit_charge_correction(charge: pd.DataFrame) -> tuple[float, float, float]:
    x = charge["x_charge"].to_numpy(float)
    y = charge["s"].to_numpy(float) - S_V_ASYM
    mat = np.column_stack([x, x**2])
    alpha, beta = np.linalg.lstsq(mat, y, rcond=None)[0]
    pred = S_V_ASYM + alpha * x + beta * x**2
    rmse = float(np.sqrt(np.mean((charge["s"].to_numpy(float) - pred) ** 2)))
    return float(alpha), float(beta), rmse


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)

    # Deduplicate by (U,V), preferring the first directory order above for older U=0 and V=0 references.
    rows: list[dict[str, object]] = []
    seen: set[tuple[float, float]] = set()
    for path in root_csvs():
        row = fit_scale(path)
        if row is None:
            continue
        key = (float(row["U"]), float(row["V"]))
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)

    scales = pd.DataFrame(rows).sort_values(["U", "V"]).reset_index(drop=True)
    scales_out = RESULTS / "additional2_zero_dispersion_scale_fits_eta0p05.csv"
    scales.to_csv(scales_out, index=False)

    uonly = scales[(scales["U"] > 0) & (scales["V"] == 0)].set_index("U")["s"].to_dict()
    df = scales[(scales["U"] > 0)].copy()
    df["s_uonly"] = df["U"].map(uonly)
    df["x_charge"] = np.where(df["V"] > 0, df["U"] / (4.0 * df["V"]), np.nan)

    mott = df[(df["V"] > 0) & (df["r"] < R_CRIT)].copy()
    mott_boundary = df[(df["V"] > 0) & (df["r"] <= R_CRIT)].copy()
    charge = df[(df["V"] > 0) & (df["r"] > R_CRIT)].copy()
    lam, lam_rmse = fit_lambda(mott)
    lam_b, lam_b_rmse = fit_lambda(mott_boundary)
    charge_alpha, charge_beta, charge_rmse = fit_charge_correction(charge)

    def branch(row: pd.Series) -> str:
        if row["U"] == 0:
            return "V-only"
        if row["V"] == 0:
            return "U-only"
        if row["r"] < R_CRIT:
            return "Mott-side fit"
        if np.isclose(row["r"], R_CRIT):
            return "boundary"
        return "charge-side fit"

    def predict(row: pd.Series) -> float:
        if row["U"] == 0:
            return S_V_ASYM
        if row["V"] == 0:
            return float(row["s_uonly"])
        if row["r"] < R_CRIT:
            return float(row["s_uonly"] / (1.0 - lam * row["r"]))
        if row["r"] > R_CRIT:
            x = float(row["U"] / (4.0 * row["V"]))
            return float(S_V_ASYM + charge_alpha * x + charge_beta * x**2)
        return np.nan

    fit_table = scales.copy()
    fit_table["s_uonly"] = fit_table["U"].map(uonly)
    fit_table["branch"] = fit_table.apply(branch, axis=1)
    fit_table["s_formula"] = fit_table.apply(predict, axis=1)
    fit_table["formula_residual"] = fit_table["s"] - fit_table["s_formula"]
    fit_out = RESULTS / "additional2_large_uv_scale_rule_fit_eta0p05.csv"
    fit_table.to_csv(fit_out, index=False)

    u0 = scales[scales["U"] == 0].copy()
    u80 = scales[(scales["U"] == 80) & (scales["V"] == 0)]
    summary = {
        "convention": "omega_GZ(k) ~= -s(U,V) epsilon_0(k) + offset, eta=0.05, t'=0",
        "scale_fits_csv": str(scales_out.relative_to(ROOT)),
        "piecewise_fit_csv": str(fit_out.relative_to(ROOT)),
        "mott_rule": "s = s_U(U)/(1 - lambda V/U), fit on 0<V/U<1/4",
        "mott_lambda": lam,
        "mott_lambda_rmse_in_scale_ratio": lam_rmse,
        "mott_lambda_including_boundary_check": lam_b,
        "mott_lambda_including_boundary_rmse": lam_b_rmse,
        "charge_rule": "s = 8/7 + alpha (U/(4V)) + beta (U/(4V))^2, fit on V/U>1/4",
        "charge_alpha": charge_alpha,
        "charge_beta": charge_beta,
        "charge_rmse_in_s": charge_rmse,
        "v_only_asymptote": S_V_ASYM,
        "u_only_heisenberg_4x4_expected": S_U_HEISENBERG_4X4,
        "u0_scales": u0[["V", "s", "rmse", "accepted_root_count"]].to_dict(orient="records"),
        "u0_max_abs_error_vs_8_over_7": float(np.max(np.abs(u0["s"] - S_V_ASYM))) if len(u0) else None,
        "u80_v0_scale": float(u80["s"].iloc[0]) if len(u80) else None,
        "u80_minus_heisenberg_4x4": float(u80["s"].iloc[0] - S_U_HEISENBERG_4X4) if len(u80) else None,
    }
    summary_out = RESULTS / "additional2_large_uv_scale_rule_summary_eta0p05.json"
    summary_out.write_text(json.dumps(summary, indent=2) + "\n")

    # Plot observed scale and fitted rule.
    fig, ax = plt.subplots(figsize=(7.4, 4.8))
    colors = {8.0: "#1f77b4", 20.0: "#ff7f0e", 40.0: "#d62728", 80.0: "#9467bd"}
    markers = {8.0: "o", 20.0: "s", 40.0: "^", 80.0: "D"}
    for U, sub in df.groupby("U"):
        sub = sub.sort_values("r")
        color = colors.get(float(U), None)
        marker = markers.get(float(U), "o")
        # The partially complete sets used here still retain >90% of the path
        # rows and the fitted scale is stable, so show them as ordinary data
        # points.  The accepted_root_count column remains in the CSV for audit.
        ax.plot(
            sub["r"],
            sub["s"],
            lw=0,
            marker=marker,
            ms=7,
            color=color,
            label=rf"$U={U:g}$",
        )
        if U in uonly:
            rr = np.linspace(0, R_CRIT * 0.98, 200)
            ax.plot(rr, uonly[U] / (1.0 - lam * rr), color=color, lw=1.5, alpha=0.55)
    rr = np.linspace(R_CRIT * 1.02, 0.55, 250)
    x = 1.0 / (4.0 * rr)
    ax.plot(rr, S_V_ASYM + charge_alpha * x + charge_beta * x**2, color="k", lw=2.4, ls="-.")
    if len(u0):
        ax.plot(np.full(len(u0), 0.56), u0["s"], marker="x", lw=0, ms=7, color="0.2")
    ax.axvline(R_CRIT, color="0.35", lw=1.2, ls=":")
    # Restrict asymptotic reference lines to the regions where each
    # strong-coupling limit is the relevant comparison.
    ax.hlines(
        S_U_HEISENBERG_4X4,
        xmin=-0.02,
        xmax=R_CRIT,
        color="0.55",
        lw=1.0,
        ls="--",
    )
    ax.text(
        0.125,
        S_U_HEISENBERG_4X4 - 0.012,
        r"$U\to\infty,\ 4C_{\mathrm{NN}}$",
        ha="center",
        va="top",
        fontsize=9.5,
        color="0.42",
    )
    ax.hlines(
        S_V_ASYM,
        xmin=R_CRIT,
        xmax=0.59,
        color="0.2",
        lw=1.1,
        ls="--",
    )
    ax.text(
        0.585,
        S_V_ASYM - 0.012,
        r"$V$-only $8/7$",
        ha="right",
        va="top",
        fontsize=9.5,
        color="0.15",
    )
    ax.set_xlabel(r"$V/U$", fontsize=15.36)
    ax.set_ylabel(
        r"scale $s$ in $\omega_{\mathrm{GZ}}=-s\epsilon_0+\delta$",
        fontsize=15.36,
        labelpad=12,
    )
    ax.set_xlim(-0.02, 0.59)
    ax.set_ylim(1.10, 1.86)
    ax.tick_params(axis="both", which="major", labelsize=15.36)
    ax.grid(alpha=0.22)
    ax.legend(fontsize=12, ncol=1, frameon=False)
    fig.subplots_adjust(left=0.22, bottom=0.22, right=0.98, top=0.96)
    pdf = FIGURES / "additional2_large_uv_scale_rule_eta0p05.pdf"
    png = FIGURES / "additional2_large_uv_scale_rule_eta0p05.png"
    fig.savefig(pdf, bbox_inches="tight")
    fig.savefig(png, dpi=220, bbox_inches="tight")
    plt.close(fig)

    print(json.dumps({**summary, "summary_json": str(summary_out), "figure_pdf": str(pdf), "figure_png": str(png)}, indent=2))


if __name__ == "__main__":
    main()
