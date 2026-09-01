#!/usr/bin/env python3
"""Cross-validate the large-(U,V) zero-dispersion scale rules used in the paper.

The fitted convention is omega_GZ(k) = -s epsilon_0(k) + delta at t'=0.
Only U >= 20 is used for the asymptotic finite-(U,V) comparison.  The point
V/U = 1/4 is displayed as the high-scale boundary point but is excluded from
both side fits.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
SOURCE = RESULTS / "additional2_zero_dispersion_scale_fits_eta0p05.csv"

S_V = 8.0 / 7.0
R_BOUNDARY = 0.25
MIN_U = 20.0
BOOTSTRAP_SAMPLES = 5000
RNG_SEED = 20260714


def load_data() -> pd.DataFrame:
    df = pd.read_csv(SOURCE)
    df = df[(df["U"] >= MIN_U) & (df["U"] > 0)].copy()
    df["r"] = df["V"] / df["U"]
    u0 = df[df["V"] == 0].set_index("U")["s"].to_dict()
    df["s_u0"] = df["U"].map(u0)
    df["s_normalized"] = df["s"] / df["s_u0"]
    df["x_charge"] = np.where(df["V"] > 0, df["U"] / (4.0 * df["V"]), np.nan)
    df["accepted_fraction"] = df["accepted_root_count"] / 121.0
    df["missing_raw_rows"] = 121 - df["accepted_root_count"]
    return df


def fit_mott(df: pd.DataFrame, model: str) -> dict[str, float]:
    r = df["r"].to_numpy(float)
    y = df["s_normalized"].to_numpy(float)
    if model == "linear":
        a = float(np.dot(r, y - 1.0) / np.dot(r, r))
        return {"a": a}
    if model == "rational":
        objective = lambda lam: float(np.mean((y - 1.0 / (1.0 - lam * r)) ** 2))
        result = minimize_scalar(objective, bounds=(0.0, 2.0), method="bounded")
        return {"lambda": float(result.x)}
    if model == "quadratic":
        a, b = np.linalg.lstsq(np.column_stack([r, r**2]), y - 1.0, rcond=None)[0]
        return {"a": float(a), "b": float(b)}
    raise ValueError(model)


def predict_mott(df: pd.DataFrame, model: str, p: dict[str, float]) -> np.ndarray:
    r = df["r"].to_numpy(float)
    if model == "linear":
        return 1.0 + p["a"] * r
    if model == "rational":
        return 1.0 / (1.0 - p["lambda"] * r)
    if model == "quadratic":
        return 1.0 + p["a"] * r + p["b"] * r**2
    raise ValueError(model)


def fit_charge(df: pd.DataFrame, model: str) -> dict[str, float]:
    x = df["x_charge"].to_numpy(float)
    y = df["s"].to_numpy(float) - S_V
    if model == "linear":
        a = float(np.dot(x, y) / np.dot(x, x))
        return {"alpha": a}
    if model == "quadratic":
        b = float(np.dot(x**2, y) / np.dot(x**2, x**2))
        return {"beta": b}
    if model == "linear_quadratic":
        a, b = np.linalg.lstsq(np.column_stack([x, x**2]), y, rcond=None)[0]
        return {"alpha": float(a), "beta": float(b)}
    raise ValueError(model)


def predict_charge(df: pd.DataFrame, model: str, p: dict[str, float]) -> np.ndarray:
    x = df["x_charge"].to_numpy(float)
    if model == "linear":
        return S_V + p["alpha"] * x
    if model == "quadratic":
        return S_V + p["beta"] * x**2
    if model == "linear_quadratic":
        return S_V + p["alpha"] * x + p["beta"] * x**2
    raise ValueError(model)


def cross_validate(
    df: pd.DataFrame,
    model: str,
    fitter,
    predictor,
    observed_column: str,
) -> tuple[float, float, dict[str, float]]:
    full_params = fitter(df, model)
    full_pred = predictor(df, model, full_params)
    train_rmse = float(np.sqrt(np.mean((df[observed_column].to_numpy(float) - full_pred) ** 2)))

    observations: list[float] = []
    predictions: list[float] = []
    for held_out_u in sorted(df["U"].unique()):
        train = df[df["U"] != held_out_u]
        test = df[df["U"] == held_out_u]
        params = fitter(train, model)
        predictions.extend(predictor(test, model, params).tolist())
        observations.extend(test[observed_column].to_numpy(float).tolist())
    lofo_rmse = float(np.sqrt(np.mean((np.asarray(observations) - np.asarray(predictions)) ** 2)))
    return train_rmse, lofo_rmse, full_params


def choose_model(rows: list[dict[str, object]]) -> str:
    """Choose by LOFO RMSE; prefer fewer parameters when within 5%."""
    ordered = sorted(rows, key=lambda row: float(row["lofo_rmse"]))
    best = ordered[0]
    eligible = [row for row in ordered if float(row["lofo_rmse"]) <= 1.05 * float(best["lofo_rmse"])]
    eligible.sort(key=lambda row: (int(row["parameter_count"]), float(row["lofo_rmse"])))
    return str(eligible[0]["model"])


def stratified_bootstrap(
    df: pd.DataFrame,
    model: str,
    fitter,
    parameter: str,
    n: int = BOOTSTRAP_SAMPLES,
) -> tuple[float, float]:
    rng = np.random.default_rng(RNG_SEED)
    groups = [g.reset_index(drop=True) for _, g in df.groupby("U")]
    values: list[float] = []
    for _ in range(n):
        samples = []
        for group in groups:
            take = rng.integers(0, len(group), len(group))
            samples.append(group.iloc[take])
        sample = pd.concat(samples, ignore_index=True)
        try:
            values.append(float(fitter(sample, model)[parameter]))
        except (ValueError, FloatingPointError):
            continue
    return tuple(float(v) for v in np.quantile(values, [0.025, 0.975]))


def refresh_availability(df: pd.DataFrame) -> None:
    retained = [(20, 4.5), (20, 5.0), (20, 5.5), (40, 9.0), (40, 10.0),
                (80, 18.0), (80, 20.0), (80, 21.0), (80, 24.0)]
    intentionally_dropped = [(40, 11.0)]
    rows: list[dict[str, object]] = []
    for U, V in retained + intentionally_dropped:
        match = df[(df["U"] == U) & (df["V"] == V)]
        dropped = (U, V) in intentionally_dropped
        if len(match):
            rec = match.iloc[0]
            accepted = int(rec["accepted_root_count"])
            path = str(rec["source_csv"])
        else:
            accepted = 0
            path = ""
        rows.append(
            {
                "U": U,
                "V": V,
                "V_over_U": V / U,
                "required_for_current_manuscript": not dropped,
                "source_csv": path,
                "accepted_root_count": accepted,
                "accepted_fraction": accepted / 121.0,
                "available_for_scale_fit": accepted >= 110 and not dropped,
                "status": "intentionally_dropped" if dropped else ("available" if accepted >= 110 else "missing"),
            }
        )
    pd.DataFrame(rows).to_csv(RESULTS / "refined_finite_v_data_availability.csv", index=False)


def main() -> None:
    df = load_data()
    mott = df[(df["V"] > 0) & (df["r"] < R_BOUNDARY)].copy()
    charge = df[(df["V"] > 0) & (df["r"] > R_BOUNDARY)].copy()

    comparison: list[dict[str, object]] = []
    mott_models = [("linear", 1), ("rational", 1), ("quadratic", 2)]
    charge_models = [("linear", 1), ("quadratic", 1), ("linear_quadratic", 2)]
    for model, count in mott_models:
        train, lofo, params = cross_validate(
            mott, model, fit_mott, predict_mott, "s_normalized"
        )
        comparison.append(
            {"branch": "Mott/spin", "model": model, "parameter_count": count,
             "train_rmse": train, "lofo_rmse": lofo, "parameters": json.dumps(params)}
        )
    for model, count in charge_models:
        train, lofo, params = cross_validate(
            charge, model, fit_charge, predict_charge, "s"
        )
        comparison.append(
            {"branch": "charge", "model": model, "parameter_count": count,
             "train_rmse": train, "lofo_rmse": lofo, "parameters": json.dumps(params)}
        )

    mott_rows = [row for row in comparison if row["branch"] == "Mott/spin"]
    charge_rows = [row for row in comparison if row["branch"] == "charge"]
    selected_mott = choose_model(mott_rows)
    selected_charge = choose_model(charge_rows)
    mott_params = fit_mott(mott, selected_mott)
    charge_params = fit_charge(charge, selected_charge)
    lambda_ci = stratified_bootstrap(mott, selected_mott, fit_mott, "lambda")
    beta_ci = stratified_bootstrap(charge, selected_charge, fit_charge, "beta")

    for row in comparison:
        row["selected"] = (
            row["branch"] == "Mott/spin" and row["model"] == selected_mott
        ) or (
            row["branch"] == "charge" and row["model"] == selected_charge
        )
    pd.DataFrame(comparison).to_csv(
        RESULTS / "pnas_scale_model_comparison_eta0p05.csv", index=False
    )

    df["branch"] = np.select(
        [df["V"] == 0, df["r"] < R_BOUNDARY, df["r"] > R_BOUNDARY],
        ["U-only", "Mott/spin", "charge"],
        default="boundary",
    )
    df["s_selected_fit"] = np.nan
    df.loc[df["V"] == 0, "s_selected_fit"] = df.loc[df["V"] == 0, "s"]
    mmask = df["branch"] == "Mott/spin"
    cmask = df["branch"] == "charge"
    df.loc[mmask, "s_selected_fit"] = (
        predict_mott(df.loc[mmask], selected_mott, mott_params)
        * df.loc[mmask, "s_u0"].to_numpy(float)
    )
    df.loc[cmask, "s_selected_fit"] = predict_charge(
        df.loc[cmask], selected_charge, charge_params
    )
    df["fit_residual"] = df["s"] - df["s_selected_fit"]
    columns = [
        "U", "V", "r", "branch", "s", "s_u0", "s_normalized", "s_selected_fit",
        "fit_residual", "rmse", "accepted_root_count", "accepted_fraction",
        "missing_raw_rows", "source_csv",
    ]
    df[columns].to_csv(RESULTS / "pnas_scale_rule_points_eta0p05.csv", index=False)

    # Sensitivity to the few rows with incomplete momentum paths.
    complete = df[df["accepted_root_count"] == 121]
    mott_complete = complete[(complete["V"] > 0) & (complete["r"] < R_BOUNDARY)]
    charge_complete = complete[(complete["V"] > 0) & (complete["r"] > R_BOUNDARY)]
    mott_complete_params = fit_mott(mott_complete, selected_mott)
    charge_complete_params = fit_charge(charge_complete, selected_charge)

    summary = {
        "convention": "omega_GZ(k) = -s epsilon_0(k) + delta, t'=0",
        "minimum_U": MIN_U,
        "boundary_ratio": R_BOUNDARY,
        "boundary_points_excluded_from_side_fits": True,
        "selection_rule": "lowest leave-one-U-family-out RMSE; choose fewer parameters within 5%",
        "selected_mott_model": selected_mott,
        "selected_mott_rule": "s(U,V)=s(U,0)/(1-lambda V/U)",
        "mott_parameters": mott_params,
        "mott_95pct_stratified_bootstrap_ci": {"lambda": list(lambda_ci)},
        "selected_charge_model": selected_charge,
        "selected_charge_rule": "s(U,V)=8/7+beta[U/(4V)]^2",
        "charge_parameters": charge_params,
        "charge_95pct_stratified_bootstrap_ci": {"beta": list(beta_ci)},
        "complete_path_only_mott_parameters": mott_complete_params,
        "complete_path_only_charge_parameters": charge_complete_params,
        "parameter_shift_when_incomplete_rows_removed": {
            "lambda": mott_complete_params["lambda"] - mott_params["lambda"],
            "beta": charge_complete_params["beta"] - charge_params["beta"],
        },
        "minimum_accepted_fraction": float(df["accepted_fraction"].min()),
        "all_retained_points_above_90pct_path_coverage": bool((df["accepted_fraction"] > 0.9).all()),
        "source": str(SOURCE.relative_to(ROOT)),
    }
    (RESULTS / "pnas_scale_rule_summary_eta0p05.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )

    refresh_availability(df)
    status = {
        "primary_broadening": 0.05,
        "retained_refined_points_available": True,
        "all_scale_points_above_90pct_path_coverage": bool((df["accepted_fraction"] > 0.9).all()),
        "charge_sector_diagnostics_available": False,
        "direct_Sc_pi_pi_available": False,
        "sector_resolved_charge_gap_available": False,
        "recommended_claim_language": (
            "Green-function-zero dispersion reorganization near the strong-coupling "
            "Mott-charge competition scale V/U=1/4 in the 4x4 MMHK resolution"
        ),
        "scale_summary": "results/pnas_scale_rule_summary_eta0p05.json",
        "availability": "results/refined_finite_v_data_availability.csv",
    }
    (RESULTS / "finite_v_zero_dispersion_claim_status.json").write_text(
        json.dumps(status, indent=2) + "\n"
    )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
