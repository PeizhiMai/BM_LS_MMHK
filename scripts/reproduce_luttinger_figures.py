#!/usr/bin/env python3
"""Reproduce Fig. 3/4-style Luttinger-surface figures from raw Lanczos data.

This script is intentionally self-contained so the extracted ReG=0 curves and
figures can be regenerated directly from data/Gcalpath/Lanczos_raw_data.
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import curve_fit

NUMBER_RE = r"-?(?:\d+(?:\.\d*)?|\.\d+)"
FILE_RE = re.compile(
    rf"L4x4Nup8Ndn8U(?P<U>{NUMBER_RE})V(?P<V>{NUMBER_RE})"
    rf"tp(?P<tp>{NUMBER_RE})f(?P<kx>\d+)x(?P<ky>\d+)Q0x0_(?P<kind>G[hp])\.dat$"
)
U_VALUES = (8, 12, 20, 40)
TP_VALUES = (0.0, -0.25)
TP_LABELS = {0.0: "tp0", -0.25: "tpn25"}
TP_TITLES = {0.0: r"$t'=0$", -0.25: r"$t'=-0.25t$"}


@dataclass(frozen=True)
class GreenComponent:
    path: Path
    kind: str
    U: float
    V: float
    tp: float
    E0: float
    a: np.ndarray
    b: np.ndarray
    nrm2: float


@dataclass(frozen=True)
class CandidateRoot:
    omega: float
    rho: float
    rho_ratio: float
    re_abs: float
    method: str
    clean: bool
    candidate_count: int
    clean_count: int


@dataclass
class GroupResult:
    tp: float
    U: int
    eta: float
    omega: np.ndarray
    x_cent: np.ndarray
    k_path: list[tuple[int, int]]
    rho: np.ndarray  # shape: (k, omega)
    re_g: np.ndarray  # shape: (k, omega)
    roots: np.ndarray  # shape: (k,)
    root_rows: list[dict]
    fit: dict


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recompute Fig. 3/4 Luttinger-surface figures from raw Lanczos data."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/Gcalpath/Lanczos_raw_data"),
        help="Directory containing ML_MMHK-style *_Gh.dat and *_Gp.dat files.",
    )
    parser.add_argument(
        "--fig-dir",
        type=Path,
        default=Path("figures"),
        help="Directory for generated PDF/PNG figures.",
    )
    parser.add_argument(
        "--out-root",
        type=Path,
        default=Path("data/Gcalpath"),
        help="Root directory for eta-specific CSV/NPZ/JSON diagnostics.",
    )
    parser.add_argument(
        "--eta",
        type=float,
        nargs="*",
        default=[0.2, 0.1, 0.05],
        help="Broadening values to run.",
    )
    parser.add_argument(
        "--omega-max",
        type=float,
        default=24.0,
        help="Half-width of the omega grid. Default matches the current Fig. 3/4 U=40 map window.",
    )
    parser.add_argument(
        "--omega-points",
        type=int,
        default=4801,
        help="Omega-grid point count. Default keeps the previous 0.01 spacing over [-24, 24].",
    )
    parser.add_argument("--plot-omega-limit", type=float, default=10.0)
    parser.add_argument("--steps-max", type=int, default=1000)
    parser.add_argument("--coordination", type=int, default=4)
    parser.add_argument("--rho-clean-ratio", type=float, default=0.25)
    parser.add_argument(
        "--max-continuity-jump",
        type=float,
        default=2.0,
        help="Reject accepted root segments separated by larger nearest-neighbor jumps.",
    )
    parser.add_argument(
        "--min-continuous-segment",
        type=int,
        default=5,
        help="Reject short clean-root islands after continuity segmentation.",
    )
    parser.add_argument("--q", default="0,0")
    parser.add_argument(
        "--manual-root",
        type=Path,
        default=Path("/Users/cosdis/Desktop/projects/HK_orbital_cluster/Violation_Luttinger/spectral_function/half-filling/4x4"),
        help="Optional old notebook directory for eta=0.2 sanity comparisons.",
    )
    return parser.parse_args()


def eta_label(eta: float) -> str:
    return "eta" + f"{eta:g}".replace("-", "m").replace(".", "p")


def tp_label(tp: float) -> str:
    for value, label in TP_LABELS.items():
        if np.isclose(tp, value):
            return label
    return "tp" + f"{tp:g}".replace("-", "n").replace(".", "p")


def param_label(value: int | float) -> str:
    value_f = float(value)
    if value_f.is_integer():
        return str(int(value_f))
    return f"{value_f:g}"


def parse_q(text: str) -> tuple[int, int]:
    parts = text.split(",")
    if len(parts) != 2:
        raise ValueError(f"Expected Q as 'qx,qy', got {text!r}")
    return int(parts[0]), int(parts[1])


def default_k_path(nn: int = 40) -> list[tuple[int, int]]:
    return (
        [(i, 0) for i in range(0, nn)]
        + [(nn, i) for i in range(0, nn)]
        + [(i, i) for i in range(nn, -1, -1)]
    )


def unique_k_path(nn: int = 40) -> list[tuple[int, int]]:
    seen: set[tuple[int, int]] = set()
    out: list[tuple[int, int]] = []
    for item in default_k_path(nn):
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def x_centers(nn: int = 40) -> np.ndarray:
    x = np.zeros(3 * nn + 1, dtype=float)
    for idx in range(x.size):
        if idx < 2 * nn:
            x[idx] = idx + 1.0
        else:
            x[idx] = x[2 * nn - 1] + 1.0 + (idx - 2 * nn) * math.sqrt(2.0)
    return x


def centers_to_edges(centers: np.ndarray) -> np.ndarray:
    edges = np.empty(centers.size + 1, dtype=float)
    edges[1:-1] = 0.5 * (centers[:-1] + centers[1:])
    edges[0] = centers[0] - 0.5 * (centers[1] - centers[0])
    edges[-1] = centers[-1] + 0.5 * (centers[-1] - centers[-2])
    return edges


def parse_green_file(path: Path, q_target: tuple[int, int]) -> GreenComponent:
    metadata: dict[str, float | None] = {"U": None, "V": 0.0, "tp": 0.0, "E0": None}
    q_values: list[tuple[int, int]] = []
    nrm2_values: list[float] = []
    a_values: list[np.ndarray] = []
    b_values: list[np.ndarray] = []

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            parts = raw_line.split()
            if not parts:
                continue
            key = parts[0]
            if key == "U":
                metadata["U"] = float(parts[1])
            elif key == "V":
                metadata["V"] = float(parts[1])
            elif key == "tp":
                metadata["tp"] = float(parts[1])
            elif key == "E0":
                metadata["E0"] = float(parts[1])
            elif key == "Q":
                q_values.append(tuple(int(x) for x in parts[1].split(",")))
            elif key == "nrm2":
                nrm2_values.append(float(parts[1]))
            elif key == "a":
                a_values.append(np.array([float(x) for x in parts[1:]], dtype=np.float64))
            elif key == "b":
                b_values.append(np.array([float(x) for x in parts[1:]], dtype=np.float64))

    missing = [key for key in ("U", "E0") if metadata[key] is None]
    if missing:
        raise ValueError(f"Missing required metadata {missing} in {path}")
    if q_target not in q_values:
        raise ValueError(f"Q={q_target} not found in {path}")
    idx = q_values.index(q_target)
    kind = path.name.rsplit("_", 1)[1].replace(".dat", "")
    return GreenComponent(
        path=path,
        kind=kind,
        U=float(metadata["U"]),
        V=float(metadata["V"] or 0.0),
        tp=float(metadata["tp"] or 0.0),
        E0=float(metadata["E0"]),
        a=a_values[idx],
        b=b_values[idx],
        nrm2=nrm2_values[idx],
    )


def continued_fraction_values(
    component: GreenComponent,
    omega: np.ndarray,
    eta: float,
    steps_max: int,
    coordination: int,
) -> np.ndarray:
    if component.nrm2 <= 1.0e-12:
        return np.zeros_like(omega, dtype=np.complex128)

    length = min(steps_max, component.a.size, component.b.size)
    z = omega.astype(np.complex128) + 1j * eta
    mu_ph = component.U / 2.0 + coordination * component.V
    res = np.zeros_like(z)

    if component.kind == "Gh":
        constant = mu_ph - component.E0
        sign = 1.0
    elif component.kind == "Gp":
        constant = mu_ph + component.E0
        sign = -1.0
    else:
        raise ValueError(f"Unknown component kind {component.kind!r} for {component.path}")

    for j in range(length - 1, 0, -1):
        res = -(component.b[j] * component.b[j]) / (z + constant + sign * component.a[j] + res)
    denominator = z + constant + sign * component.a[0] + res
    return component.nrm2 * component.nrm2 / denominator


def validate_group(data_dir: Path, U: int, V: int, tp: float) -> dict:
    missing: list[str] = []
    for kx, ky in unique_k_path():
        for kind in ("Gh", "Gp"):
            path = data_dir / (
                f"L4x4Nup8Ndn8U{param_label(U)}V{param_label(V)}"
                f"tp{param_label(tp)}f{kx}x{ky}Q0x0_{kind}.dat"
            )
            if not path.exists():
                missing.append(str(path))
    return {
        "U": U,
        "V": V,
        "tp": tp,
        "expected_unique_pairs": 120,
        "expected_path_rows": 121,
        "missing_file_count": len(missing),
        "missing_files_sample": missing[:12],
        "complete": not missing,
    }


def sign_change_candidates(
    omega: np.ndarray,
    re_g: np.ndarray,
    rho: np.ndarray,
    plot_omega_limit: float,
    clean_ratio: float,
) -> list[CandidateRoot]:
    rho_pos = np.maximum(rho, 0.0)
    peak = max(float(np.nanmax(rho_pos)), 1.0e-14)
    candidates: list[CandidateRoot] = []

    for idx in range(omega.size - 1):
        w0 = float(omega[idx])
        w1 = float(omega[idx + 1])
        y0 = float(re_g[idx])
        y1 = float(re_g[idx + 1])
        if not (np.isfinite(y0) and np.isfinite(y1)):
            continue
        root: float | None = None
        if y0 == 0.0:
            root = w0
        elif y0 * y1 < 0.0:
            root = w0 - y0 * (w1 - w0) / (y1 - y0)
        if root is None or abs(root) > plot_omega_limit:
            continue
        rho_at_root = float(np.interp(root, omega, rho_pos))
        ratio = rho_at_root / peak
        candidates.append(
            CandidateRoot(
                omega=root,
                rho=rho_at_root,
                rho_ratio=ratio,
                re_abs=0.0,
                method="sign_change_linear",
                clean=ratio <= clean_ratio,
                candidate_count=0,
                clean_count=0,
            )
        )

    # De-duplicate exact-grid zeros that can appear in adjacent intervals.
    candidates.sort(key=lambda item: item.omega)
    deduped: list[CandidateRoot] = []
    for cand in candidates:
        if deduped and abs(cand.omega - deduped[-1].omega) < 0.5 * float(omega[1] - omega[0]):
            if cand.rho_ratio < deduped[-1].rho_ratio:
                deduped[-1] = cand
        else:
            deduped.append(cand)

    total = len(deduped)
    clean_count = sum(1 for item in deduped if item.clean)
    return [
        CandidateRoot(
            omega=item.omega,
            rho=item.rho,
            rho_ratio=item.rho_ratio,
            re_abs=item.re_abs,
            method=item.method,
            clean=item.clean,
            candidate_count=total,
            clean_count=clean_count,
        )
        for item in deduped
    ]


def fallback_candidate(
    omega: np.ndarray,
    re_g: np.ndarray,
    rho: np.ndarray,
    plot_omega_limit: float,
) -> CandidateRoot:
    mask = np.abs(omega) <= plot_omega_limit
    rho_pos = np.maximum(rho, 0.0)
    peak = max(float(np.nanmax(rho_pos)), 1.0e-14)
    idxs = np.nonzero(mask)[0]
    local_idx = idxs[np.nanargmin(np.abs(re_g[mask]))]
    rho_at = float(rho_pos[local_idx])
    return CandidateRoot(
        omega=float(omega[local_idx]),
        rho=rho_at,
        rho_ratio=rho_at / peak,
        re_abs=float(abs(re_g[local_idx])),
        method="fallback_min_abs_ReG",
        clean=False,
        candidate_count=0,
        clean_count=0,
    )


def choose_continuous_roots(
    omega: np.ndarray,
    rho: np.ndarray,
    re_g: np.ndarray,
    plot_omega_limit: float,
    clean_ratio: float,
    max_continuity_jump: float,
    min_continuous_segment: int,
) -> tuple[np.ndarray, list[dict]]:
    candidate_lists: list[list[CandidateRoot]] = []
    for k_idx in range(rho.shape[0]):
        candidates = sign_change_candidates(
            omega, re_g[k_idx], rho[k_idx], plot_omega_limit=plot_omega_limit, clean_ratio=clean_ratio
        )
        # Implement the planned "discard high-spectral-weight roots" rule
        # locally at each k.  High-weight roots are retained only when no
        # clean ReG sign-change exists for that momentum.
        clean_candidates = [cand for cand in candidates if cand.clean]
        if clean_candidates:
            candidates = clean_candidates
        if not candidates:
            candidates = [fallback_candidate(omega, re_g[k_idx], rho[k_idx], plot_omega_limit)]
        candidate_lists.append(candidates)

    # Dynamic program: keep the low-spectral-weight branch smooth along Gamma-X-M-Gamma.
    smooth_scale = 1.0
    costs: list[np.ndarray] = []
    parents: list[np.ndarray] = []
    for k_idx, candidates in enumerate(candidate_lists):
        base = np.array(
            [
                cand.rho_ratio
                + (0.0 if cand.clean else 2.0)
                + (0.2 if cand.method.startswith("fallback") else 0.0)
                + 0.002 * abs(cand.omega)
                for cand in candidates
            ],
            dtype=float,
        )
        if k_idx == 0:
            costs.append(base)
            parents.append(np.full(len(candidates), -1, dtype=int))
            continue
        prev_costs = costs[-1]
        prev_candidates = candidate_lists[k_idx - 1]
        step_costs = np.empty(len(candidates), dtype=float)
        step_parents = np.empty(len(candidates), dtype=int)
        for cand_idx, cand in enumerate(candidates):
            trans = np.array(
                [0.5 * ((cand.omega - prev.omega) / smooth_scale) ** 2 for prev in prev_candidates],
                dtype=float,
            )
            best_parent = int(np.argmin(prev_costs + trans))
            step_costs[cand_idx] = base[cand_idx] + prev_costs[best_parent] + trans[best_parent]
            step_parents[cand_idx] = best_parent
        costs.append(step_costs)
        parents.append(step_parents)

    chosen_indices = [0] * len(candidate_lists)
    chosen_indices[-1] = int(np.argmin(costs[-1]))
    for k_idx in range(len(candidate_lists) - 1, 0, -1):
        chosen_indices[k_idx - 1] = int(parents[k_idx][chosen_indices[k_idx]])

    roots = np.array(
        [candidate_lists[k_idx][chosen_indices[k_idx]].omega for k_idx in range(len(candidate_lists))], dtype=float
    )
    rows: list[dict] = []
    for k_idx, cand_idx in enumerate(chosen_indices):
        cand = candidate_lists[k_idx][cand_idx]
        status = "clean" if cand.clean and cand.method == "sign_change_linear" else cand.method
        if cand.method == "sign_change_linear" and not cand.clean:
            status = "high_spectral_weight"
        rows.append(
            {
                "omega_root": cand.omega,
                "rho_at_root": cand.rho,
                "rho_ratio_at_root": cand.rho_ratio,
                "abs_reG_at_root": cand.re_abs,
                "root_status": status,
                "candidate_roots": cand.candidate_count,
                "clean_candidate_roots": cand.clean_count,
                "candidate_omega_roots": ";".join(
                    f"{item.omega:.12g}" for item in candidate_lists[k_idx]
                ),
                "clean_candidate_omega_roots": ";".join(
                    f"{item.omega:.12g}" for item in candidate_lists[k_idx] if item.clean
                ),
                "chosen_candidate_index": cand_idx,
            }
        )
    return reject_unreliable_roots(
        roots,
        rows,
        max_continuity_jump=max_continuity_jump,
        min_continuous_segment=min_continuous_segment,
    )


def reject_unreliable_roots(
    roots: np.ndarray,
    rows: list[dict],
    max_continuity_jump: float,
    min_continuous_segment: int,
) -> tuple[np.ndarray, list[dict]]:
    """Reject roots that are not low-spectral-weight, continuous LS roots.

    The raw selected root is preserved in raw_omega_root/raw_rho_at_root; the
    public omega_root/rho_at_root fields are set to NaN for rejected rows.
    """
    raw_roots = roots.copy()
    accepted = np.array([row["root_status"] == "clean" for row in rows], dtype=bool)

    # Split clean roots into continuous segments.  Small clean islands bounded
    # by large jumps are usually pole-adjacent artifacts in the weak U=8 data.
    segments: list[tuple[int, int]] = []
    start: int | None = None
    prev: int | None = None
    for idx, ok in enumerate(accepted):
        if not ok:
            if start is not None and prev is not None:
                segments.append((start, prev))
            start = None
            prev = None
            continue
        if start is None:
            start = idx
            prev = idx
            continue
        assert prev is not None
        if abs(raw_roots[idx] - raw_roots[prev]) > max_continuity_jump:
            segments.append((start, prev))
            start = idx
        prev = idx
    if start is not None and prev is not None:
        segments.append((start, prev))

    for start, end in segments:
        if end - start + 1 < min_continuous_segment:
            accepted[start : end + 1] = False
            for idx in range(start, end + 1):
                rows[idx]["root_status"] = "discontinuous_short_segment_rejected"

    processed_roots = raw_roots.copy()
    for idx, row in enumerate(rows):
        row["raw_omega_root"] = row["omega_root"]
        row["raw_rho_at_root"] = row["rho_at_root"]
        row["raw_rho_ratio_at_root"] = row["rho_ratio_at_root"]
        if not accepted[idx]:
            if row["root_status"] in {"high_spectral_weight", "fallback_min_abs_ReG"}:
                row["root_status"] = "no_clean_low_weight_root"
            processed_roots[idx] = np.nan
            row["omega_root"] = np.nan
            row["rho_at_root"] = np.nan
            row["rho_ratio_at_root"] = np.nan
    return processed_roots, rows


def compute_group(
    data_dir: Path,
    U: int,
    tp: float,
    eta: float,
    omega: np.ndarray,
    q_target: tuple[int, int],
    steps_max: int,
    coordination: int,
    plot_omega_limit: float,
    clean_ratio: float,
    max_continuity_jump: float,
    min_continuous_segment: int,
) -> GroupResult:
    k_path = default_k_path()
    x_cent = x_centers()
    rho = np.zeros((len(k_path), omega.size), dtype=np.float64)
    re_g = np.zeros_like(rho)

    parse_cache: dict[Path, GreenComponent] = {}

    for k_idx, (kx, ky) in enumerate(k_path):
        components: list[np.ndarray] = []
        for kind in ("Gh", "Gp"):
            path = data_dir / (
                f"L4x4Nup8Ndn8U{param_label(U)}V0tp{param_label(tp)}"
                f"f{kx}x{ky}Q0x0_{kind}.dat"
            )
            if path not in parse_cache:
                parse_cache[path] = parse_green_file(path, q_target=q_target)
            components.append(
                continued_fraction_values(parse_cache[path], omega, eta, steps_max=steps_max, coordination=coordination)
            )
        g_total = components[0] + components[1]
        rho[k_idx, :] = -2.0 * g_total.imag
        re_g[k_idx, :] = -2.0 * g_total.real

    roots, root_rows = choose_continuous_roots(
        omega,
        rho,
        re_g,
        plot_omega_limit=plot_omega_limit,
        clean_ratio=clean_ratio,
        max_continuity_jump=max_continuity_jump,
        min_continuous_segment=min_continuous_segment,
    )
    fit = fit_noninteracting_reference(k_path, roots, tp)
    return GroupResult(
        tp=tp,
        U=U,
        eta=eta,
        omega=omega,
        x_cent=x_cent,
        k_path=k_path,
        rho=rho,
        re_g=re_g,
        roots=roots,
        root_rows=root_rows,
        fit=fit,
    )


def noninteracting_dispersion(k_path: Iterable[tuple[int, int]], tp: float, nn: int = 40) -> np.ndarray:
    delta = math.pi / nn
    values: list[float] = []
    for kx_i, ky_i in k_path:
        kx = kx_i * delta
        ky = ky_i * delta
        values.append(-2.0 * (math.cos(kx) + math.cos(ky)) - 4.0 * tp * math.cos(kx) * math.cos(ky))
    return np.array(values, dtype=float)


def fit_noninteracting_reference(k_path: list[tuple[int, int]], roots: np.ndarray, tp: float) -> dict:
    eps_fixed = noninteracting_dispersion(k_path, tp)
    mask = np.isfinite(roots) & np.isfinite(eps_fixed)
    A = np.column_stack([eps_fixed[mask], np.ones(np.count_nonzero(mask))])
    fixed_scale, fixed_offset = np.linalg.lstsq(A, roots[mask], rcond=None)[0]
    fixed_pred = fixed_scale * eps_fixed + fixed_offset
    fixed_residual = roots[mask] - fixed_pred[mask]

    k_arr = np.array(k_path, dtype=float)
    delta = math.pi / 40.0
    cos_kx = np.cos(k_arr[:, 0] * delta)
    cos_ky = np.cos(k_arr[:, 1] * delta)

    def model(xdata: tuple[np.ndarray, np.ndarray], scale: float, offset: float, teff: float) -> np.ndarray:
        cx, cy = xdata
        eps = -2.0 * (cx + cy) - 4.0 * teff * cx * cy
        return scale * eps + offset

    fitted_scale, fitted_offset, fitted_teff = curve_fit(
        model,
        (cos_kx[mask], cos_ky[mask]),
        roots[mask],
        p0=(fixed_scale, fixed_offset, tp),
        maxfev=10000,
    )[0]
    eps_fitted = -2.0 * (cos_kx + cos_ky) - 4.0 * fitted_teff * cos_kx * cos_ky
    pred = fitted_scale * eps_fitted + fitted_offset
    residual = roots[mask] - pred[mask]
    return {
        "scale": float(fitted_scale),
        "offset": float(fitted_offset),
        "teff": float(fitted_teff),
        "rmse": float(np.sqrt(np.mean(residual**2))),
        "max_abs_error": float(np.max(np.abs(residual))),
        "reference": pred,
        "epsilon0": eps_fitted,
        "fixed_tp": float(tp),
        "fixed_tp_scale": float(fixed_scale),
        "fixed_tp_offset": float(fixed_offset),
        "fixed_tp_rmse": float(np.sqrt(np.mean(fixed_residual**2))),
        "fixed_tp_max_abs_error": float(np.max(np.abs(fixed_residual))),
        "fixed_tp_reference": fixed_pred,
        "fixed_tp_epsilon0": eps_fixed,
    }


def write_group_csv(path: Path, result: GroupResult) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "tp",
            "U",
            "V",
            "eta",
            "k_index",
            "kx",
            "ky",
            "x_path",
            "omega_root",
            "rho_at_root",
            "rho_ratio_at_root",
            "raw_omega_root",
            "raw_rho_at_root",
            "raw_rho_ratio_at_root",
            "abs_reG_at_root",
            "root_status",
            "candidate_roots",
            "clean_candidate_roots",
            "candidate_omega_roots",
            "clean_candidate_omega_roots",
            "chosen_candidate_index",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for k_idx, ((kx, ky), x_path, row) in enumerate(zip(result.k_path, result.x_cent, result.root_rows)):
            writer.writerow(
                {
                    "tp": result.tp,
                    "U": result.U,
                    "V": 0,
                    "eta": result.eta,
                    "k_index": k_idx,
                    "kx": kx,
                    "ky": ky,
                    "x_path": x_path,
                    **row,
                }
            )


def write_combined_csv(path: Path, results: list[GroupResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "tp",
            "U",
            "V",
            "eta",
            "k_index",
            "kx",
            "ky",
            "x_path",
            "omega_root",
            "rho_at_root",
            "rho_ratio_at_root",
            "raw_omega_root",
            "raw_rho_at_root",
            "raw_rho_ratio_at_root",
            "abs_reG_at_root",
            "root_status",
            "candidate_roots",
            "clean_candidate_roots",
            "candidate_omega_roots",
            "clean_candidate_omega_roots",
            "chosen_candidate_index",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            for k_idx, ((kx, ky), x_path, row) in enumerate(zip(result.k_path, result.x_cent, result.root_rows)):
                writer.writerow(
                    {
                        "tp": result.tp,
                        "U": result.U,
                        "V": 0,
                        "eta": result.eta,
                        "k_index": k_idx,
                        "kx": kx,
                        "ky": ky,
                        "x_path": x_path,
                        **row,
                    }
                )


def save_npz(path: Path, results: list[GroupResult]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    roots = np.stack([result.roots for result in results])
    rho = np.stack([result.rho for result in results])
    re_g = np.stack([result.re_g for result in results])
    np.savez_compressed(
        path,
        omega=results[0].omega,
        x_path=results[0].x_cent,
        k_path=np.array(results[0].k_path, dtype=int),
        U=np.array([result.U for result in results], dtype=int),
        tp=np.array(results[0].tp, dtype=float),
        eta=np.array(results[0].eta, dtype=float),
        rho_G=rho,
        reG=re_g,
        omega_root=roots,
        fit_scale=np.array([result.fit["scale"] for result in results], dtype=float),
        fit_offset=np.array([result.fit["offset"] for result in results], dtype=float),
        fit_teff=np.array([result.fit["teff"] for result in results], dtype=float),
        fixed_tp_fit_scale=np.array([result.fit["fixed_tp_scale"] for result in results], dtype=float),
        fixed_tp_fit_offset=np.array([result.fit["fixed_tp_offset"] for result in results], dtype=float),
        fixed_tp_fit_rmse=np.array([result.fit["fixed_tp_rmse"] for result in results], dtype=float),
    )


def load_manual_curves(manual_root: Path, tp: float) -> dict[int, np.ndarray]:
    if np.isclose(tp, 0.0):
        nb_path = manual_root / "fitting_tp0U40.ipynb"
        names = {U: f"LStp0U{U}" for U in U_VALUES}
    elif np.isclose(tp, -0.25):
        nb_path = manual_root / "fitting_tpn25U40.ipynb"
        names = {U: f"LStpn25U{U}" for U in U_VALUES}
    else:
        return {}
    if not nb_path.exists():
        return {}
    try:
        data = json.loads(nb_path.read_text(encoding="utf-8"))
        source = "\n".join("".join(cell.get("source", [])) for cell in data.get("cells", []))
    except Exception:
        return {}

    curves: dict[int, np.ndarray] = {}
    for U, name in names.items():
        match = re.search(rf"{re.escape(name)}\s*=\s*np\.array\((\[.*?\])\)", source, flags=re.S)
        if not match:
            continue
        text = match.group(1).replace("\\\n", "\n")
        try:
            values = np.array(ast.literal_eval(text), dtype=float)
        except Exception:
            continue
        if values.size == 121:
            curves[U] = values
    return curves


def manual_comparison(results: list[GroupResult], manual_root: Path) -> dict:
    tp = results[0].tp
    manual = load_manual_curves(manual_root, tp)
    output: dict[str, dict] = {}
    for result in results:
        ref = manual.get(result.U)
        if ref is None:
            continue
        diff = result.roots - ref
        output[str(result.U)] = {
            "rmse": float(np.sqrt(np.nanmean(diff**2))),
            "max_abs": float(np.nanmax(np.abs(diff))),
            "mean_abs": float(np.nanmean(np.abs(diff))),
        }
    return output


def plot_figure(
    fig_path_pdf: Path,
    fig_path_png: Path,
    results: list[GroupResult],
    plot_omega_limit: float,
) -> None:
    """Render with the visual grammar of the existing manuscript Fig. 3/4."""
    fig_path_pdf.parent.mkdir(parents=True, exist_ok=True)
    tp = results[0].tp
    eta = results[0].eta
    x = results[0].x_cent
    x_edges = centers_to_edges(x)
    omega = results[0].omega
    panel_labels = ["(a)", "(b)", "(c)", "(d)", "(e)", "(f)"]
    map_ylims = {8: 8.0, 12: 10.0, 20: 15.0, 40: 24.0}
    line_colors = {8: "#1f77b4", 12: "#ff7f0e", 20: "#2ca02c", 40: "#d62728"}
    intensity_vmax = 1.5

    with plt.rc_context(
        {
            "font.family": "Arial",
            "font.size": 18,
            "axes.labelsize": 22,
            "xtick.labelsize": 20,
            "ytick.labelsize": 20,
            "legend.fontsize": 16,
            "axes.linewidth": 1.2,
        }
    ):
        fig = plt.figure(figsize=(10.05, 11.8), constrained_layout=False)
        gs = fig.add_gridspec(3, 2, height_ratios=[1.0, 1.0, 0.95], wspace=0.18, hspace=0.34)
        map_axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])]
        line_ax = fig.add_subplot(gs[2, 0])
        ref_ax = fig.add_subplot(gs[2, 1])
        fig.subplots_adjust(left=0.09, right=0.985, top=0.985, bottom=0.07)

        map_images = []
        for map_idx, (ax, result, panel) in enumerate(zip(map_axes, results, panel_labels[:4])):
            ylim = map_ylims.get(result.U, plot_omega_limit)
            omega_mask = np.abs(omega) <= ylim
            omega_plot = omega[omega_mask]
            omega_edges = centers_to_edges(omega_plot)
            z = np.maximum(result.rho[:, omega_mask], 0.0).T
            im = ax.pcolormesh(
                x_edges,
                omega_edges,
                z,
                shading="auto",
                cmap="rainbow",
                vmin=0.0,
                vmax=intensity_vmax,
            )
            map_images.append(im)
            ax.plot(x, result.roots, color="white", lw=1.8, solid_capstyle="round")
            ax.axhline(0.0, color="black", ls="--", lw=1.4)
            ax.axvline(x[40], color="black", ls="--", lw=1.4)
            ax.axvline(x[80], color="black", ls="--", lw=1.4)
            decorate_k_axis(ax, x)
            ax.set_ylim(-ylim, ylim)
            if map_idx in (0, 2):
                ax.set_ylabel(r"$\omega/t$")
            ax.text(
                -0.20,
                1.03,
                panel,
                transform=ax.transAxes,
                ha="left",
                va="top",
                color="black",
                fontsize=20,
            )
            ax.text(
                0.03,
                0.46,
                rf"$U={result.U}$",
                transform=ax.transAxes,
                ha="left",
                va="center",
                color="white",
                fontsize=18,
                fontstyle="italic",
            )

        # Match the current Fig. 3/4 look: one horizontal colorbar under each spectral column.
        for cax_source in (map_axes[2], map_axes[3]):
            cbar = fig.colorbar(map_images[-1], ax=cax_source, orientation="horizontal", fraction=0.08, pad=0.16)
            cbar.set_ticks([0.0, 0.4, 0.8, 1.2])
            cbar.ax.tick_params(labelsize=18, pad=2)

        y_abs_max = 0.0
        for result in results:
            line_ax.plot(
                x,
                result.roots,
                lw=2.8,
                color=line_colors.get(result.U),
                label=rf"$U={result.U}$" if result.U in (8, 12) else rf"${result.U}$",
            )
            if np.isfinite(result.roots).any():
                y_abs_max = max(y_abs_max, float(np.nanmax(np.abs(result.roots))))
        decorate_k_axis(line_ax, x)
        line_ax.set_ylabel(r"$\omega_{\mathrm{GZ}}(\mathbf{k})/t$")
        line_ax.grid(True, alpha=0.35)
        line_ax.legend(frameon=False, ncol=2, loc="upper center", bbox_to_anchor=(0.52, 0.98))
        line_ax.text(-0.20, 1.03, panel_labels[4], transform=line_ax.transAxes, ha="left", va="top", fontsize=20)

        u40 = next(result for result in results if result.U == 40)
        ref = u40.fit["reference"]
        ref_ax.plot(x, u40.roots, lw=2.8, color="#d62728", label=r"$U=40$")
        if abs(tp) < 1.0e-12:
            ref_label = rf"${u40.fit['scale']:.2g}*\varepsilon_{{0,\mathbf{{k}}}}(t'=0)$"
        else:
            ref_label = rf"${u40.fit['scale']:.2g}*\varepsilon_{{0,\mathbf{{k}}}}(t'_{{\rm eff}}={u40.fit['teff']:.2g})$"
        ref_ax.plot(x, ref, lw=2.8, color="black", ls=":", label=ref_label)
        decorate_k_axis(ref_ax, x)
        ref_ax.grid(True, alpha=0.35)
        ref_ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.53, 0.98))
        ref_ax.text(-0.20, 1.03, panel_labels[5], transform=ref_ax.transAxes, ha="left", va="top", fontsize=20)

        line_ylim = max(6.2, math.ceil(1.02 * y_abs_max))
        for ax in (line_ax, ref_ax):
            ax.set_ylim(-line_ylim, line_ylim)

        # No suptitle: current manuscript Fig. 3/4 are panel-only figures.
        fig.savefig(fig_path_pdf, bbox_inches="tight")
        fig.savefig(fig_path_png, dpi=220, bbox_inches="tight")
        plt.close(fig)

    for path in (fig_path_pdf, fig_path_png):
        if not path.exists() or path.stat().st_size <= 0:
            raise RuntimeError(f"Failed to render non-empty figure {path}")
    if fig_path_pdf.read_bytes()[:4] != b"%PDF":
        raise RuntimeError(f"Rendered PDF does not have a PDF header: {fig_path_pdf}")

def decorate_k_axis(ax: plt.Axes, x: np.ndarray) -> None:
    ax.set_xlim(x[0], x[-1])
    ax.set_xticks([x[0], x[40], x[80], x[120]])
    ax.set_xticklabels([r"$\Gamma$", "X", "M", r"$\Gamma$"])


def group_summary(result: GroupResult) -> dict:
    status_counts: dict[str, int] = {}
    for row in result.root_rows:
        status_counts[row["root_status"]] = status_counts.get(row["root_status"], 0) + 1
    ratios = np.array([row["rho_ratio_at_root"] for row in result.root_rows], dtype=float)
    candidate_counts = np.array([row["candidate_roots"] for row in result.root_rows], dtype=float)
    finite_roots = result.roots[np.isfinite(result.roots)]
    finite_jumps = []
    for left, right in zip(result.roots[:-1], result.roots[1:]):
        if np.isfinite(left) and np.isfinite(right):
            finite_jumps.append(abs(right - left))
    jumps = np.array(finite_jumps, dtype=float)
    return {
        "tp": result.tp,
        "U": result.U,
        "eta": result.eta,
        "accepted_root_count": int(finite_roots.size),
        "rejected_root_count": int(result.roots.size - finite_roots.size),
        "root_min": float(np.nanmin(result.roots)) if finite_roots.size else None,
        "root_max": float(np.nanmax(result.roots)) if finite_roots.size else None,
        "max_neighbor_jump": float(np.nanmax(jumps)) if jumps.size else None,
        "mean_rho_ratio_at_root": float(np.nanmean(ratios)) if np.isfinite(ratios).any() else None,
        "max_rho_ratio_at_root": float(np.nanmax(ratios)) if np.isfinite(ratios).any() else None,
        "mean_candidate_count": float(np.nanmean(candidate_counts)),
        "root_status_counts": status_counts,
        "u40_fit_scale": result.fit["scale"] if result.U == 40 else None,
        "u40_fit_offset": result.fit["offset"] if result.U == 40 else None,
        "u40_fit_teff": result.fit["teff"] if result.U == 40 else None,
        "u40_fit_rmse": result.fit["rmse"] if result.U == 40 else None,
        "u40_fixed_tp_fit_scale": result.fit["fixed_tp_scale"] if result.U == 40 else None,
        "u40_fixed_tp_fit_offset": result.fit["fixed_tp_offset"] if result.U == 40 else None,
        "u40_fixed_tp_fit_rmse": result.fit["fixed_tp_rmse"] if result.U == 40 else None,
    }


def main() -> None:
    args = parse_args()
    if args.omega_points < 3001:
        raise ValueError("Plan requires at least 3001 omega points; use --omega-points >= 3001.")

    data_dir = args.data_dir.resolve()
    fig_dir = args.fig_dir.resolve()
    out_root = args.out_root.resolve()
    q_target = parse_q(args.q)
    omega = np.linspace(-args.omega_max, args.omega_max, args.omega_points)

    validations = [validate_group(data_dir, U, 0, tp) for tp in TP_VALUES for U in U_VALUES]
    incomplete = [item for item in validations if not item["complete"]]
    if incomplete:
        raise FileNotFoundError(json.dumps({"incomplete_groups": incomplete}, indent=2))

    all_summaries: list[dict] = []
    rendered_files: list[str] = []

    for eta in args.eta:
        eta_dir = out_root / f"luttinger_surface_{eta_label(eta)}"
        eta_dir.mkdir(parents=True, exist_ok=True)

        for tp in TP_VALUES:
            print(f"Computing eta={eta:g}, tp={tp:g} ...", flush=True)
            results = [
                compute_group(
                    data_dir=data_dir,
                    U=U,
                    tp=tp,
                    eta=eta,
                    omega=omega,
                    q_target=q_target,
                    steps_max=args.steps_max,
                    coordination=args.coordination,
                    plot_omega_limit=args.plot_omega_limit,
                    clean_ratio=args.rho_clean_ratio,
                    max_continuity_jump=args.max_continuity_jump,
                    min_continuous_segment=args.min_continuous_segment,
                )
                for U in U_VALUES
            ]
            label = tp_label(tp)
            e_label = eta_label(eta)
            combined_csv = eta_dir / f"luttinger_{label}_{e_label}_curves.csv"
            write_combined_csv(combined_csv, results)
            for result in results:
                write_group_csv(eta_dir / f"luttinger_{label}_U{result.U}_{e_label}_curves.csv", result)
            npz_path = eta_dir / f"luttinger_{label}_{e_label}_spectra_and_roots.npz"
            save_npz(npz_path, results)

            pdf_path = fig_dir / f"luttinger_{label}_{e_label}.pdf"
            png_path = fig_dir / f"luttinger_{label}_{e_label}.png"
            plot_figure(pdf_path, png_path, results, plot_omega_limit=args.plot_omega_limit)
            rendered_files.extend([str(pdf_path), str(png_path)])

            comparison = manual_comparison(results, args.manual_root) if np.isclose(eta, 0.2) else {}
            summary = {
                "eta": eta,
                "tp": tp,
                "figure_pdf": str(pdf_path),
                "figure_png": str(png_path),
                "combined_csv": str(combined_csv),
                "npz": str(npz_path),
                "group_summaries": [group_summary(result) for result in results],
                "manual_eta0p2_comparison_if_available": comparison,
            }
            summary_path = eta_dir / f"luttinger_{label}_{e_label}_summary.json"
            summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
            all_summaries.append({**summary, "summary_json": str(summary_path)})

    global_summary = {
        "data_dir": str(data_dir),
        "fig_dir": str(fig_dir),
        "out_root": str(out_root),
        "etas": args.eta,
        "omega_max": args.omega_max,
        "omega_points": args.omega_points,
        "steps_max": args.steps_max,
        "q": args.q,
        "coordination": args.coordination,
        "rho_clean_ratio": args.rho_clean_ratio,
        "max_continuity_jump": args.max_continuity_jump,
        "min_continuous_segment": args.min_continuous_segment,
        "validations": validations,
        "outputs": all_summaries,
        "rendered_files": rendered_files,
    }
    global_path = out_root / "luttinger_surface_reproduction_summary.json"
    global_path.write_text(json.dumps(global_summary, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"summary": str(global_path), "rendered_files": rendered_files}, indent=2))


if __name__ == "__main__":
    main()
