#!/usr/bin/env python3
"""Fit a simple large-(U,V) piecewise rule for the Luttinger-surface scale.

Convention: fit positive s in omega_GZ(k) ~= -s * epsilon_0(k)
for t'=0 and eta=0.05.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
OUTDIR = FIGURES / "large_uv_scale_rule"
OUTDIR.mkdir(parents=True, exist_ok=True)

S_V_ASYM = 8.0 / 7.0
S_U_HEISENBERG_4X4 = 1.4035604012
R_CRIT = 0.25
MIN_U_FOR_RULE = 20.0
ESSENTIAL_TARGETS = [
    (20.0, 3.0),
    (20.0, 7.0),
    (20.0, 10.0),
    (40.0, 14.0),
    (40.0, 20.0),
    (80.0, 4.0),
    (80.0, 8.0),
    (80.0, 12.0),
    (80.0, 16.0),
    (80.0, 18.0),
    (80.0, 20.0),
    (80.0, 21.0),
    (80.0, 24.0),
]


def fit_lambda_mott(df: pd.DataFrame) -> tuple[float, float]:
    """Fit f=s/s_U=1/(1-lambda*r) on the Mott-side data."""
    r = df["r"].to_numpy(float)
    y = (df["s_obs"] / df["s_uonly"]).to_numpy(float)
    grid = np.linspace(0.0, 2.0, 20001)
    err = []
    for lam in grid:
        pred = 1.0 / (1.0 - lam * r)
        err.append(np.mean((y - pred) ** 2))
    idx = int(np.argmin(err))
    return float(grid[idx]), float(np.sqrt(err[idx]))


def fit_charge_correction(df: pd.DataFrame) -> tuple[float, float, float]:
    """Fit s=s_V+alpha*(U/4V)+beta*(U/4V)^2 on charge-side data.

    The fixed-asymptote pure quadratic form forced the curve to approach 8/7
    too quickly over the available range V/U <= 0.5.  Including the linear
    correction keeps the V-only asymptote while allowing a slower monotone
    approach that is visible in the data.
    """
    x = df["x_charge"].to_numpy(float)
    y = df["s_obs"].to_numpy(float) - S_V_ASYM
    mat = np.column_stack([x, x**2])
    alpha, beta = np.linalg.lstsq(mat, y, rcond=None)[0]
    pred = S_V_ASYM + alpha * x + beta * x**2
    rmse = float(np.sqrt(np.mean((df["s_obs"].to_numpy(float) - pred) ** 2)))
    return float(alpha), float(beta), rmse


def load_scale_data() -> tuple[pd.DataFrame, pd.DataFrame, str]:
    """Load the most complete eta=0.05 scale table available.

    Prefer the root-CSV refit generated after the additional2 download because it
    contains the new U=0,V=16,20, U=20,V=4.5,5,5.5, U=40,V=6,9,10, and U=80,V=0
    points.  Fall back to the older finite-V metric table if the refit is absent.
    """
    additional = RESULTS / "additional2_zero_dispersion_scale_fits_eta0p05.csv"
    if additional.exists():
        scales = pd.read_csv(additional)
        scales["U"] = scales["U"].astype(float)
        scales["V"] = scales["V"].astype(float)
        scales["r"] = np.where(scales["U"] > 0, scales["V"] / scales["U"], np.nan)
        scales["s_obs"] = scales["s"].astype(float)
        scales["accepted_root_count"] = scales["accepted_root_count"].astype(int)
        scales["missing_raw_rows"] = np.maximum(121 - scales["accepted_root_count"], 0).astype(int)
        uonly_map = scales[(scales["U"] > 0) & (scales["V"] == 0)].set_index("U")["s_obs"].to_dict()
        finite = scales[scales["U"] > 0].copy()
        finite["s_uonly"] = finite["U"].map(uonly_map)
        finite["x_charge"] = np.where(finite["V"] > 0, finite["U"] / (4.0 * finite["V"]), np.nan)
        return finite, scales[scales["U"] == 0].copy(), str(additional.relative_to(ROOT))

    fv = pd.read_csv(RESULTS / "finite_v_ls_transition_metrics.csv")
    uonly = pd.read_csv(RESULTS / "ls_noninteracting_scale_summary.csv")
    uonly = uonly[(uonly["eta"] == 0.05) & (uonly["tp"] == 0)][["U", "scale_fixed_tp"]]
    df = fv.merge(uonly, on="U", how="left")
    df = df[(df["U"].isin([8, 20, 40])) & (df["V"] >= 0)].copy()
    df["r"] = df["V"] / df["U"]
    df["s_uonly"] = -df["scale_fixed_tp"]
    df["s_obs"] = -df["scale_fixed_tp"] * df["scale_vs_V0"]
    df.loc[df["V"] == 0, "s_obs"] = df.loc[df["V"] == 0, "s_uonly"]
    df["x_charge"] = np.where(df["V"] > 0, df["U"] / (4.0 * df["V"]), np.nan)
    return df, pd.DataFrame(), "legacy finite_v_ls_transition_metrics.csv"


def expected_targets(df: pd.DataFrame, lam: float, alpha: float, beta: float) -> pd.DataFrame:
    """Expected positions of missing/essential target sets on the fitted rule."""
    uonly = df[df["V"] == 0].set_index("U")["s_uonly"].to_dict()
    rows: list[dict[str, object]] = []
    existing = {(float(row.U), float(row.V)) for _, row in df.iterrows()}
    for U, V in ESSENTIAL_TARGETS:
        if U not in uonly:
            continue
        r = V / U
        if r < R_CRIT:
            expected_s = float(uonly[U] / (1.0 - lam * r))
            branch = "Mott/spin expected"
        elif r > R_CRIT:
            x = 1.0 / (4.0 * r)
            expected_s = float(S_V_ASYM + alpha * x + beta * x**2)
            branch = "CDW/charge expected"
        else:
            # At the discontinuous empirical crossover, use the high-branch
            # continuation because the available U=20,40 boundary points sit on
            # the high-scale side before the drop above V/U=1/4.
            expected_s = float(uonly[U] / (1.0 - lam * r))
            branch = "boundary/high-branch expected"
        rows.append(
            {
                "U": U,
                "V": V,
                "r": r,
                "expected_s": expected_s,
                "branch": branch,
                "already_in_scale_table": (U, V) in existing,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    df_all, u0_checks, scale_source = load_scale_data()
    # The U=8 zero branch is visibly more piecewise/branch-sensitive, so the
    # large-U,V scale-rule plot and fits use only the more asymptotic U>=20 data.
    df = df_all[df_all["U"] >= MIN_U_FOR_RULE].copy()

    mott = df[(df["V"] > 0) & (df["r"] < R_CRIT) & np.isfinite(df["s_uonly"])].copy()
    charge = df[(df["V"] > 0) & (df["r"] > R_CRIT)].copy()
    lam, lam_rmse = fit_lambda_mott(mott)
    charge_alpha, charge_beta, charge_rmse = fit_charge_correction(charge)

    def predict(row: pd.Series, fitted: bool = True) -> float:
        if row["V"] == 0:
            return float(row["s_uonly"])
        r = float(row["r"])
        if r < R_CRIT:
            lam_use = lam if fitted else 1.0
            return float(row["s_uonly"] / (1.0 - lam_use * r))
        if r > R_CRIT:
            x = float(row["x_charge"])
            return float(S_V_ASYM + charge_alpha * x + charge_beta * x**2)
        return float("nan")

    df["branch"] = np.select(
        [df["V"] == 0, df["r"] < R_CRIT, df["r"] > R_CRIT],
        ["U-only", "Mott/spin side", "charge/CDW side"],
        default="near boundary",
    )
    df["s_piecewise_fit"] = df.apply(lambda row: predict(row, True), axis=1)
    df["s_piecewise_theory_lambda1"] = df.apply(lambda row: predict(row, False), axis=1)
    df["residual_fit"] = df["s_obs"] - df["s_piecewise_fit"]
    df["residual_theory_lambda1"] = df["s_obs"] - df["s_piecewise_theory_lambda1"]

    out_csv = RESULTS / "large_uv_luttinger_scale_piecewise_fit.csv"
    keep = [
        "U", "V", "r", "branch", "s_obs", "s_uonly", "s_piecewise_fit",
        "s_piecewise_theory_lambda1", "residual_fit", "residual_theory_lambda1",
        "accepted_root_count", "missing_raw_rows",
    ]
    df[keep].to_csv(out_csv, index=False)

    # Compatibility copy for manuscript/source references that used the older name.
    simple_out = RESULTS / "large_uv_luttinger_scale_simple_rule_check.csv"
    simple = df[keep].rename(
        columns={
            "s_piecewise_theory_lambda1": "s_simple_analytic",
            "residual_theory_lambda1": "analytic_residual",
            "s_piecewise_fit": "s_empirical_fit",
            "residual_fit": "empirical_residual",
        }
    )
    simple.to_csv(simple_out, index=False)

    summary = {
        "convention": "omega_GZ(k) ~= -s(U,V) epsilon_0(k), t'=0, eta=0.05",
        "scale_source": scale_source,
        "minimum_U_in_scale_rule_fit_and_plot": MIN_U_FOR_RULE,
        "excluded_reason": "U=8 branch is more piecewise/root-branch-sensitive; use U>=20 for large-U,V rule",
        "critical_ratio_atomic": R_CRIT,
        "u_only_asymptote_4x4": float(df.loc[(df.U == 40) & (df.V == 0), "s_obs"].iloc[0]),
        "u_only_heisenberg_4x4_expected": S_U_HEISENBERG_4X4,
        "u80_v0_scale_if_available": (
            float(df.loc[(df.U == 80) & (df.V == 0), "s_obs"].iloc[0])
            if len(df.loc[(df.U == 80) & (df.V == 0)])
            else None
        ),
        "v_only_asymptote": S_V_ASYM,
        "u0_scales_if_available": (
            u0_checks[["V", "s_obs", "accepted_root_count"]].to_dict(orient="records")
            if len(u0_checks)
            else []
        ),
        "mott_rule": "s = s_U(U)/(1 - lambda V/U)",
        "mott_lambda_fit_all_available_r_less_1_over_4": lam,
        "mott_lambda_fit_rmse": lam_rmse,
        "mott_lambda_theory_from_adjacent_doublon_holon_denominator": 1.0,
        "charge_rule": "s = 8/7 + alpha (U/(4V)) + beta (U/(4V))^2",
        "charge_alpha_fit": charge_alpha,
        "charge_beta_fit": charge_beta,
        "charge_fit_rmse": charge_rmse,
        "fit_csv": str(out_csv),
    }
    out_json = RESULTS / "large_uv_luttinger_scale_rule_summary.json"
    out_json.write_text(json.dumps(summary, indent=2) + "\n")
    targets = expected_targets(df, lam=lam, alpha=charge_alpha, beta=charge_beta)
    target_out = RESULTS / "large_uv_luttinger_scale_essential_targets_expected_eta0p05.csv"
    targets.to_csv(target_out, index=False)

    # Figure 1: observed s versus V/U with piecewise rule curves for each U.
    fig, ax = plt.subplots(figsize=(7.35, 4.8))
    colors = {20.0: "#ff7f0e", 40.0: "#d62728", 80.0: "#9467bd"}
    markers = {20.0: "s", 40.0: "^", 80.0: "D"}
    # Lightly mark the two branches/regions without obscuring the data.
    ax.axvspan(-0.02, R_CRIT, color="#1f77b4", alpha=0.035, zorder=0)
    ax.axvspan(R_CRIT, 0.59, color="#d62728", alpha=0.030, zorder=0)

    for U, g in df.groupby("U"):
        g = g.sort_values("r")
        if U not in colors:
            continue
        label = rf"$U={U:g}$"
        # The few partially complete sets still have >90% of the path rows and
        # give stable scale fits, so show them as ordinary data points.  Keep
        # missing_raw_rows in the CSV for provenance, but do not label or style
        # them separately in the manuscript-facing plot.
        ax.plot(
            g["r"],
            g["s_obs"],
            marker=markers[U],
            color=colors[U],
            lw=0,
            ms=7,
            label=label,
        )
        # Mott side fitted rule from r=0 to just below 1/4.
        sU = float(g.loc[g["V"] == 0, "s_uonly"].iloc[0])
        rr1 = np.linspace(0, R_CRIT * 0.98, 200)
        alpha = 0.65 if U in (20.0, 40.0) else 0.32
        lw = 1.8 if U in (20.0, 40.0) else 1.2
        ax.plot(rr1, sU / (1.0 - lam * rr1), color=colors[U], lw=lw, alpha=alpha)
    rr2 = np.linspace(R_CRIT * 1.02, 0.55, 250)
    x2 = 1.0 / (4.0 * rr2)
    ax.plot(rr2, S_V_ASYM + charge_alpha * x2 + charge_beta * x2**2, color="k", lw=2.4, ls="-.")
    if len(u0_checks):
        ax.plot(
            np.full(len(u0_checks), 0.565),
            u0_checks["s_obs"],
            marker="x",
            lw=0,
            ms=7,
            mew=1.6,
            color="0.15",
        )
    ax.axvline(R_CRIT, color="0.35", lw=1.2, ls=":")
    # Draw the asymptotic reference lines only in the regions where the
    # corresponding strong-coupling limit is meant to apply.
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
        color="0.1",
        lw=1.3,
        ls="--",
    )
    ax.text(
        0.585,
        S_V_ASYM - 0.012,
        r"$V$-only $8/7$",
        ha="right",
        va="top",
        fontsize=9.5,
        color="0.1",
    )
    ax.text(
        0.115,
        1.075,
        "Mott / spin side",
        ha="center",
        va="bottom",
        fontsize=11,
        color="#1f4e79",
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.65, "pad": 2.0},
    )
    ax.text(
        0.415,
        1.075,
        "CDW / charge side",
        ha="center",
        va="bottom",
        fontsize=11,
        color="#8c1d18",
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.65, "pad": 2.0},
    )
    ax.set_xlabel(r"$V/U$", fontsize=15.36)
    ax.set_ylabel(r"scale $s$ in $\omega_{\mathrm{GZ}}=-s\epsilon_0$", fontsize=15.36, labelpad=12)
    ax.set_xlim(-0.02, 0.59)
    ax.set_ylim(1.05, 1.85)
    ax.tick_params(axis="both", which="major", labelsize=15.36)
    ax.legend(fontsize=11.5, ncol=1, frameon=False)
    ax.grid(alpha=0.2)
    fig.subplots_adjust(left=0.22, bottom=0.22, right=0.98, top=0.96)
    out_png = OUTDIR / "large_uv_luttinger_scale_piecewise_rule_eta0p05.png"
    out_pdf = OUTDIR / "large_uv_luttinger_scale_piecewise_rule_eta0p05.pdf"
    fig.savefig(out_png, dpi=220, bbox_inches="tight")
    fig.savefig(out_pdf, bbox_inches="tight")

    # Annotated planning version: show where the essential missing sets should
    # land if the fitted scale rule is correct.
    if len(targets):
        target_colors = {20.0: "#ff7f0e", 40.0: "#d62728", 80.0: "#9467bd"}
        plotted_label = False
        # Group charge-side targets that share the same expected point.
        grouped: dict[tuple[float, float], list[dict[str, object]]] = {}
        for _, target in targets.iterrows():
            key = (round(float(target["r"]), 5), round(float(target["expected_s"]), 5))
            grouped.setdefault(key, []).append(target.to_dict())
        for idx, ((r_key, s_key), items) in enumerate(sorted(grouped.items())):
            r = float(items[0]["r"])
            s = float(items[0]["expected_s"])
            dominant_U = float(items[0]["U"])
            color = target_colors.get(dominant_U, "0.25")
            labels = [f"{int(item['U'])},{item['V']:g}" for item in items]
            text = ";".join(labels)
            ax.plot(
                r,
                s,
                marker="o",
                ms=6.0,
                mfc="white",
                mec=color,
                mew=1.4,
                lw=0,
                label="essential targets (expected)" if not plotted_label else None,
                zorder=8,
            )
            plotted_label = True
            # Hand-tuned offsets to reduce collisions near the crossover.
            if r < 0.25:
                dy = 8 if idx % 2 == 0 else -12
                dx = 4
            elif np.isclose(r, 0.25):
                dy = 12
                dx = 4
            else:
                dy = -12 if idx % 2 == 0 else 8
                dx = 4
            if r >= 0.35:
                dy = 8
            ax.annotate(
                text,
                xy=(r, s),
                xytext=(dx, dy),
                textcoords="offset points",
                fontsize=6.6,
                color=color,
                ha="left",
                va="center",
                rotation=0,
                bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.72, "pad": 0.7},
                zorder=9,
            )
        ax.legend(fontsize=11.1, ncol=1, frameon=False)
        target_png = OUTDIR / "large_uv_luttinger_scale_piecewise_rule_with_essential_targets_eta0p05.png"
        target_pdf = OUTDIR / "large_uv_luttinger_scale_piecewise_rule_with_essential_targets_eta0p05.pdf"
        fig.savefig(target_png, dpi=220, bbox_inches="tight")
        fig.savefig(target_pdf, bbox_inches="tight")
    plt.close(fig)

    print(
        json.dumps(
            {
                "csv": str(out_csv),
                "summary": str(out_json),
                "png": str(out_png),
                "pdf": str(out_pdf),
                "target_csv": str(target_out),
                "target_png": str(OUTDIR / "large_uv_luttinger_scale_piecewise_rule_with_essential_targets_eta0p05.png"),
                "target_pdf": str(OUTDIR / "large_uv_luttinger_scale_piecewise_rule_with_essential_targets_eta0p05.pdf"),
                **summary,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
