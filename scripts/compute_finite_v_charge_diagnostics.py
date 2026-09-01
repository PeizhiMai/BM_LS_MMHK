#!/usr/bin/env python3
"""Assemble finite-V charge/sector diagnostics for the MMHK zero-dispersion scan.

This script is intentionally conservative.  The current Green-function raw files
contain the Q sector used for the Lanczos Green function and the continued
fractions for rho_G/ReG, but they do not contain a full ground-state sector scan,
N±1 sector minima, or density-density observables.  When a true diagnostic source
is absent, the script writes NaN plus an explicit status string rather than
inventing a number.  It also reports a clearly labeled spectral-gap proxy derived
from the eta=0.05 rho_G arrays, which is *not* used as a true charge gap.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FINITE_ROOT_DIR = ROOT / "data/Gcalpath/luttinger_surface_eta0p05_other_parameter_sets"
V0_ROOT_DIR = ROOT / "data/Gcalpath/luttinger_surface_eta0p05"
U0_ROOT_DIR = ROOT / "data/Gcalpath/luttinger_surface_eta0p05_U0_finiteV"
RAW_DIR = ROOT / "data/Gcalpath/Lanczos_raw_data"
RESULTS_DIR = ROOT / "results"

RAW_RE = re.compile(
    r"U(?P<U>-?\d+(?:\.\d+)?)V(?P<V>-?\d+(?:\.\d+)?)tp(?P<tp>-?\d+(?:\.\d+)?)"
    r"f(?P<fx>\d+)x(?P<fy>\d+)Q(?P<Qx>-?\d+)x(?P<Qy>-?\d+)_(?P<kind>G[hp])\.dat$"
)


def fnum(x: float) -> str:
    return f"{x:g}"


def parse_group_from_name(path: Path) -> tuple[float, float, float] | None:
    m = RAW_RE.search(path.name)
    if not m:
        return None
    return (float(m.group("U")), float(m.group("V")), float(m.group("tp")))


def raw_inventory(raw_dir: Path) -> dict[tuple[float, float, float], dict[str, object]]:
    inv: dict[tuple[float, float, float], dict[str, object]] = defaultdict(
        lambda: {"Gh": 0, "Gp": 0, "Q": set()}
    )
    for path in raw_dir.glob("*.dat"):
        m = RAW_RE.search(path.name)
        if not m:
            continue
        key = (float(m.group("U")), float(m.group("V")), float(m.group("tp")))
        inv[key][m.group("kind")] = int(inv[key][m.group("kind")]) + 1
        inv[key]["Q"].add((int(m.group("Qx")), int(m.group("Qy"))))
    return inv


def discover_npz_groups() -> list[tuple[float, float, float, Path, str]]:
    groups: list[tuple[float, float, float, Path, str]] = []
    for path in sorted(FINITE_ROOT_DIR.glob("rhoG_LS_U*_V*_tp0_eta0p05_spectra_and_roots.npz")):
        with np.load(path, allow_pickle=True) as z:
            groups.append((float(z["U"]), float(z["V"]), float(z["tp"]), path, "finite_v"))
    for path in sorted(V0_ROOT_DIR.glob("luttinger_tp0_eta0p05_spectra_and_roots.npz")):
        with np.load(path, allow_pickle=True) as z:
            # This combined file contains several U values, so handle elsewhere.
            pass
    for csv_path in sorted(V0_ROOT_DIR.glob("luttinger_tp0_U*_eta0p05_curves.csv")):
        m = re.search(r"U(?P<U>\d+(?:\.\d+)?)_eta", csv_path.name)
        if m:
            groups.append((float(m.group("U")), 0.0, 0.0, csv_path, "v0_reference"))
    for path in sorted(U0_ROOT_DIR.glob("rhoG_LS_U0_V*_tp0_eta0p05_spectra_and_roots.npz")):
        with np.load(path, allow_pickle=True) as z:
            groups.append((float(z["U"]), float(z["V"]), float(z["tp"]), path, "u0_reference"))
    # Deduplicate by preferring spectra npz over root-only csv where both exist.
    best: dict[tuple[float, float, float], tuple[Path, str]] = {}
    priority = {"finite_v": 3, "u0_reference": 3, "v0_reference": 1}
    for U, V, tp, path, source in groups:
        key = (U, V, tp)
        if key not in best or priority[source] > priority[best[key][1]]:
            best[key] = (path, source)
    return [(U, V, tp, path, source) for (U, V, tp), (path, source) in sorted(best.items())]


def spectral_gap_proxy(npz_path: Path, rel_threshold: float) -> dict[str, float | str]:
    if npz_path.suffix != ".npz":
        return {
            "spectral_gap_proxy": math.nan,
            "spectral_gap_lower_edge": math.nan,
            "spectral_gap_upper_edge": math.nan,
            "spectral_gap_proxy_status": "not_computed_no_spectra_npz",
        }
    with np.load(npz_path, allow_pickle=True) as z:
        omega = np.asarray(z["omega"], dtype=float)
        rho = np.asarray(z["rho_G"], dtype=float)
    finite = np.isfinite(rho)
    if not finite.any():
        return {
            "spectral_gap_proxy": math.nan,
            "spectral_gap_lower_edge": math.nan,
            "spectral_gap_upper_edge": math.nan,
            "spectral_gap_proxy_status": "not_computed_no_finite_rho",
        }
    threshold = rel_threshold * float(np.nanmax(rho))
    # Use a robust path-integrated spectrum.  The proxy gap is the distance
    # between the nearest negative and positive frequencies where this integrated
    # weight exceeds a small fraction of its maximum.
    rho_path = np.nanmean(np.where(finite, rho, np.nan), axis=0)
    mask = np.isfinite(rho_path) & (rho_path >= threshold)
    neg = omega[mask & (omega < 0)]
    pos = omega[mask & (omega > 0)]
    if neg.size == 0 or pos.size == 0:
        return {
            "spectral_gap_proxy": math.nan,
            "spectral_gap_lower_edge": math.nan,
            "spectral_gap_upper_edge": math.nan,
            "spectral_gap_proxy_status": f"not_bracketed_at_rel_threshold_{rel_threshold:g}",
        }
    lower = float(neg.max())
    upper = float(pos.min())
    return {
        "spectral_gap_proxy": float(upper - lower),
        "spectral_gap_lower_edge": lower,
        "spectral_gap_upper_edge": upper,
        "spectral_gap_proxy_status": f"rho_path_threshold_proxy_rel_{rel_threshold:g}_not_true_charge_gap",
    }


def load_optional_observables(path: Path | None) -> pd.DataFrame:
    if path is None or not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    needed = {"U", "V", "tp"}
    if not needed.issubset(df.columns):
        raise ValueError(f"Optional observable file {path} must contain {sorted(needed)}")
    return df


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    p.add_argument("--optional-observables", type=Path, default=None,
                   help="Optional CSV with true diagnostics: U,V,tp,S_c_pi_pi,charge_gap,...")
    p.add_argument("--rel-threshold", type=float, default=1e-3)
    p.add_argument("--out", type=Path, default=RESULTS_DIR / "finite_v_charge_diagnostics.csv")
    args = p.parse_args()

    inv = raw_inventory(args.raw_dir)
    obs = load_optional_observables(args.optional_observables)
    obs_idx = {}
    if not obs.empty:
        for _, row in obs.iterrows():
            obs_idx[(float(row["U"]), float(row["V"]), float(row.get("tp", 0.0)))] = row.to_dict()

    rows = []
    for U, V, tp, source_path, source_kind in discover_npz_groups():
        if tp != 0.0:
            continue
        key = (float(U), float(V), float(tp))
        qset = sorted(inv.get(key, {}).get("Q", set()))
        raw_gh = int(inv.get(key, {}).get("Gh", 0))
        raw_gp = int(inv.get(key, {}).get("Gp", 0))
        q_string = ";".join(f"{qx},{qy}" for qx, qy in qset)
        if len(qset) == 1:
            qx, qy = qset[0]
            sector_status = "green_function_raw_Q_only_not_sector_scan"
        elif len(qset) > 1:
            qx, qy = qset[0]
            sector_status = "multiple_Q_in_raw_inventory_but_no_energy_scan_parser"
        else:
            qx = qy = math.nan
            sector_status = "no_raw_Q_source"

        true = obs_idx.get(key, {})
        proxy = spectral_gap_proxy(source_path, args.rel_threshold)
        row = {
            "U": U,
            "V": V,
            "tp": tp,
            "V_over_U": (V / U if U else math.nan),
            "source_kind": source_kind,
            "source_path": str(source_path.relative_to(ROOT)),
            "raw_Gh_files": raw_gh,
            "raw_Gp_files": raw_gp,
            "raw_Q_sectors_seen": q_string,
            "ground_state_Qx": true.get("ground_state_Qx", qx),
            "ground_state_Qy": true.get("ground_state_Qy", qy),
            "ground_state_sector_status": true.get("ground_state_sector_status", sector_status),
            "ground_state_degeneracy": true.get("ground_state_degeneracy", math.nan),
            "sector_gap": true.get("sector_gap", math.nan),
            "sector_gap_status": true.get("sector_gap_status", "not_available_no_sector_scan_source"),
            "charge_gap": true.get("charge_gap", math.nan),
            "charge_gap_status": true.get("charge_gap_status", "not_available_no_Npm1_ground_state_scan"),
            "pair_gap": true.get("pair_gap", math.nan),
            "pair_gap_status": true.get("pair_gap_status", "not_available_no_Npm2_ground_state_scan"),
            "S_c_pi_pi": true.get("S_c_pi_pi", math.nan),
            "S_c_pi_pi_status": true.get("S_c_pi_pi_status", "not_available_no_density_density_observable"),
            "nn_density_corr": true.get("nn_density_corr", math.nan),
            "checkerboard_proxy": true.get("checkerboard_proxy", math.nan),
            "checkerboard_proxy_status": true.get("checkerboard_proxy_status", "not_available_no_density_density_observable"),
        }
        row.update(proxy)
        row["diagnostics_complete"] = bool(
            pd.notna(row["charge_gap"]) and pd.notna(row["S_c_pi_pi"]) and row["sector_gap_status"] != "not_available_no_sector_scan_source"
        )
        rows.append(row)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows).sort_values(["U", "V", "tp"], na_position="last")
    df.to_csv(args.out, index=False)
    print(f"Wrote {args.out} with {len(df)} rows")
    incomplete = int((~df["diagnostics_complete"]).sum()) if len(df) else 0
    print(f"Diagnostics complete rows: {len(df) - incomplete}/{len(df)}")


if __name__ == "__main__":
    main()
