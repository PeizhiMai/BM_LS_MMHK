#!/usr/bin/env python3
"""Fit one arbitrary (U,V,t') Green-function-zero dispersion.

This is the reusable single-group entry point introduced by the 2026-07-31
bond-resolved plan.  The pre-existing ``fit_tpn25_zero_dispersion.py`` remains
available unchanged for exact reproduction of its historical outputs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from analyze_bond_resolved_zero_theorem import GroupData, fit_group, value_label
from generate_eta005_other_parameter_colorplots import ParameterGroup, compute_group
from reproduce_luttinger_figures import default_k_path, x_centers


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--U", type=float, required=True)
    p.add_argument("--V", type=float, required=True)
    p.add_argument("--tprime", type=float, required=True)
    p.add_argument("--data-dir", type=Path, default=ROOT / "data/Gcalpath/Lanczos_raw_data")
    p.add_argument("--eta", type=float, default=0.05)
    p.add_argument("--omega-max", type=float, default=60.0)
    p.add_argument("--omega-points", type=int, default=6001)
    p.add_argument("--steps-max", type=int, default=1000)
    p.add_argument("--output-dir", type=Path, default=ROOT / "results/bond_resolved_single_groups")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if not np.isclose(args.eta, 0.05):
        raise ValueError("The established root audit is currently fixed at eta=0.05")
    group = ParameterGroup(args.U, args.V, args.tprime)
    omega = np.linspace(-args.omega_max, args.omega_max, args.omega_points)
    rho, re_g, roots, root_rows, ylim, root_window, color_vmax = compute_group(
        args.data_dir.resolve(), group, omega, args.eta, (0, 0), args.steps_max, 4,
        0.25, 2.0, 5,
    )
    data = GroupData(group, omega, rho, re_g, roots, root_rows, ylim, root_window, color_vmax)
    rows, predictions = fit_group(data)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"U{value_label(args.U)}_V{value_label(args.V)}_tp{value_label(args.tprime).replace('-', 'n').replace('.', 'p')}_eta0p05"
    metrics = args.output_dir / f"{stem}_metrics.csv"
    curves = args.output_dir / f"{stem}_curves.csv"
    npz = args.output_dir / f"{stem}_spectra_and_roots.npz"
    pd.DataFrame(rows).to_csv(metrics, index=False)
    path = default_k_path()
    curve_rows = []
    for i, ((kx, ky), x, root_row) in enumerate(zip(path, x_centers(), root_rows)):
        row = {
            "U": args.U, "V": args.V, "tprime": args.tprime, "eta": args.eta,
            "k_index": i, "kx": kx, "ky": ky, "x_path": x, **root_row,
        }
        for model, prediction in predictions.items():
            row[f"omega_{model}"] = float(prediction[i])
        curve_rows.append(row)
    pd.DataFrame(curve_rows).to_csv(curves, index=False)
    np.savez_compressed(
        npz, U=args.U, V=args.V, tp=args.tprime, eta=args.eta,
        omega=omega, x_path=x_centers(), k_path=np.asarray(path, dtype=int),
        rho_G=rho, reG=re_g, omega_root=roots,
    )
    summary = {
        "U": args.U, "V": args.V, "tprime": args.tprime, "eta": args.eta,
        "root_count_unique": int(np.isfinite(roots[:120]).sum()),
        "root_count_plotted": int(np.isfinite(roots).sum()),
        "outputs": {"metrics": str(metrics), "curves": str(curves), "npz": str(npz)},
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
