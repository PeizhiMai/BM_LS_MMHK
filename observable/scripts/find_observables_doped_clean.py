#!/usr/bin/env python3
"""Standalone observable functions on merged _obs data.

Import in notebook and call `find_observables_at_density(...)`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
from typing import Iterable

import numpy as np

NUP_NDN_ARRAY = np.array(
    [[n, n] for n in range(1, 16)] + [[n, n + 1] for n in range(1, 15)],
    dtype=int,
)
NUP_NDN_ARRAY = NUP_NDN_ARRAY[np.argsort(NUP_NDN_ARRAY[:, 0] + NUP_NDN_ARRAY[:, 1], kind="stable")]


@lru_cache(maxsize=None)
def _read_lines(path: Path) -> list[str]:
    return path.read_text().splitlines()


@lru_cache(maxsize=None)
def _read_scalar(path: Path, key: str) -> float:
    value: float | None = None
    for raw in _read_lines(path):
        parts = raw.split()
        if parts and parts[0] == key:
            value = float(parts[1])
    if value is None:
        raise ValueError(f"Key '{key}' not found in {path}")
    return value


@lru_cache(maxsize=None)
def _q_block(qmins_file: Path, i: int, j: int) -> list[tuple[int, int]]:
    target = f"f{i:g}x{j:g}:"
    q_vals: list[tuple[int, int]] = []
    active = False

    for line in _read_lines(qmins_file):
        if active:
            if line.startswith("f"):
                break
            s = line.strip()
            if s.startswith("Q") and "=" in s:
                rhs = s.split("=", 1)[1].strip().strip("()")
                qx, qy = map(int, rhs.split(","))
                q_vals.append((qx, qy))
        if target in line:
            active = True

    return q_vals


@lru_cache(maxsize=None)
def _get_q_list(data_root: Path, u_dir: str, nup: int, ndn: int, ix: int, iy: int) -> list[tuple[int, int]]:
    if nup == 8 and ndn == 8:
        return [(0, 0)]
    qmins = data_root / u_dir / "Qmins_sym" / f"Nup{nup:g}Ndn{ndn:g}_Qmins_sym.dat"
    q_vals = _q_block(qmins, ix, iy)
    if not q_vals:
        raise ValueError(f"No Q values in {qmins} for f{ix}x{iy}")
    return q_vals


def _obs_file(data_root: Path, u_dir: str, nup: int, ndn: int, ix: int, iy: int, qx: int, qy: int) -> Path:
    q_path = (
        data_root
        / u_dir
        / f"Nup{nup:g}Ndn{ndn:g}"
        / f"L4x4Nup{nup:g}Ndn{ndn:g}f{ix:g}x{iy:g}Q{qx:g}x{qy:g}_obs.dat"
    )
    if q_path.exists():
        return q_path

    # Some datasets (for example tp0U12 at half-filling) omit the explicit Q tag.
    fallback = (
        data_root
        / u_dir
        / f"Nup{nup:g}Ndn{ndn:g}"
        / f"L4x4Nup{nup:g}Ndn{ndn:g}f{ix:g}x{iy:g}_obs.dat"
    )
    return fallback


def _read_e0_for_gce(data_root: Path, u_dir: str, nup: int, ndn: int, ix: int, iy: int) -> float:
    # Match notebook behavior: use first Q for GCE comparison.
    qx, qy = _get_q_list(data_root, u_dir, nup, ndn, ix, iy)[0]
    return _read_scalar(_obs_file(data_root, u_dir, nup, ndn, ix, iy, qx, qy), "E0")


def _avg_over_q(data_root: Path, u_dir: str, nup: int, ndn: int, ix: int, iy: int, key: str) -> float:
    vals = []
    for qx, qy in _get_q_list(data_root, u_dir, nup, ndn, ix, iy):
        vals.append(_read_scalar(_obs_file(data_root, u_dir, nup, ndn, ix, iy, qx, qy), key))
    return float(np.mean(vals))


def _iter_unique(nx: int, ny: int, div: int) -> Iterable[tuple[int, int]]:
    for ix in range(0, nx, div):
        for iy in range(0, ny, div):
            if ix <= iy:
                yield ix, iy


def _u_from_dir(u_dir: str) -> float:
    match = re.search(r"U([-+]?\d*\.?\d+)", u_dir)
    if match is None:
        raise ValueError(f"Could not parse U from u_dir='{u_dir}'")
    return float(match.group(1))


def find_ave_n_E(mu: float, div: int, data_root: Path, u_dir: str) -> tuple[float, np.ndarray, float]:
    nx = 40
    ny = nx
    gce = np.zeros(NUP_NDN_ARRAY.shape[0], dtype=float)
    e0_only = np.zeros(NUP_NDN_ARRAY.shape[0], dtype=float)
    num_dist = np.zeros((nx // div, ny // div), dtype=float)
    e0_dist = np.zeros((nx // div, ny // div), dtype=float)

    for ix in range(0, nx, div):
        for iy in range(0, ny, div):
            if ix > iy:
                continue

            for ii, (nup, ndn) in enumerate(NUP_NDN_ARRAY):
                e0 = _read_e0_for_gce(data_root, u_dir, int(nup), int(ndn), ix, iy)
                gce[ii] = e0 - mu * (nup + ndn)
                e0_only[ii] = e0

            best = int(np.argmin(gce))
            iix = ix // div
            iiy = iy // div
            e0_dist[iix, iiy] = e0_only[best]
            num_dist[iix, iiy] = NUP_NDN_ARRAY[best, 0] + NUP_NDN_ARRAY[best, 1]
            e0_dist[iiy, iix] = e0_dist[iix, iiy]
            num_dist[iiy, iix] = num_dist[iix, iiy]

    n_den = float(np.mean(num_dist) / 16)
    e0_avg = float(np.mean(e0_dist) / 16)
    return n_den, num_dist, e0_avg


def find_mu_for_density(
    target_density: float,
    div: int,
    data_root: Path,
    u_dir: str,
    mu_low: float = -20.0,
    mu_high: float = 20.0,
    mu_tol: float = 2e-4,
    max_iter: int = 200,
) -> tuple[float, float]:
    if mu_low >= mu_high:
        raise ValueError("mu_low must be smaller than mu_high")

    d_low, _, _ = find_ave_n_E(mu_low, div, data_root, u_dir)
    d_high, _, _ = find_ave_n_E(mu_high, div, data_root, u_dir)
    increasing = d_high > d_low

    def _between(x: float, a: float, b: float) -> bool:
        return (a <= x <= b) or (b <= x <= a)

    if not _between(target_density, d_low, d_high):
        raise ValueError(
            "Target density is outside bracket: "
            f"target={target_density}, density(mu_low)={d_low}, density(mu_high)={d_high}."
        )

    left = mu_low
    right = mu_high

    for _ in range(max_iter):
        mid = 0.5 * (left + right)
        d_mid, _, _ = find_ave_n_E(mid, div, data_root, u_dir)

        if abs(right - left) <= mu_tol:
            return mid, d_mid

        if increasing:
            if d_mid < target_density:
                left = mid
            else:
                right = mid
        else:
            if d_mid > target_density:
                left = mid
            else:
                right = mid

        if abs(d_mid - target_density) < 1e-12:
            return mid, d_mid

    mu_star = 0.5 * (left + right)
    d_star, _, _ = find_ave_n_E(mu_star, div, data_root, u_dir)
    return mu_star, d_star


def _compute_sp_doi_doq(mu: float, div: int, data_root: Path, u_dir: str) -> tuple[float, float, float]:
    nx = 40
    ny = nx
    gce = np.zeros(NUP_NDN_ARRAY.shape[0], dtype=float)
    fs_sp = np.zeros((nx // div, ny // div), dtype=float)
    fs_doi = np.zeros((nx // div, ny // div), dtype=float)
    fs_doq = np.zeros((nx // div, ny // div), dtype=float)

    for ix, iy in _iter_unique(nx, ny, div):
        for ii, (nup, ndn) in enumerate(NUP_NDN_ARRAY):
            e0 = _read_e0_for_gce(data_root, u_dir, int(nup), int(ndn), ix, iy)
            gce[ii] = e0 - mu * (nup + ndn)

        best = int(np.argmin(gce))
        nupf, ndnf = map(int, NUP_NDN_ARRAY[best])
        iix = ix // div
        iiy = iy // div

        fs_sp[iix, iiy] = _avg_over_q(data_root, u_dir, nupf, ndnf, ix, iy, "<Spipi>")
        fs_doi[iix, iiy] = _avg_over_q(data_root, u_dir, nupf, ndnf, ix, iy, "<ni_upni_dn>")
        fs_doq[iix, iiy] = _avg_over_q(data_root, u_dir, nupf, ndnf, ix, iy, "<nq_upnq_dn>")

        fs_sp[iiy, iix] = fs_sp[iix, iiy]
        fs_doi[iiy, iix] = fs_doi[iix, iiy]
        fs_doq[iiy, iix] = fs_doq[iix, iiy]

    sp = float(np.sqrt(np.mean(fs_sp) / 16))
    doi = float(np.mean(fs_doi))
    doq = float(np.mean(fs_doq))
    return sp, doi, doq


def find_observables_at_density(
    target_density: float,
    div: int,
    data_root: Path,
    u_dir: str,
    mu_low: float = -20.0,
    mu_high: float = 20.0,
    mu_tol: float = 2e-4,
    max_iter: int = 200,
) -> tuple[float, float, float, float, float, float]:
    if np.isclose(target_density, 1.0):
        mu_star = 0.5 * _u_from_dir(u_dir)
        density_star, _, _ = find_ave_n_E(mu_star, div, data_root, u_dir)
    else:
        mu_star, density_star = find_mu_for_density(
            target_density=target_density,
            div=div,
            data_root=data_root,
            u_dir=u_dir,
            mu_low=mu_low,
            mu_high=mu_high,
            mu_tol=mu_tol,
            max_iter=max_iter,
        )
    _, _, e0_avg = find_ave_n_E(mu_star, div, data_root, u_dir)
    sp, doi, doq = _compute_sp_doi_doq(mu_star, div, data_root, u_dir)
    return mu_star, density_star, e0_avg, sp, doi, doq
