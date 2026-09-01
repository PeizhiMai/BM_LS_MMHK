#!/usr/bin/env python3
"""Create the strict all-F861 Fig. 4 :math:`C_{NN}` publication bundle.

The immutable expansion snapshot contains twelve complete 861-coordinate
wedge grids: 10,032 complement calculations plus the exact 300 hash-pinned
pilot outputs.  This staging-only analyzer independently verifies the two
manifests, raw-byte ledger, full wedges, observable identities, quadrature,
and the remote/local snapshot summaries.  It then joins four separately
hash-pinned U=40 F861 controls and evaluates signed Eq. (10) at the exact 16
Mott-side GZ points.

No manuscript, active figure, or published result file is modified.  The old
25-point analyzer remains available solely for the expansion decision audit.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from fig4_cnn_prediction_input import (
    C_NN_OBSERVABLE,
    DATA_PRODUCT,
    DECISION_GATE_ALGORITHM,
    EXPECTED_CONTROL_CASES,
    EXPECTED_EXPANSION_CASES,
    EXPECTED_POINTWISE_CASES,
    FULL861_CONTROL_SOURCE,
    FULL861_EXPANSION_SOURCE,
    FULL861_FIDELITY,
    FULL861_SAMPLING,
    POINTWISE_BASENAME,
    PROVENANCE_BASENAME,
    REVIEWED_FULL861_PINS,
    SCHEMA_VERSION,
    validate_immutable_snapshot_tree,
)


ROOT = Path(__file__).resolve().parents[1]
NSITES = 16.0
EXPECTED_EXPANSION = 10_032
EXPECTED_REUSED = 300
EXPECTED_COMBINED = 10_332
EXPECTED_EXPANSION_PER_CASE = 836
EXPECTED_FULL_PER_CASE = 861
EXPECTED_QUADRATURE_WEIGHT = 1600.0
IDENTITY_TOLERANCE = 1.0e-8

FULL_WEDGE = tuple((kx, ky) for ky in range(41) for kx in range(ky + 1))
FULL_WEDGE_SET = set(FULL_WEDGE)
PILOT_TWISTS = (
    (3, 3),
    (7, 7),
    (2, 8),
    (10, 12),
    (1, 14),
    (6, 16),
    (17, 17),
    (9, 21),
    (1, 23),
    (15, 23),
    (20, 25),
    (25, 25),
    (6, 26),
    (12, 29),
    (17, 29),
    (22, 30),
    (27, 30),
    (4, 32),
    (19, 34),
    (34, 34),
    (28, 35),
    (10, 36),
    (4, 38),
    (38, 38),
    (33, 39),
)
PILOT_TWIST_SET = set(PILOT_TWISTS)
COMPLEMENT_SET = FULL_WEDGE_SET - PILOT_TWIST_SET

COMPLETE_RE = re.compile(r"(?m)^status\s+COMPLETE\s*$")
FILENAME_RE = re.compile(
    r"^L4x4Nup8Ndn8U(?P<U>[^V]+)V(?P<V>[^t]+)tp(?P<tp>[^f]+)"
    r"f(?P<kx>\d+)x(?P<ky>\d+)Q(?P<Qm>-?\d+)x(?P<Qn>-?\d+)_obs\.dat$"
)
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_RAW_KEYS = {
    "Lx",
    "Ly",
    "tp",
    "U",
    "V",
    "E0",
    "Gap",
    "<nn_NN>",
    "<delta_n_delta_n_NN>",
    "<Kinetic_NN_per_site>",
    "<Kinetic_NNN_per_site>",
    "<Kinetic_per_site>",
    "<C1_NN>",
    "Q",
    "<nq>",
    "<nq_upnq_dn>",
    "<ni_upni_dn>",
    "<Spipi>",
    "<Sc_pipi>",
    "<mCDW2_pipi>",
    "status",
}

OUTPUT_BASENAMES = {
    "raw": "fig4_cnn_full861_campaign_raw_validation.csv",
    "campaign": "fig4_cnn_full861_campaign_summary.csv",
    "controls": "fig4_cnn_full861_u40_control_summary.csv",
    "pointwise": POINTWISE_BASENAME,
    "families": "fig4_cnn_pointwise_family_summary.csv",
    "provenance": PROVENANCE_BASENAME,
}


class ValidationError(RuntimeError):
    """Raised when an input violates the all-F861 publication contract."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot-root",
        type=Path,
        required=True,
        help="Immutable fullobs_861twist_fig4_cnn_20260821 snapshot.",
    )
    parser.add_argument(
        "--u40-summary",
        type=Path,
        default=ROOT
        / "results"
        / "fullobs_U40_observable_summary_by_V_20260723_091307.csv",
    )
    parser.add_argument(
        "--u40-rows",
        type=Path,
        default=ROOT / "results" / "fullobs_U40_observable_rows_20260723_091307.csv.gz",
    )
    parser.add_argument(
        "--gz-points",
        type=Path,
        default=ROOT / "results" / "pnas_scale_rule_points_eta0p05.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Fresh staging directory; analyzer outputs are never overwritten.",
    )
    parser.add_argument(
        "--identity-tolerance",
        type=float,
        default=IDENTITY_TOLERANCE,
        help="Must remain exactly 1e-8 for a publishable bundle.",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise ValidationError(f"Missing {label}: {path}")
    return path


def require_hash(path: Path, expected: str, label: str) -> Path:
    require_file(path, label)
    actual = sha256(path)
    if actual != expected:
        raise ValidationError(
            f"{label} SHA-256 mismatch: expected {expected}, got {actual}"
        )
    return path


def canonical_case(U: object, V: object) -> tuple[float, float]:
    return round(float(U), 10), round(float(V), 10)


def validate_output_destination(output_dir: Path) -> None:
    resolved = output_dir.expanduser().resolve()
    for protected in (ROOT / "manuscript", ROOT / "figures", ROOT / "results"):
        try:
            resolved.relative_to(protected.resolve())
        except ValueError:
            continue
        raise ValidationError(
            f"Refusing to write staging analysis inside publication tree: {protected}"
        )
    collisions = [
        resolved / basename
        for basename in OUTPUT_BASENAMES.values()
        if (resolved / basename).exists()
    ]
    if collisions:
        raise ValidationError(
            "Analyzer output already exists; choose a fresh staging directory: "
            + ", ".join(str(path) for path in collisions)
        )


def numeric_frame(frame: pd.DataFrame, columns: Iterable[str], label: str) -> None:
    for column in columns:
        try:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"Non-numeric {column} in {label}") from exc


def expected_filename(U: object, V: object, kx: object, ky: object) -> str:
    def tag(value: object) -> str:
        number = float(value)
        return str(int(number)) if number.is_integer() else format(number, "g")

    return (
        f"L4x4Nup8Ndn8U{tag(U)}V{tag(V)}tp0"
        f"f{int(kx)}x{int(ky)}Q0x0_obs.dat"
    )


def validate_result_name(row: pd.Series | object, label: str) -> str:
    name = Path(str(getattr(row, "result"))).name
    match = FILENAME_RE.fullmatch(name)
    if not match:
        raise ValidationError(f"Malformed result filename in {label}: {name}")
    values = match.groupdict()
    if (
        canonical_case(values["U"], values["V"])
        != canonical_case(getattr(row, "U"), getattr(row, "V"))
        or float(values["tp"]) != 0.0
        or int(values["kx"]) != int(getattr(row, "kx"))
        or int(values["ky"]) != int(getattr(row, "ky"))
        or int(values["Qm"]) != 0
        or int(values["Qn"]) != 0
        or name
        != expected_filename(
            getattr(row, "U"),
            getattr(row, "V"),
            getattr(row, "kx"),
            getattr(row, "ky"),
        )
    ):
        raise ValidationError(f"Result filename/manifest mismatch in {label}: {name}")
    return name


def load_expansion_manifest(path: Path) -> pd.DataFrame:
    require_hash(
        path,
        REVIEWED_FULL861_PINS["expansion_manifest_sha256"],
        "expansion manifest",
    )
    frame = pd.read_csv(path, sep="\t")
    required = {
        "index",
        "U",
        "V",
        "V_over_U",
        "expected_phase",
        "complement_index",
        "wedge_index",
        "kx",
        "ky",
        "symmetry_multiplicity",
        "endpoint_weight",
        "quadrature_weight",
        "seed",
        "job_name",
        "result",
    }
    if not required.issubset(frame.columns):
        raise ValidationError(
            f"Expansion manifest is missing columns: {sorted(required - set(frame.columns))}"
        )
    if len(frame) != EXPECTED_EXPANSION:
        raise ValidationError(
            f"Expansion manifest must contain 10,032 rows, found {len(frame)}"
        )
    numeric_frame(
        frame,
        (
            "index",
            "U",
            "V",
            "V_over_U",
            "complement_index",
            "wedge_index",
            "kx",
            "ky",
            "symmetry_multiplicity",
            "endpoint_weight",
            "quadrature_weight",
            "seed",
        ),
        "expansion manifest",
    )
    if set(frame["index"].astype(int)) != set(range(1, EXPECTED_EXPANSION + 1)):
        raise ValidationError("Expansion manifest indices are not the exact integers 1..10032")
    if frame["index"].duplicated().any() or frame["seed"].duplicated().any():
        raise ValidationError("Expansion manifest indices/seeds are not unique")
    if frame["result"].duplicated().any():
        raise ValidationError("Expansion manifest result paths are not unique")
    if not frame["expected_phase"].astype(str).eq("Mott").all():
        raise ValidationError("Expansion manifest contains a non-Mott target")
    if not frame["job_name"].astype(str).eq("F4CNN861X").all():
        raise ValidationError("Expansion manifest has an unexpected job name")
    if not np.allclose(frame["V_over_U"], frame["V"] / frame["U"], atol=1e-13, rtol=0):
        raise ValidationError("Expansion V_over_U values are inconsistent")
    cases = {canonical_case(row.U, row.V) for row in frame.itertuples(index=False)}
    if cases != set(EXPECTED_EXPANSION_CASES):
        raise ValidationError("Expansion case inventory differs from the reviewed 12 cases")

    for (U, V), group in frame.groupby(["U", "V"], sort=True):
        coordinates = set(zip(group["kx"].astype(int), group["ky"].astype(int)))
        if len(group) != EXPECTED_EXPANSION_PER_CASE or coordinates != COMPLEMENT_SET:
            raise ValidationError(
                f"Expansion complement is not the exact 836 coordinates at U={U:g}, V={V:g}"
            )
        if set(group["complement_index"].astype(int)) != set(range(1, 837)):
            raise ValidationError(f"Complement indices are not 1..836 at U={U:g}, V={V:g}")
    for row in frame.itertuples(index=False):
        symmetry = 1.0 if int(row.kx) == int(row.ky) else 2.0
        endpoint = (0.5 if int(row.kx) in (0, 40) else 1.0) * (
            0.5 if int(row.ky) in (0, 40) else 1.0
        )
        if not (
            float(row.symmetry_multiplicity) == symmetry
            and float(row.endpoint_weight) == endpoint
            and float(row.quadrature_weight) == symmetry * endpoint
        ):
            raise ValidationError("Expansion manifest quadrature metadata is inconsistent")
        validate_result_name(row, "expansion manifest")
    return frame.sort_values("index").reset_index(drop=True)


def load_source_and_reused(
    source_path: Path, reused_path: Path
) -> tuple[pd.DataFrame, pd.DataFrame]:
    require_hash(
        source_path,
        REVIEWED_FULL861_PINS["source_25_manifest_sha256"],
        "reviewed source-25 manifest",
    )
    source = pd.read_csv(source_path, sep="\t")
    reused = pd.read_csv(require_file(reused_path, "reused-25 manifest"), sep="\t")
    source_required = {
        "index",
        "U",
        "V",
        "V_over_U",
        "expected_phase",
        "twist_index",
        "kx",
        "ky",
        "seed",
        "result",
    }
    reused_required = {
        "source_index",
        "U",
        "V",
        "V_over_U",
        "expected_phase",
        "source_twist_index",
        "kx",
        "ky",
        "seed",
        "result",
        "size_bytes",
        "sha256",
        "state",
    }
    if not source_required.issubset(source.columns):
        raise ValidationError("Reviewed source-25 manifest lacks required columns")
    if not reused_required.issubset(reused.columns):
        raise ValidationError("Reused-25 manifest lacks required columns")
    if len(source) != EXPECTED_REUSED or len(reused) != EXPECTED_REUSED:
        raise ValidationError("Source and reused manifests must each contain exactly 300 rows")
    numeric_frame(
        source,
        ("index", "U", "V", "V_over_U", "twist_index", "kx", "ky", "seed"),
        "source-25 manifest",
    )
    numeric_frame(
        reused,
        (
            "source_index",
            "U",
            "V",
            "V_over_U",
            "source_twist_index",
            "kx",
            "ky",
            "seed",
            "size_bytes",
        ),
        "reused-25 manifest",
    )
    if (
        source["index"].duplicated().any()
        or reused["source_index"].duplicated().any()
        or source["seed"].duplicated().any()
        or reused["seed"].duplicated().any()
    ):
        raise ValidationError("Source/reused manifest index or seed collision")
    if not reused["sha256"].astype(str).map(lambda value: bool(HEX64_RE.fullmatch(value))).all():
        raise ValidationError("Reused-25 manifest has a malformed raw SHA-256")
    if not reused["state"].astype(str).eq("reused_complete_25").all():
        raise ValidationError("Reused-25 manifest has an unexpected state")

    left = source.sort_values("index").reset_index(drop=True)
    right = reused.sort_values("source_index").reset_index(drop=True)
    comparisons = (
        ("index", "source_index"),
        ("U", "U"),
        ("V", "V"),
        ("V_over_U", "V_over_U"),
        ("expected_phase", "expected_phase"),
        ("twist_index", "source_twist_index"),
        ("kx", "kx"),
        ("ky", "ky"),
        ("seed", "seed"),
        ("result", "result"),
    )
    for source_column, reused_column in comparisons:
        if source_column in {"expected_phase", "result"}:
            equal = left[source_column].astype(str).equals(right[reused_column].astype(str))
        else:
            equal = np.allclose(
                left[source_column].to_numpy(dtype=float),
                right[reused_column].to_numpy(dtype=float),
                atol=0.0,
                rtol=0.0,
            )
        if not equal:
            raise ValidationError(
                f"Reused-25 manifest differs from reviewed source column {source_column}"
            )
    for (U, V), group in source.groupby(["U", "V"], sort=True):
        coordinates = set(zip(group["kx"].astype(int), group["ky"].astype(int)))
        if len(group) != 25 or coordinates != PILOT_TWIST_SET:
            raise ValidationError(f"Source pilot panel mismatch at U={U:g}, V={V:g}")
    for row in source.itertuples(index=False):
        validate_result_name(row, "source-25 manifest")
    return left, right


def combined_manifest(expansion: pd.DataFrame, reused: pd.DataFrame) -> pd.DataFrame:
    expansion_rows = expansion[
        ["U", "V", "kx", "ky", "seed", "result"]
    ].copy()
    expansion_rows["source_campaign"] = "expansion_complement_836"
    expansion_rows["source_index"] = expansion["index"].astype(int)
    expansion_rows["expected_size_bytes"] = np.nan
    expansion_rows["expected_reused_sha256"] = ""

    reused_rows = reused[["U", "V", "kx", "ky", "seed", "result"]].copy()
    reused_rows["source_campaign"] = "reused_pilot_25"
    reused_rows["source_index"] = reused["source_index"].astype(int)
    reused_rows["expected_size_bytes"] = reused["size_bytes"].astype(int)
    reused_rows["expected_reused_sha256"] = reused["sha256"].astype(str)
    combined = pd.concat([expansion_rows, reused_rows], ignore_index=True)
    combined.insert(0, "global_index", np.arange(1, len(combined) + 1))
    combined["filename"] = [
        validate_result_name(row, "combined manifest")
        for row in combined.itertuples(index=False)
    ]
    if len(combined) != EXPECTED_COMBINED:
        raise ValidationError("Combined manifest is not exactly 10,332 rows")
    if combined.duplicated(["U", "V", "kx", "ky"]).any():
        raise ValidationError("Expansion and reused coordinate sets overlap")
    if combined["filename"].duplicated().any() or combined["seed"].duplicated().any():
        raise ValidationError("Combined filename/seed inventory is not unique")
    for (U, V), group in combined.groupby(["U", "V"], sort=True):
        coordinates = set(zip(group["kx"].astype(int), group["ky"].astype(int)))
        if len(group) != EXPECTED_FULL_PER_CASE or coordinates != FULL_WEDGE_SET:
            raise ValidationError(
                f"Combined inventory is not an exact 861-coordinate wedge at U={U:g}, V={V:g}"
            )
        counts = group["source_campaign"].value_counts().to_dict()
        if counts != {"expansion_complement_836": 836, "reused_pilot_25": 25}:
            raise ValidationError(f"Wrong expansion/reuse split at U={U:g}, V={V:g}")
    return combined


def load_raw_ledger(path: Path, combined: pd.DataFrame) -> pd.DataFrame:
    ledger = pd.read_csv(require_file(path, "remote raw SHA-256 ledger"), sep="\t")
    required = {"index", "U", "V", "kx", "ky", "filename", "size_bytes", "sha256"}
    if not required.issubset(ledger.columns):
        raise ValidationError("Remote raw SHA-256 ledger lacks required columns")
    if len(ledger) != EXPECTED_COMBINED:
        raise ValidationError("Remote raw SHA-256 ledger must have 10,332 rows")
    numeric_frame(ledger, ("index", "U", "V", "kx", "ky", "size_bytes"), "raw ledger")
    if ledger["index"].duplicated().any() or ledger["filename"].duplicated().any():
        raise ValidationError("Remote raw SHA-256 ledger contains duplicate rows")
    if not ledger["sha256"].astype(str).map(lambda value: bool(HEX64_RE.fullmatch(value))).all():
        raise ValidationError("Remote raw SHA-256 ledger contains malformed hashes")
    expected = combined.sort_values("global_index").reset_index(drop=True)
    observed = ledger.sort_values("index").reset_index(drop=True)
    for column, expected_column in (
        ("index", "global_index"),
        ("U", "U"),
        ("V", "V"),
        ("kx", "kx"),
        ("ky", "ky"),
    ):
        if not np.allclose(
            observed[column].to_numpy(dtype=float),
            expected[expected_column].to_numpy(dtype=float),
            atol=0,
            rtol=0,
        ):
            raise ValidationError(f"Raw ledger {column} does not match combined manifest")
    if not observed["filename"].astype(str).equals(expected["filename"].astype(str)):
        raise ValidationError("Raw ledger filenames do not match combined manifest")
    return observed


def index_raw_files(raw_dir: Path, expected_names: Iterable[str]) -> dict[str, Path]:
    if not raw_dir.is_dir():
        raise ValidationError(f"Missing raw directory: {raw_dir}")
    expected = set(expected_names)
    found: dict[str, Path] = {}
    unexpected: list[str] = []
    for path in raw_dir.rglob("*_obs.dat"):
        if path.name not in expected:
            unexpected.append(str(path.relative_to(raw_dir)))
        elif path.name in found:
            raise ValidationError(f"Duplicate raw basename: {path.name}")
        else:
            found[path.name] = path
    if unexpected:
        raise ValidationError(
            f"Raw directory contains {len(unexpected)} unexpected outputs; first={sorted(unexpected)[:3]}"
        )
    missing = sorted(expected - set(found))
    if missing:
        raise ValidationError(f"Missing {len(missing)} of 10,332 raw outputs; first={missing[:3]}")
    return found


def parse_values(path: Path) -> dict[str, str]:
    text = path.read_text(errors="replace")
    if not COMPLETE_RE.search(text):
        raise ValidationError(f"Raw output lacks COMPLETE marker: {path.name}")
    values: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2:
            values[parts[0]] = parts[1].strip()
    missing = sorted(REQUIRED_RAW_KEYS - set(values))
    if missing:
        raise ValidationError(f"Raw output {path.name} is missing fields: {missing}")
    return values


def numeric(values: dict[str, str], key: str, path: Path) -> float:
    try:
        value = float(values[key])
    except (KeyError, ValueError) as exc:
        raise ValidationError(f"Non-numeric {key} in {path.name}") from exc
    if not math.isfinite(value):
        raise ValidationError(f"Non-finite {key} in {path.name}")
    return value


def parse_and_validate_raw(
    combined: pd.DataFrame,
    ledger: pd.DataFrame,
    raw_dir: Path,
    identity_tolerance: float,
) -> pd.DataFrame:
    indexed = index_raw_files(raw_dir, combined["filename"].astype(str))
    ledger_by_name = ledger.set_index("filename")
    parsed: list[dict[str, object]] = []
    for row in combined.itertuples(index=False):
        path = indexed[str(row.filename)]
        expected = ledger_by_name.loc[str(row.filename)]
        actual_size = path.stat().st_size
        actual_hash = sha256(path)
        if actual_size != int(expected["size_bytes"]) or actual_hash != str(expected["sha256"]):
            raise ValidationError(f"Raw bytes disagree with remote ledger: {row.filename}")
        if row.source_campaign == "reused_pilot_25" and (
            actual_size != int(row.expected_size_bytes)
            or actual_hash != str(row.expected_reused_sha256)
        ):
            raise ValidationError(f"Reused pilot raw bytes are not hash-pinned: {row.filename}")
        values = parse_values(path)
        U, V = float(row.U), float(row.V)
        if (
            numeric(values, "Lx", path) != 4.0
            or numeric(values, "Ly", path) != 4.0
            or numeric(values, "tp", path) != 0.0
            or not math.isclose(numeric(values, "U", path), U, abs_tol=1e-12, rel_tol=0)
            or not math.isclose(numeric(values, "V", path), V, abs_tol=1e-12, rel_tol=0)
            or values["Q"].replace(" ", "") != "0,0"
            or values["status"].strip() != "COMPLETE"
        ):
            raise ValidationError(f"Raw body metadata mismatch: {row.filename}")

        E0 = numeric(values, "E0", path)
        gap = numeric(values, "Gap", path)
        nn = numeric(values, "<nn_NN>", path)
        delta_nn = numeric(values, "<delta_n_delta_n_NN>", path)
        kinetic_nn = numeric(values, "<Kinetic_NN_per_site>", path)
        kinetic_nnn = numeric(values, "<Kinetic_NNN_per_site>", path)
        kinetic = numeric(values, "<Kinetic_per_site>", path)
        C = numeric(values, "<C1_NN>", path)
        D = numeric(values, "<ni_upni_dn>", path)
        Sc = numeric(values, "<Sc_pipi>", path)
        mcdw = numeric(values, "<mCDW2_pipi>", path)
        residuals = {
            "energy_identity_residual": E0 / NSITES - (kinetic + U * D + 2.0 * V * nn),
            "connected_density_identity_residual": delta_nn - (nn - 1.0),
            "kinetic_identity_residual": kinetic - (kinetic_nn + kinetic_nnn),
            "charge_identity_residual": mcdw - Sc / NSITES,
        }
        if max(abs(value) for value in residuals.values()) > identity_tolerance:
            raise ValidationError(
                f"Observable identity residual exceeds {identity_tolerance:g} in {row.filename}: {residuals}"
            )
        if not (-0.75 - 1e-10 <= C < 0.0) or not (0.0 <= D < 0.25):
            raise ValidationError(f"Raw Mott-side C_NN/D range failed: {row.filename}")
        if not (0.0 <= nn <= 4.0 and 0.0 <= mcdw <= 1.0 + 1e-10):
            raise ValidationError(f"Raw physical-range check failed: {row.filename}")

        kx, ky = int(row.kx), int(row.ky)
        symmetry = 1.0 if kx == ky else 2.0
        endpoint = (0.5 if kx in (0, 40) else 1.0) * (
            0.5 if ky in (0, 40) else 1.0
        )
        parsed.append(
            {
                "global_index": int(row.global_index),
                "source_campaign": str(row.source_campaign),
                "source_index": int(row.source_index),
                "U": U,
                "V": V,
                "V_over_U": V / U,
                "kx": kx,
                "ky": ky,
                "seed": int(row.seed),
                "symmetry_multiplicity": symmetry,
                "endpoint_weight": endpoint,
                "quadrature_weight": symmetry * endpoint,
                "filename": str(row.filename),
                "raw_path": str(path.resolve()),
                "size_bytes": actual_size,
                "raw_sha256": actual_hash,
                "E0": E0,
                "Gap": gap,
                "C1_NN": C,
                "D_site": D,
                "nn_NN": nn,
                "mCDW2_pipi": mcdw,
                "kinetic_per_site": kinetic,
                **residuals,
                "status": "COMPLETE",
            }
        )
    output = pd.DataFrame(parsed).sort_values("global_index").reset_index(drop=True)
    if len(output) != EXPECTED_COMBINED or output["filename"].duplicated().any():
        raise ValidationError("Parsed raw inventory is not exactly 10,332 unique rows")
    return output


def aggregate_campaign(raw: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for (U, V), group in raw.groupby(["U", "V"], sort=True):
        coordinates = set(zip(group["kx"].astype(int), group["ky"].astype(int)))
        if len(group) != 861 or coordinates != FULL_WEDGE_SET:
            raise ValidationError(f"Cannot aggregate incomplete wedge U={U:g}, V={V:g}")
        weights = group["quadrature_weight"].to_numpy(dtype=float)
        if not math.isclose(float(weights.sum()), 1600.0, abs_tol=1e-12, rel_tol=0):
            raise ValidationError(f"Quadrature weight does not sum to 1600 at U={U:g}, V={V:g}")
        C = group["C1_NN"].to_numpy(dtype=float)
        mean = float(np.average(C, weights=weights))
        std = float(np.sqrt(np.average((C - mean) ** 2, weights=weights)))
        factor = (2.0 * U - V) / (U - V)
        source_counts = group["source_campaign"].value_counts().to_dict()
        rows.append(
            {
                "U": U,
                "V": V,
                "V_over_U": V / U,
                "expected_phase": "Mott",
                "complete_wedge": 861,
                "expansion_coordinates": int(source_counts.get("expansion_complement_836", 0)),
                "reused_coordinates": int(source_counts.get("reused_pilot_25", 0)),
                "quadrature_weight": float(weights.sum()),
                "C_NN_full_861": mean,
                "C_NN_full_quadrature_weighted_population_std": std,
                "C_NN_min": float(C.min()),
                "C_NN_max": float(C.max()),
                "s_eq10_signed": 1.0 + factor * (2.0 * mean - 0.5),
                "D_site_full_quadrature_mean": float(
                    np.average(group["D_site"].to_numpy(dtype=float), weights=weights)
                ),
                "mCDW2_pipi_full_quadrature_mean": float(
                    np.average(group["mCDW2_pipi"].to_numpy(dtype=float), weights=weights)
                ),
                "max_abs_identity_residual": float(
                    group[
                        [
                            "energy_identity_residual",
                            "connected_density_identity_residual",
                            "kinetic_identity_residual",
                            "charge_identity_residual",
                        ]
                    ].abs().to_numpy().max()
                ),
                "C_NN_source": FULL861_EXPANSION_SOURCE,
                "C_NN_sampling": FULL861_SAMPLING,
                "C_NN_fidelity": FULL861_FIDELITY,
                "twist_spread_is_standard_error": False,
            }
        )
    summary = pd.DataFrame(rows)
    cases = {canonical_case(row.U, row.V) for row in summary.itertuples(index=False)}
    if len(summary) != 12 or cases != set(EXPECTED_EXPANSION_CASES):
        raise ValidationError("Aggregated campaign does not contain the exact 12 cases")
    return summary


def compare_snapshot_analyses(
    snapshot_root: Path,
    campaign: pd.DataFrame,
    raw: pd.DataFrame,
) -> dict[str, Path]:
    local_summary_path = require_file(
        snapshot_root / "analysis/fig4_cnn_full861_summary.csv",
        "snapshot-local F861 summary",
    )
    remote_summary_path = require_file(
        snapshot_root / "metadata/analysis/fig4_cnn_full861_summary.csv",
        "snapshot-remote F861 summary",
    )
    remote_provenance_path = require_file(
        snapshot_root / "metadata/analysis/fig4_cnn_full861_provenance.json",
        "snapshot-remote F861 analysis provenance",
    )
    local_raw_path = require_file(
        snapshot_root / "analysis/fig4_cnn_full861_raw_validation.csv",
        "snapshot-local F861 raw validation",
    )
    expected = campaign.sort_values(["U", "V"]).reset_index(drop=True)
    common = (
        "U",
        "V",
        "C_NN_full_861",
        "C_NN_full_quadrature_weighted_population_std",
        "s_eq10_signed",
    )
    for label, path in (("local", local_summary_path), ("remote", remote_summary_path)):
        observed = pd.read_csv(path).sort_values(["U", "V"]).reset_index(drop=True)
        if len(observed) != 12 or not set(common).issubset(observed.columns):
            raise ValidationError(f"Snapshot {label} F861 summary contract is incomplete")
        for column in common:
            if not np.allclose(
                observed[column].to_numpy(dtype=float),
                expected[column].to_numpy(dtype=float),
                atol=1e-13,
                rtol=1e-13,
            ):
                raise ValidationError(
                    f"Snapshot {label} F861 summary disagrees with raw rederivation: {column}"
                )

    local_raw = pd.read_csv(local_raw_path)
    required_raw = {"source_campaign", "U", "V", "kx", "ky", "C_NN", "sha256"}
    if len(local_raw) != EXPECTED_COMBINED or not required_raw.issubset(local_raw.columns):
        raise ValidationError("Snapshot-local raw validation is not exactly 10,332 rows")
    if local_raw.duplicated(["U", "V", "kx", "ky"]).any():
        raise ValidationError("Snapshot-local raw validation contains duplicate coordinates")
    observed_raw = local_raw.sort_values(["U", "V", "kx", "ky"]).reset_index(drop=True)
    expected_raw = raw.sort_values(["U", "V", "kx", "ky"]).reset_index(drop=True)
    for column in ("U", "V", "kx", "ky", "C_NN"):
        expected_column = "C1_NN" if column == "C_NN" else column
        if not np.allclose(
            observed_raw[column].to_numpy(dtype=float),
            expected_raw[expected_column].to_numpy(dtype=float),
            atol=1e-14,
            rtol=1e-13,
        ):
            raise ValidationError(
                f"Snapshot-local raw validation disagrees with raw rederivation: {column}"
            )
    if not observed_raw["sha256"].astype(str).equals(
        expected_raw["raw_sha256"].astype(str)
    ):
        raise ValidationError("Snapshot-local raw-validation hashes disagree with raw bytes")
    expected_sources = expected_raw["source_campaign"].map(
        {"expansion_complement_836": "expansion", "reused_pilot_25": "reused_25"}
    )
    if not observed_raw["source_campaign"].astype(str).equals(expected_sources):
        raise ValidationError("Snapshot-local raw-validation source labels are inconsistent")

    remote_provenance = json.loads(remote_provenance_path.read_text())
    if (
        remote_provenance.get("schema_version") != 1
        or remote_provenance.get("data_product")
        != "fig4_cnn_full861_direct_fullobs_C_NN_eq10"
        or remote_provenance.get("combined_raw_output_count") != EXPECTED_COMBINED
        or remote_provenance.get("case_count") != 12
        or remote_provenance.get("coordinates_per_case") != 861
        or remote_provenance.get("quadrature_weight_per_case") != 1600.0
        or remote_provenance.get("C_NN_observable") != C_NN_OBSERVABLE
        or remote_provenance.get("spread_is_standard_error") is not False
        or remote_provenance.get("manifest_sha256")
        != REVIEWED_FULL861_PINS["expansion_manifest_sha256"]
        or remote_provenance.get("summary_sha256") != sha256(remote_summary_path)
    ):
        raise ValidationError("Snapshot-remote F861 analysis provenance is inconsistent")
    if remote_provenance.get("reused_25_sha256") != sha256(
        snapshot_root / "metadata/reused_25.tsv"
    ):
        raise ValidationError("Snapshot-remote analysis does not pin reused_25.tsv")
    return {
        "local_summary": local_summary_path,
        "remote_summary": remote_summary_path,
        "remote_provenance": remote_provenance_path,
        "local_raw": local_raw_path,
    }


def validate_snapshot_provenance(
    snapshot_root: Path,
    source_raw_digest: str,
    source_rows: pd.DataFrame,
    raw: pd.DataFrame,
) -> tuple[dict, dict, dict, Path, Path, dict]:
    campaign_path = require_file(snapshot_root / "metadata/provenance.json", "campaign provenance")
    decision_path = require_file(
        snapshot_root / "metadata/decision_certificate.json",
        "expansion decision certificate",
    )
    verifier_path = require_file(
        snapshot_root / "metadata/tools/generate_batch.py",
        "archived expansion decision verifier",
    )
    snapshot_path = require_file(
        snapshot_root / "metadata/snapshot_provenance.json", "snapshot provenance"
    )
    campaign = json.loads(campaign_path.read_text())
    snapshot = json.loads(snapshot_path.read_text())
    decision_sha256 = sha256(decision_path)
    verifier_sha256 = sha256(verifier_path)
    package_tools = campaign.get("package_tools_sha256", {})
    expected_pairs = set(EXPECTED_EXPANSION_CASES)
    observed_pairs = {
        canonical_case(row.get("U"), row.get("V")) for row in campaign.get("pairs", [])
    }
    if (
        campaign.get("manifest_sha256")
        != REVIEWED_FULL861_PINS["expansion_manifest_sha256"]
        or campaign.get("source_manifest_sha256")
        != REVIEWED_FULL861_PINS["source_25_manifest_sha256"]
        or campaign.get("plan_sha256")
        != REVIEWED_FULL861_PINS["expansion_plan_sha256"]
        or campaign.get("wedge_sha256")
        != REVIEWED_FULL861_PINS["wedge_861_sha256"]
        or campaign.get("source_result_inventory_digest") != source_raw_digest
        or campaign.get("decision_certificate_sha256") != decision_sha256
        or campaign.get("decision_gate_algorithm") != DECISION_GATE_ALGORITHM
        or not isinstance(package_tools, dict)
        or package_tools.get("generate_batch.py")
        != REVIEWED_FULL861_PINS["expansion_generator_sha256"]
        or verifier_sha256 != REVIEWED_FULL861_PINS["expansion_generator_sha256"]
        or campaign.get("solver_sha256") != REVIEWED_FULL861_PINS["solver_sha256"]
        or campaign.get("source_sha256") != REVIEWED_FULL861_PINS["source_sha256"]
        or campaign.get("qbasis_library_sha256")
        != REVIEWED_FULL861_PINS["qbasis_library_sha256"]
        or campaign.get("reused_total") != 300
        or campaign.get("expansion_total") != 10_032
        or campaign.get("combined_total") != 10_332
        or campaign.get("full_coordinates_per_case") != 861
        or observed_pairs != expected_pairs
    ):
        raise ValidationError("Expansion campaign provenance contract is inconsistent")

    module_name = "archived_fig4_full861_expansion_decision_verifier"
    spec = importlib.util.spec_from_file_location(module_name, verifier_path)
    if spec is None or spec.loader is None:
        raise ValidationError("Could not load archived expansion decision verifier")
    verifier = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(verifier)
        decision, verified_decision_sha256 = verifier.validate_decision_certificate(
            decision_path
        )
    except Exception as exc:
        raise ValidationError(
            f"Archived expansion decision verifier refused the certificate: {exc}"
        ) from exc
    if (
        verified_decision_sha256 != decision_sha256
        or decision.get("decision") != "APPROVE_EXPANSION"
        or decision.get("approved") is not True
        or decision.get("gate_algorithm") != DECISION_GATE_ALGORITHM
        or decision.get("source_raw_inventory", {}).get(
            "ordered_filename_sha256_digest"
        )
        != source_raw_digest
    ):
        raise ValidationError(
            "Expansion decision certificate is not the exact approved source-bound v2 decision"
        )

    source_inventory = [
        {
            "index": int(row.source_index),
            "C_NN": float(row.C1_NN),
        }
        for row in raw.loc[
            raw["source_campaign"].eq("reused_pilot_25")
        ].itertuples(index=False)
    ]
    try:
        source_revalidation = verifier.validate_source_decision_inputs(
            decision,
            source_rows.to_dict(orient="records"),
            source_inventory,
        )
    except Exception as exc:
        raise ValidationError(
            f"Archived verifier could not bind the decision to the 300 reused bytes: {exc}"
        ) from exc
    if campaign.get("source_decision_revalidation") != source_revalidation:
        raise ValidationError(
            "Campaign provenance decision revalidation differs from the 300 reused bytes"
        )

    validation = snapshot.get("validation", {})
    if (
        snapshot.get("schema_version") != 1
        or snapshot.get("immutable_add_only") is not True
        or snapshot.get("expansion_targets") != 10_032
        or snapshot.get("reused_targets") != 300
        or snapshot.get("combined_targets") != 10_332
        or snapshot.get("manifest_sha256")
        != REVIEWED_FULL861_PINS["expansion_manifest_sha256"]
        or snapshot.get("plan_sha256")
        != REVIEWED_FULL861_PINS["expansion_plan_sha256"]
        or snapshot.get("solver_sha256") != REVIEWED_FULL861_PINS["solver_sha256"]
        or snapshot.get("source_sha256") != REVIEWED_FULL861_PINS["source_sha256"]
        or snapshot.get("qbasis_library_sha256")
        != REVIEWED_FULL861_PINS["qbasis_library_sha256"]
        or validation.get("remote_counts") != {"COMPLETE": 10_032}
        or validation.get("local_counts") != {"COMPLETE": 10_332}
        or validation.get("remote_activity") != {}
    ):
        raise ValidationError("Immutable snapshot provenance contract is inconsistent")
    return (
        campaign,
        snapshot,
        decision,
        decision_path,
        verifier_path,
        source_revalidation,
    )


def trapezoidal_weights(frame: pd.DataFrame) -> np.ndarray:
    kx = frame["kx"].to_numpy(dtype=int)
    ky = frame["ky"].to_numpy(dtype=int)
    symmetry = np.where(kx == ky, 1.0, 2.0)
    endpoint = np.where(np.isin(kx, [0, 40]), 0.5, 1.0) * np.where(
        np.isin(ky, [0, 40]), 0.5, 1.0
    )
    return symmetry * endpoint


def validate_u40_controls(summary_path: Path, rows_path: Path) -> pd.DataFrame:
    require_hash(
        summary_path,
        REVIEWED_FULL861_PINS["u40_summary_sha256"],
        "U=40 F861 summary",
    )
    require_hash(rows_path, REVIEWED_FULL861_PINS["u40_rows_sha256"], "U=40 F861 rows")
    summary = pd.read_csv(summary_path)
    rows = pd.read_csv(rows_path)
    needed_summary = {
        "U",
        "V",
        "wedge_rows",
        "wedge_completion_fraction",
        "quadrature_weight_observed",
        "quadrature_completion_fraction",
        "C1_NN_mean",
        "C1_NN_std",
        "branch",
    }
    needed_rows = {
        "U",
        "V",
        "kx",
        "ky",
        "C1_NN",
        "D_site",
        "status",
        "energy_identity_residual",
        "connected_density_identity_residual",
        "kinetic_identity_residual",
        "charge_identity_residual",
    }
    if not needed_summary.issubset(summary.columns) or not needed_rows.issubset(rows.columns):
        raise ValidationError("U=40 F861 inputs lack required columns")
    selected = summary[
        summary.apply(
            lambda row: canonical_case(row["U"], row["V"])
            in set(EXPECTED_CONTROL_CASES),
            axis=1,
        )
    ].copy()
    if len(selected) != 4 or selected.duplicated(["U", "V"]).any():
        raise ValidationError("U=40 F861 summary does not contain four unique controls")
    if {canonical_case(row.U, row.V) for row in selected.itertuples(index=False)} != set(
        EXPECTED_CONTROL_CASES
    ):
        raise ValidationError("U=40 F861 control case inventory mismatch")
    if not (
        selected["wedge_rows"].eq(861).all()
        and np.allclose(selected["wedge_completion_fraction"], 1.0)
        and np.allclose(selected["quadrature_weight_observed"], 1600.0)
        and np.allclose(selected["quadrature_completion_fraction"], 1.0)
        and selected["branch"].astype(str).str.lower().eq("mott").all()
    ):
        raise ValidationError("U=40 controls are not complete F861 Mott grids")

    output: list[dict[str, object]] = []
    residual_columns = [
        "energy_identity_residual",
        "connected_density_identity_residual",
        "kinetic_identity_residual",
        "charge_identity_residual",
    ]
    for control in selected.sort_values("V").itertuples(index=False):
        group = rows[
            rows["U"].astype(float).eq(40.0)
            & np.isclose(rows["V"].astype(float), float(control.V))
        ].copy()
        coordinates = set(zip(group["kx"].astype(int), group["ky"].astype(int)))
        if len(group) != 861 or coordinates != FULL_WEDGE_SET:
            raise ValidationError(f"U=40,V={control.V:g} control wedge is incomplete")
        if not group["status"].astype(str).eq("COMPLETE").all():
            raise ValidationError(f"U=40,V={control.V:g} has a non-COMPLETE row")
        max_residual = float(group[residual_columns].abs().to_numpy().max())
        if max_residual > IDENTITY_TOLERANCE:
            raise ValidationError(f"U=40,V={control.V:g} fails observable identities")
        C = group["C1_NN"].to_numpy(dtype=float)
        D = group["D_site"].to_numpy(dtype=float)
        if np.any((C < -0.75) | (C >= 0.0)) or np.any((D < 0.0) | (D >= 0.25)):
            raise ValidationError(f"U=40,V={control.V:g} fails Mott-side ranges")
        weights = trapezoidal_weights(group)
        if not math.isclose(float(weights.sum()), 1600.0, abs_tol=1e-12, rel_tol=0):
            raise ValidationError("U=40 control quadrature weights do not sum to 1600")
        mean = float(np.average(C, weights=weights))
        std = float(np.sqrt(np.average((C - mean) ** 2, weights=weights)))
        if not math.isclose(mean, float(control.C1_NN_mean), abs_tol=5e-13, rel_tol=0):
            raise ValidationError(f"U=40,V={control.V:g} stored mean mismatch")
        if not math.isclose(std, float(control.C1_NN_std), abs_tol=5e-13, rel_tol=0):
            raise ValidationError(f"U=40,V={control.V:g} stored spread mismatch")
        factor = (80.0 - float(control.V)) / (40.0 - float(control.V))
        output.append(
            {
                "U": 40.0,
                "V": float(control.V),
                "V_over_U": float(control.V) / 40.0,
                "expected_phase": "Mott",
                "complete_wedge": 861,
                "quadrature_weight": 1600.0,
                "C_NN_full_861": mean,
                "C_NN_full_quadrature_weighted_population_std": std,
                "C_NN_min": float(C.min()),
                "C_NN_max": float(C.max()),
                "s_eq10_signed": 1.0 + factor * (2.0 * mean - 0.5),
                "max_abs_identity_residual": max_residual,
                "C_NN_source": FULL861_CONTROL_SOURCE,
                "C_NN_sampling": FULL861_SAMPLING,
                "C_NN_fidelity": FULL861_FIDELITY,
                "twist_spread_is_standard_error": False,
            }
        )
    return pd.DataFrame(output)


def axis_anchor_law(r: np.ndarray, s0: np.ndarray) -> np.ndarray:
    return (s0 - 0.5 * (s0 + 1.0) * r) / (1.0 - r)


def metric_rows(pointwise: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for U, group in pointwise.groupby("U", sort=True):
        for scope, scoped in (
            ("all_points", group),
            ("finite_V_only", group[group["finite_V"]]),
        ):
            eq = scoped["eq10_residual_observed_minus_prediction"].to_numpy(dtype=float)
            anchor = scoped[
                "axis_anchor_residual_observed_minus_prediction"
            ].to_numpy(dtype=float)
            rows.append(
                {
                    "U": float(U),
                    "scope": scope,
                    "point_count": len(scoped),
                    "eq10_rmse": float(np.sqrt(np.mean(eq**2))),
                    "eq10_mae": float(np.mean(np.abs(eq))),
                    "eq10_max_abs_residual": float(np.max(np.abs(eq))),
                    "axis_anchor_rmse": float(np.sqrt(np.mean(anchor**2))),
                    "axis_anchor_mae": float(np.mean(np.abs(anchor))),
                    "axis_anchor_max_abs_residual": float(np.max(np.abs(anchor))),
                    "rmse_reduction_eq10_vs_anchor": float(
                        np.sqrt(np.mean(anchor**2)) - np.sqrt(np.mean(eq**2))
                    ),
                }
            )
    for scope, scoped in (
        ("all_points", pointwise),
        ("finite_V_only", pointwise[pointwise["finite_V"]]),
    ):
        eq = scoped["eq10_residual_observed_minus_prediction"].to_numpy(dtype=float)
        anchor = scoped["axis_anchor_residual_observed_minus_prediction"].to_numpy(dtype=float)
        rows.append(
            {
                "U": "all",
                "scope": scope,
                "point_count": len(scoped),
                "eq10_rmse": float(np.sqrt(np.mean(eq**2))),
                "eq10_mae": float(np.mean(np.abs(eq))),
                "eq10_max_abs_residual": float(np.max(np.abs(eq))),
                "axis_anchor_rmse": float(np.sqrt(np.mean(anchor**2))),
                "axis_anchor_mae": float(np.mean(np.abs(anchor))),
                "axis_anchor_max_abs_residual": float(np.max(np.abs(anchor))),
                "rmse_reduction_eq10_vs_anchor": float(
                    np.sqrt(np.mean(anchor**2)) - np.sqrt(np.mean(eq**2))
                ),
            }
        )
    return pd.DataFrame(rows)


def build_pointwise(
    campaign: pd.DataFrame,
    controls: pd.DataFrame,
    gz_path: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    require_hash(gz_path, REVIEWED_FULL861_PINS["gz_points_sha256"], "GZ scale points")
    gz = pd.read_csv(gz_path)
    required = {"U", "V", "r", "branch", "s", "s_u0", "source_csv"}
    if not required.issubset(gz.columns):
        raise ValidationError("GZ scale-point table lacks required columns")
    selected = gz[
        gz["branch"].astype(str).isin(["U-only", "Mott/spin"])
        & gz["U"].astype(float).isin([20.0, 40.0, 80.0])
    ].copy()
    if len(selected) != 16 or selected.duplicated(["U", "V"]).any():
        raise ValidationError("GZ table does not contain 16 unique Mott-side points")
    cases = {canonical_case(row.U, row.V) for row in selected.itertuples(index=False)}
    if cases != set(EXPECTED_POINTWISE_CASES):
        raise ValidationError("GZ point inventory does not match the exact 16 cases")
    if not np.allclose(selected["r"], selected["V"] / selected["U"], atol=1e-13, rtol=0):
        raise ValidationError("GZ r values are inconsistent with V/U")
    anchors = selected[selected["V"].astype(float).eq(0.0)]
    if len(anchors) != 3 or set(anchors["branch"].astype(str)) != {"U-only"}:
        raise ValidationError("GZ table does not have three U-only anchors")
    for U, group in selected.groupby("U", sort=True):
        if not np.allclose(group["s_u0"], group["s_u0"].iloc[0], atol=1e-13, rtol=0):
            raise ValidationError(f"GZ s_u0 is not constant within U={U:g}")
        anchor = group[group["V"].astype(float).eq(0.0)].iloc[0]
        if not math.isclose(float(anchor["s"]), float(anchor["s_u0"]), abs_tol=1e-13, rel_tol=0):
            raise ValidationError(f"GZ V=0 slope does not equal s_u0 at U={U:g}")

    columns = [
        "U",
        "V",
        "C_NN_full_861",
        "C_NN_full_quadrature_weighted_population_std",
        "complete_wedge",
        "quadrature_weight",
        "C_NN_source",
        "C_NN_sampling",
        "C_NN_fidelity",
        "twist_spread_is_standard_error",
    ]
    c_inputs = pd.concat([campaign[columns], controls[columns]], ignore_index=True)
    if len(c_inputs) != 16 or c_inputs.duplicated(["U", "V"]).any():
        raise ValidationError("C_NN merge is not one-to-one over the exact 16 F861 cases")
    c_inputs = c_inputs.rename(columns={"C_NN_full_861": "C_NN"})
    pointwise = selected.merge(c_inputs, on=["U", "V"], how="left", validate="one_to_one")
    if pointwise["C_NN"].isna().any():
        raise ValidationError("At least one GZ point lacks an independent F861 C_NN")
    pointwise = pointwise.rename(
        columns={
            "complete_wedge": "C_NN_full_wedge_rows",
            "quadrature_weight": "C_NN_quadrature_weight",
        }
    )
    pointwise["C_NN_population_std_diagnostic"] = pointwise[
        "C_NN_full_quadrature_weighted_population_std"
    ]
    pointwise["C_NN_spread"] = np.nan
    pointwise["s_signed_observed"] = -pointwise["s"].astype(float)
    pointwise["s_u0_signed"] = -pointwise["s_u0"].astype(float)
    pointwise["eq10_factor"] = (2.0 * pointwise["U"] - pointwise["V"]) / (
        pointwise["U"] - pointwise["V"]
    )
    pointwise["s_eq10_signed"] = 1.0 + pointwise["eq10_factor"] * (
        2.0 * pointwise["C_NN"] - 0.5
    )
    pointwise["s_axis_anchor_signed"] = axis_anchor_law(
        pointwise["r"].to_numpy(dtype=float),
        pointwise["s_u0_signed"].to_numpy(dtype=float),
    )
    pointwise["eq10_residual_observed_minus_prediction"] = (
        pointwise["s_signed_observed"] - pointwise["s_eq10_signed"]
    )
    pointwise["axis_anchor_residual_observed_minus_prediction"] = (
        pointwise["s_signed_observed"] - pointwise["s_axis_anchor_signed"]
    )
    pointwise["abs_residual_reduction_eq10_vs_anchor"] = (
        pointwise["axis_anchor_residual_observed_minus_prediction"].abs()
        - pointwise["eq10_residual_observed_minus_prediction"].abs()
    )
    pointwise["finite_V"] = pointwise["V"].astype(float) > 0.0
    pointwise["eq10_convention"] = "signed s_NN in omega_GZ=s_NN epsilon_NN"
    pointwise["residual_convention"] = "observed minus prediction"
    pointwise = pointwise.sort_values(["U", "V"]).reset_index(drop=True)
    if not pointwise["C_NN_fidelity"].eq(FULL861_FIDELITY).all():
        raise ValidationError("Not every final pointwise C_NN row is labeled F861")
    return pointwise, metric_rows(pointwise)


def source_inventory_digest(raw: pd.DataFrame) -> str:
    source = raw[raw["source_campaign"].eq("reused_pilot_25")].sort_values("filename")
    if len(source) != 300:
        raise ValidationError("Cannot construct source digest without 300 reused rows")
    text = "".join(
        f"{row.filename}\t{row.raw_sha256}\n" for row in source.itertuples(index=False)
    )
    return hashlib.sha256(text.encode()).hexdigest()


def git_head() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def atomic_write_csv(frame: pd.DataFrame, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    frame.to_csv(tmp, index=False)
    os.replace(tmp, path)


def atomic_write_json(payload: dict, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def main() -> None:
    args = parse_args()
    if args.identity_tolerance != IDENTITY_TOLERANCE:
        raise ValidationError(
            "Publishable all-F861 analysis requires the exact identity tolerance 1e-8"
        )
    supplied_snapshot_root = args.snapshot_root.expanduser()
    if supplied_snapshot_root.is_symlink():
        raise ValidationError(
            f"Immutable snapshot root must not be a symlink: {supplied_snapshot_root}"
        )
    snapshot_root = supplied_snapshot_root.resolve()
    try:
        validate_immutable_snapshot_tree(snapshot_root)
    except Exception as exc:
        raise ValidationError(str(exc)) from exc
    metadata = snapshot_root / "metadata"
    raw_dir = snapshot_root / "raw"
    output_dir = args.output_dir.expanduser().resolve()
    validate_output_destination(output_dir)

    expansion_path = metadata / "manifest.tsv"
    reused_path = metadata / "reused_25.tsv"
    source_path = metadata / "reviewed_inputs/source_25_manifest.tsv"
    ledger_path = metadata / "remote_results_sha256.tsv"
    expansion = load_expansion_manifest(expansion_path)
    source, reused = load_source_and_reused(source_path, reused_path)
    combined = combined_manifest(expansion, reused)
    ledger = load_raw_ledger(ledger_path, combined)
    raw = parse_and_validate_raw(combined, ledger, raw_dir, args.identity_tolerance)
    campaign = aggregate_campaign(raw)
    reused_digest = source_inventory_digest(raw)
    (
        campaign_provenance,
        snapshot_provenance,
        expansion_decision,
        decision_certificate_path,
        decision_verifier_path,
        source_decision_revalidation,
    ) = validate_snapshot_provenance(
        snapshot_root,
        reused_digest,
        source,
        raw,
    )
    snapshot_analysis_paths = compare_snapshot_analyses(snapshot_root, campaign, raw)
    controls = validate_u40_controls(
        args.u40_summary.expanduser().resolve(), args.u40_rows.expanduser().resolve()
    )
    pointwise, families = build_pointwise(
        campaign, controls, args.gz_points.expanduser().resolve()
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    output_paths = {key: output_dir / value for key, value in OUTPUT_BASENAMES.items()}
    atomic_write_csv(raw, output_paths["raw"])
    atomic_write_csv(campaign, output_paths["campaign"])
    atomic_write_csv(controls, output_paths["controls"])
    atomic_write_csv(pointwise, output_paths["pointwise"])
    atomic_write_csv(families, output_paths["families"])
    output_hashes = {
        output_paths[key].name: sha256(output_paths[key])
        for key in ("raw", "campaign", "controls", "pointwise", "families")
    }
    finite_summary = families[
        families["U"].astype(str).eq("all") & families["scope"].eq("finite_V_only")
    ].iloc[0]
    raw_digest = hashlib.sha256(
        "".join(
            f"{row.filename}\t{row.raw_sha256}\n"
            for row in raw.sort_values("filename").itertuples(index=False)
        ).encode()
    ).hexdigest()
    input_paths = {
        "expansion_manifest": expansion_path,
        "reused_25_manifest": reused_path,
        "source_25_manifest": source_path,
        "remote_raw_ledger": ledger_path,
        "campaign_provenance": metadata / "provenance.json",
        "decision_certificate": decision_certificate_path,
        "decision_verifier": decision_verifier_path,
        "snapshot_provenance": metadata / "snapshot_provenance.json",
        **snapshot_analysis_paths,
        "u40_summary": args.u40_summary.expanduser().resolve(),
        "u40_rows": args.u40_rows.expanduser().resolve(),
        "gz_points": args.gz_points.expanduser().resolve(),
    }
    provenance = {
        "schema_version": SCHEMA_VERSION,
        "data_product": DATA_PRODUCT,
        "C_NN_observable": C_NN_OBSERVABLE,
        "C_NN_fidelity": FULL861_FIDELITY,
        "created_at": datetime.now().astimezone().isoformat(),
        "purpose": "staging-only all-F861 downstream analysis; no manuscript or active figure changes",
        "analyzer": str(Path(__file__).resolve()),
        "analyzer_sha256": sha256(Path(__file__).resolve()),
        "git_head": git_head(),
        "snapshot_root": str(snapshot_root),
        "decision_certificate_sha256": sha256(decision_certificate_path),
        "decision_gate_algorithm": expansion_decision["gate_algorithm"],
        "reviewed_inputs": dict(REVIEWED_FULL861_PINS),
        "input_files": {
            label: {"path": str(path), "sha256": sha256(path)}
            for label, path in input_paths.items()
        },
        "campaign_pinned_solver": {
            key: REVIEWED_FULL861_PINS[key]
            for key in ("solver_sha256", "source_sha256", "qbasis_library_sha256")
        },
        "snapshot": {
            "immutable_add_only": bool(snapshot_provenance["immutable_add_only"]),
            "combined_targets": int(snapshot_provenance["combined_targets"]),
            "full_wedges_verified": True,
            "remote_local_analysis_agreement": True,
            "expansion_plan_sha256": campaign_provenance["plan_sha256"],
        },
        "expansion_decision": {
            "decision": expansion_decision["decision"],
            "approved": bool(expansion_decision["approved"]),
            "gate_algorithm": expansion_decision["gate_algorithm"],
            "decision_certificate_sha256": sha256(decision_certificate_path),
            "decision_verifier_sha256": sha256(decision_verifier_path),
            **source_decision_revalidation,
        },
        "raw_output_inventory": {
            "count": len(raw),
            "expansion_count": int(raw["source_campaign"].eq("expansion_complement_836").sum()),
            "reused_25_count": int(raw["source_campaign"].eq("reused_pilot_25").sum()),
            "all_status_complete": bool(raw["status"].eq("COMPLETE").all()),
            "all_sha256_match": True,
            "ordered_filename_sha256_digest": raw_digest,
            "reused_25_ordered_filename_sha256_digest": reused_digest,
            "max_abs_identity_residual": float(
                raw[
                    [
                        "energy_identity_residual",
                        "connected_density_identity_residual",
                        "kinetic_identity_residual",
                        "charge_identity_residual",
                    ]
                ].abs().to_numpy().max()
            ),
            "identity_tolerance": args.identity_tolerance,
        },
        "aggregation": {
            "C_NN_estimator": "861-point wedge with exchange and trapezoidal endpoint weights (weight 1600)",
            "spread_diagnostic": "quadrature-weighted population standard deviation using the same weight 1600",
            "twist_spread_is_standard_error": False,
            "campaign_case_count": len(campaign),
            "full_wedge_coordinates_per_case": 861,
            "quadrature_weight_per_case": 1600.0,
            "pointwise_full861_count": 16,
        },
        "u40_controls": {
            "count": len(controls),
            "raw_wedge_rows": 4 * 861,
            "coordinates_per_case": 861,
            "quadrature_weight_per_case": 1600.0,
            "all_status_complete": True,
            "max_abs_identity_residual": float(
                controls["max_abs_identity_residual"].max()
            ),
            "identity_tolerance": args.identity_tolerance,
            "summary_sha256": REVIEWED_FULL861_PINS["u40_summary_sha256"],
            "rows_sha256": REVIEWED_FULL861_PINS["u40_rows_sha256"],
        },
        "equations": {
            "signed_convention": "omega_GZ(k)=s_NN epsilon_NN(k)",
            "eq10": "s_NN=1+[(2U-V)/(U-V)](2C_NN-1/2)",
            "axis_anchor_baseline": "s_anchor=[s0-(s0+1)r/2]/(1-r), r=V/U",
            "residual": "signed observed minus signed prediction",
        },
        "pointwise": {
            "count": len(pointwise),
            "expansion_full861_C_NN_points": len(campaign),
            "existing_u40_full861_C_NN_points": len(controls),
            "full861_C_NN_points": len(pointwise),
            "all_rows_labeled_F861": bool(pointwise["C_NN_fidelity"].eq("F861").all()),
            "all_C_NN_inputs_independent_of_GZ_slope": True,
            "finite_V_eq10_rmse": float(finite_summary["eq10_rmse"]),
            "finite_V_axis_anchor_rmse": float(finite_summary["axis_anchor_rmse"]),
        },
        "output_files": output_hashes,
        "publication_artifacts_modified": False,
        "methodological_caveat": (
            "The quadrature-weighted population standard deviation measures momentum-grid variation, "
            "not a standard error or confidence interval."
        ),
    }
    atomic_write_json(provenance, output_paths["provenance"])
    print("Validated expansion/reused raw outputs: 10332/10332 COMPLETE and hash-matched")
    print("Verified campaign wedges: 12/12 x 861 coordinates, weight 1600 each")
    print("Verified existing U=40 controls: 4/4 x 861 coordinates")
    print("Final pointwise bundle: 16/16 rows labeled F861")
    print(
        "Finite-V RMSE: "
        f"Eq.10={finite_summary['eq10_rmse']:.9g}, "
        f"axis-anchor={finite_summary['axis_anchor_rmse']:.9g}"
    )
    print(f"Staging outputs: {output_dir}")


if __name__ == "__main__":
    try:
        main()
    except ValidationError as exc:
        raise SystemExit(f"VALIDATION FAILED: {exc}") from exc
