#!/usr/bin/env python3
"""Build a strictly confined Fig. 4 candidate from the U=20 P25 data.

This is intentionally separate from the all-F861 publication pipeline.  It
accepts only the reviewed five-case U=20 staging source and the separately
finalized U=20,V=5 snapshot, validates all 150 raw outputs, and writes one
vertical figure plus its analysis tables below a new directory in ``tmp/``.

The U=20 line preserves the observed V=0 intercept and uses only the measured
fullobs drift,

    C_eff(V) = s_obs(U=20,V=0)/4 + C_P25(V) - C_P25(0),

before evaluating Eq. (10).  U=40 and U=80 retain their existing V=0-axis
anchor guides; the CDW law and transition-boundary panel are unchanged.

There is no promotion path in this program.  Even ``--publication-candidate``
only removes the staging watermark; every output remains confined to a fresh
top-level child of the repository ``tmp/`` directory.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import shutil
import stat
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

import build_scale_and_transition_figure as legacy_fig4


SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[1]
STAGING_ROOT = ROOT / "tmp"
DEFAULT_U20_SOURCE = STAGING_ROOT / "fig4_u20_p25_preview_20260821_085219"
SCALE_POINTS = ROOT / "results" / "pnas_scale_rule_points_eta0p05.csv"
BOUNDARY_SOURCE = ROOT / "results" / "transition_brackets_combined_U2_U40.csv"

SCALE_POINTS_SHA256 = "44755fe1c15efce59903044f31ffa0c794da8d9e85f330f89d3683e6ae609c0a"
BOUNDARY_SOURCE_SHA256 = (
    "22931d887dba76a4b523d3dadeb60378650f75f66dfb4c646a921b57e9aebd27"
)
TWIST_PANEL_SHA256 = "688132fc91e3decdb83784e71d4a69c9868e1f2ead740d753c2ca7e538b06f4b"
PIN_SHA256 = {
    "Hubbard_sym_testobs_UV.x": (
        "b85cefa08615ff2bffd46690990c68b4d1297de7a8b11046ebd6c1c29bdd8c0b"
    ),
    "Hubbard_sym_testobs_UV.cc": (
        "f68ecd93e2dee07012d7fda6521fe617775f637fede1da7f3f0cb27a92e6ce73"
    ),
    "libqbasis.so": (
        "be10e2a72679b2214735c1e71f55dfc331e395a41a0866ecde35b090ca21ba85"
    ),
}

TWISTS = (
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
U20_CASES = (0.0, 2.0, 3.0, 4.0, 4.5)
U20V5_CASES = (5.0,)
ALL_CASES = U20_CASES + U20V5_CASES
IDENTITY_TOLERANCE = 1.0e-8
V5_MOTT_ENDPOINT = 5.02
V5_CHARGE_ENDPOINT = 5.025

MANIFEST_FIELDS = (
    "index",
    "U",
    "V",
    "V_over_U",
    "expected_phase",
    "twist_index",
    "kx",
    "ky",
    "seed",
    "job_name",
    "result",
    "state_at_generation",
    "template",
)
TWIST_FIELDS = (
    "twist_index",
    "kx",
    "ky",
    "diagonal",
    "symmetry_multiplicity",
)
RAW_REQUIRED_KEYS = (
    "Lx",
    "Ly",
    "tp",
    "U",
    "V",
    "E0",
    "<nn_NN>",
    "<delta_n_delta_n_NN>",
    "<Kinetic_NN_per_site>",
    "<Kinetic_NNN_per_site>",
    "<Kinetic_per_site>",
    "<C1_NN>",
    "Q",
    "<ni_upni_dn>",
    "<Sc_pipi>",
    "<mCDW2_pipi>",
    "status",
)

RAW_VALIDATION_BASENAME = "fig4_u20_p25_raw_validation.csv"
CASE_SUMMARY_BASENAME = "fig4_u20_p25_case_summary.csv"
PROVENANCE_BASENAME = "fig4_u20_p25_provenance.json"
FIGURE_PDF_BASENAME = "fig4_u20_p25_vertical.pdf"
FIGURE_PNG_BASENAME = "fig4_u20_p25_vertical.png"
OUTPUT_BASENAMES = frozenset(
    {
        RAW_VALIDATION_BASENAME,
        CASE_SUMMARY_BASENAME,
        PROVENANCE_BASENAME,
        FIGURE_PDF_BASENAME,
        FIGURE_PNG_BASENAME,
    }
)

ACTIVE_ARTIFACTS = {
    "pnas_pdf": legacy_fig4.OUT_PDF,
    "pnas_png": legacy_fig4.OUT_PNG,
    "prl_pdf": legacy_fig4.PRL_VERTICAL_OUT_PDF,
    "prl_png": legacy_fig4.PRL_VERTICAL_OUT_PNG,
    "manuscript_pdf": legacy_fig4.MANUSCRIPT_FIG4_OUT_PDF,
    "analytic_csv": legacy_fig4.ANALYTIC_POINTS,
    "analytic_json": legacy_fig4.ANALYTIC_SUMMARY,
    "boundary_csv": legacy_fig4.BOUNDARY_FILTERED,
    "active_pointer": legacy_fig4.ACTIVE_BUNDLE_POINTER,
}


class CandidateBuildError(RuntimeError):
    """Raised when a source or output violates the figure-only contract."""


@dataclass(frozen=True)
class SourceContract:
    """Exact source identity and inventory expected for one campaign root."""

    role: str
    root_name: str
    cases: tuple[float, ...]
    raw_count: int
    manifest_total_rows: int
    manifest_sha256: str
    provenance_sha256: str
    job_name: str
    provenance_target_count: int
    pin_sha256: tuple[tuple[str, str], ...]
    raw_digest_sha256: str | None = None
    basename_list_sha256: str | None = None
    require_raw_ledger: bool = False
    require_pin_artifacts: bool = False
    require_snapshot_ledger: bool = False

    @property
    def pins(self) -> dict[str, str]:
        return dict(self.pin_sha256)


SOURCE_CONTRACTS = {
    "u20": SourceContract(
        role="reviewed_u20_five_case_staging",
        root_name="fig4_u20_p25_preview_20260821_085219",
        cases=U20_CASES,
        raw_count=125,
        manifest_total_rows=300,
        manifest_sha256=(
            "baa6f80fd1173165fa36f201c52b6c6f9ec4b1d198ef9169687c5977ffd381e5"
        ),
        provenance_sha256=(
            "844658183e18445ea49a01e71303782307474072c32b3937a5ebb31058bad322"
        ),
        job_name="F4CNN25",
        provenance_target_count=300,
        pin_sha256=tuple(PIN_SHA256.items()),
        raw_digest_sha256=(
            "a9c0c155c1b3cf9f073a58a9d30efae71e65ec67c11b82a1d5920af285191e7d"
        ),
        basename_list_sha256=(
            "cd8fdda335457a03728eb9f13442238f1412f7c49158ffacbedd336485a0ce62"
        ),
    ),
    "u20v5": SourceContract(
        role="reviewed_u20_v5_finalized_snapshot",
        root_name="fullobs_25twist_u20v5_fig4_cnn_20260821",
        cases=U20V5_CASES,
        raw_count=25,
        manifest_total_rows=25,
        manifest_sha256=(
            "05d8ee7c0aef76beb1b86b82b4780a9e85fcce9df0c4b8da023d3b84f545943e"
        ),
        provenance_sha256=(
            "ccf109a50ad2bf6d4f0abd2b1c0c2c0723354971c71b6fcdfd8815488484a51e"
        ),
        job_name="F4C20V5",
        provenance_target_count=25,
        pin_sha256=tuple(PIN_SHA256.items()),
        require_raw_ledger=True,
        require_pin_artifacts=True,
        require_snapshot_ledger=True,
    ),
}


@dataclass(frozen=True)
class ValidatedSource:
    """Raw validation rows and their exact source identity."""

    root: Path
    contract: SourceContract
    rows: pd.DataFrame
    provenance: dict[str, object]
    manifest_sha256: str
    provenance_sha256: str
    twist_panel_sha256: str
    raw_digest_sha256: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_real_directory(path: Path, label: str) -> Path:
    try:
        info = path.lstat()
    except OSError as exc:
        raise CandidateBuildError(f"Missing {label}: {path}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise CandidateBuildError(f"{label} must be a real directory: {path}")
    return path


def _require_regular_file(path: Path, label: str) -> Path:
    try:
        info = path.lstat()
    except OSError as exc:
        raise CandidateBuildError(f"Missing {label}: {path}") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode):
        raise CandidateBuildError(f"{label} must be a regular non-link file: {path}")
    return path


def _scan_no_links(root: Path) -> dict[str, Path]:
    """Return every regular file below root and reject all special objects."""
    files: dict[str, Path] = {}
    for current, directory_names, file_names in os.walk(
        root, topdown=True, followlinks=False
    ):
        current_path = Path(current)
        for name in directory_names:
            child = current_path / name
            mode = child.lstat().st_mode
            if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                raise CandidateBuildError(
                    f"Source tree contains a linked/special directory: {child}"
                )
        for name in file_names:
            child = current_path / name
            mode = child.lstat().st_mode
            if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
                raise CandidateBuildError(
                    f"Source tree contains a linked/special file: {child}"
                )
            relative = child.relative_to(root).as_posix()
            if relative in files:
                raise CandidateBuildError(f"Duplicate source-tree path: {relative}")
            files[relative] = child
    return files


def _read_tsv(
    path: Path, expected_fields: tuple[str, ...], label: str
) -> list[dict[str, str]]:
    _require_regular_file(path, label)
    try:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if tuple(reader.fieldnames or ()) != expected_fields:
                raise CandidateBuildError(
                    f"{label} has the wrong exact header: {reader.fieldnames!r}"
                )
            rows = list(reader)
    except (OSError, csv.Error) as exc:
        raise CandidateBuildError(f"Could not parse {label}: {path}") from exc
    if any(None in row for row in rows):
        raise CandidateBuildError(f"{label} contains a row wider than its header")
    return rows


def _safe_int(value: object, label: str) -> int:
    try:
        result = int(str(value))
    except (TypeError, ValueError) as exc:
        raise CandidateBuildError(f"{label} must be an integer: {value!r}") from exc
    return result


def _safe_float(value: object, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise CandidateBuildError(f"{label} must be numeric: {value!r}") from exc
    if not math.isfinite(result):
        raise CandidateBuildError(f"{label} must be finite: {value!r}")
    return result


def _number_tag(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def _expected_raw_name(V: float, kx: int, ky: int) -> str:
    return f"L4x4Nup8Ndn8U20V{_number_tag(V)}tp0f{kx}x{ky}Q0x0_obs.dat"


def _validate_twist_panel(path: Path) -> None:
    if sha256(path) != TWIST_PANEL_SHA256:
        raise CandidateBuildError(
            f"Twist-panel SHA-256 mismatch: {path}; expected {TWIST_PANEL_SHA256}"
        )
    rows = _read_tsv(path, TWIST_FIELDS, "twist panel")
    if len(rows) != len(TWISTS):
        raise CandidateBuildError(
            f"Twist panel must contain exactly 25 rows; found {len(rows)}"
        )
    for twist_index, (row, (kx, ky)) in enumerate(zip(rows, TWISTS), 1):
        expected = {
            "twist_index": str(twist_index),
            "kx": str(kx),
            "ky": str(ky),
            "diagonal": str(kx == ky),
            "symmetry_multiplicity": str(1 if kx == ky else 2),
        }
        if row != expected:
            raise CandidateBuildError(
                f"Twist panel row {twist_index} differs from the reviewed panel"
            )


def _validate_manifest(
    path: Path, contract: SourceContract
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    actual_hash = sha256(path)
    if actual_hash != contract.manifest_sha256:
        raise CandidateBuildError(
            f"{contract.role} manifest SHA-256 mismatch: actual={actual_hash}, "
            f"expected={contract.manifest_sha256}"
        )
    rows = _read_tsv(path, MANIFEST_FIELDS, f"{contract.role} manifest")
    if len(rows) != contract.manifest_total_rows:
        raise CandidateBuildError(
            f"{contract.role} manifest must contain exactly "
            f"{contract.manifest_total_rows} rows; found {len(rows)}"
        )

    selected = [
        row
        for row in rows
        if math.isclose(
            _safe_float(row["U"], "manifest U"),
            20.0,
            rel_tol=0.0,
            abs_tol=1e-13,
        )
        and any(
            math.isclose(
                _safe_float(row["V"], "manifest V"),
                case,
                rel_tol=0.0,
                abs_tol=1e-13,
            )
            for case in contract.cases
        )
    ]
    if len(selected) != contract.raw_count:
        raise CandidateBuildError(
            f"{contract.role} manifest selects {len(selected)} rows; "
            f"expected {contract.raw_count}"
        )

    expected_order = [
        (V, i, *twist) for V in contract.cases for i, twist in enumerate(TWISTS, 1)
    ]
    seen_seeds: set[int] = set()
    seen_names: set[str] = set()
    for position, (row, (expected_v, expected_twist_index, kx, ky)) in enumerate(
        zip(selected, expected_order), 1
    ):
        U = _safe_float(row["U"], "manifest U")
        V = _safe_float(row["V"], "manifest V")
        twist_index = _safe_int(row["twist_index"], "manifest twist_index")
        row_kx = _safe_int(row["kx"], "manifest kx")
        row_ky = _safe_int(row["ky"], "manifest ky")
        seed = _safe_int(row["seed"], "manifest seed")
        result_name = Path(row["result"]).name
        expected_name = _expected_raw_name(expected_v, kx, ky)
        if not (
            math.isclose(U, 20.0, rel_tol=0.0, abs_tol=1e-13)
            and math.isclose(V, expected_v, rel_tol=0.0, abs_tol=1e-13)
            and math.isclose(
                _safe_float(row["V_over_U"], "manifest V_over_U"),
                expected_v / 20.0,
                rel_tol=0.0,
                abs_tol=1e-13,
            )
            and row["expected_phase"] == "Mott"
            and twist_index == expected_twist_index
            and (row_kx, row_ky) == (kx, ky)
            and row["job_name"] == contract.job_name
            and result_name == expected_name
            and row["state_at_generation"] in {"template", "complete"}
        ):
            raise CandidateBuildError(
                f"{contract.role} manifest selected row {position} violates "
                "the reviewed physics/order/phase/name contract"
            )
        if not (1 <= seed <= 0xFFFFFFFF) or seed in seen_seeds:
            raise CandidateBuildError(
                f"{contract.role} manifest contains an invalid/duplicate seed: {seed}"
            )
        if result_name in seen_names:
            raise CandidateBuildError(
                f"{contract.role} manifest contains duplicate result: {result_name}"
            )
        seen_seeds.add(seed)
        seen_names.add(result_name)
    return rows, selected


def _validate_provenance(path: Path, contract: SourceContract) -> dict[str, object]:
    actual_hash = sha256(path)
    if actual_hash != contract.provenance_sha256:
        raise CandidateBuildError(
            f"{contract.role} provenance SHA-256 mismatch: actual={actual_hash}, "
            f"expected={contract.provenance_sha256}"
        )
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise CandidateBuildError(
            f"Could not parse campaign provenance: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise CandidateBuildError("Campaign provenance must be a JSON object")

    expected_pins = contract.pins
    actual_pins = {
        "Hubbard_sym_testobs_UV.x": payload.get("solver_sha256"),
        "Hubbard_sym_testobs_UV.cc": payload.get("source_sha256"),
        "libqbasis.so": payload.get("qbasis_library_sha256"),
    }
    if actual_pins != expected_pins:
        raise CandidateBuildError(
            f"{contract.role} solver/source/library pins do not match the reviewed pins"
        )
    if payload.get("job_name") != contract.job_name:
        raise CandidateBuildError(f"{contract.role} provenance has the wrong job name")
    if payload.get("target_count") != contract.provenance_target_count:
        raise CandidateBuildError(
            f"{contract.role} provenance has the wrong target count"
        )
    physics = payload.get("physics")
    expected_physics = {
        "Lx": 4,
        "Ly": 4,
        "Ndn": 8,
        "Nup": 8,
        "Qm": 0,
        "Qn": 0,
        "tp": 0,
    }
    if physics != expected_physics:
        raise CandidateBuildError(f"{contract.role} provenance has the wrong physics")
    twists = payload.get("twists")
    expected_twists = [{"kx": kx, "ky": ky} for kx, ky in TWISTS]
    if twists != expected_twists:
        raise CandidateBuildError(
            f"{contract.role} provenance has the wrong twist panel"
        )
    pairs = payload.get("pairs")
    if not isinstance(pairs, list):
        raise CandidateBuildError(f"{contract.role} provenance lacks parameter pairs")
    pair_keys = {
        (
            _safe_float(item.get("U"), "provenance U"),
            _safe_float(item.get("V"), "provenance V"),
        )
        for item in pairs
        if isinstance(item, dict)
    }
    for V in contract.cases:
        if (20.0, V) not in pair_keys:
            raise CandidateBuildError(
                f"{contract.role} provenance is missing the U=20,V={V:g} pair"
            )
    aggregation = payload.get("aggregation")
    if (
        not isinstance(aggregation, dict)
        or aggregation.get("primary_C_NN_estimator")
        != "unweighted arithmetic mean over deterministic 25-twist maximin panel"
    ):
        raise CandidateBuildError(f"{contract.role} provenance has the wrong estimator")
    if aggregation.get("twist_spread_is_not_standard_error") is not True:
        raise CandidateBuildError(
            f"{contract.role} provenance must mark twist spread as not a standard error"
        )
    return payload


def _parse_pin_file(path: Path, contract: SourceContract) -> None:
    _require_regular_file(path, "PINNED_SHA256SUMS")
    found: dict[str, str] = {}
    for line in path.read_text().splitlines():
        parts = line.split()
        if len(parts) != 2:
            raise CandidateBuildError(f"Malformed PINNED_SHA256SUMS line: {line!r}")
        digest, relative = parts
        name = Path(relative).name
        if name in found:
            raise CandidateBuildError(f"Duplicate pin declaration for {name}")
        found[name] = digest
    if found != contract.pins:
        raise CandidateBuildError(
            "PINNED_SHA256SUMS does not contain the exact reviewed pins"
        )


def _validate_pin_artifacts(metadata: Path, contract: SourceContract) -> None:
    pin_file = metadata / "PINNED_SHA256SUMS"
    _parse_pin_file(pin_file, contract)
    pinned_dir = _require_real_directory(
        metadata / "pinned_solver", "pinned-solver directory"
    )
    entries = list(pinned_dir.iterdir())
    if any(path.is_symlink() or not path.is_file() for path in entries):
        raise CandidateBuildError(
            "Pinned-solver directory contains a non-regular entry"
        )
    actual_names = {path.name for path in entries}
    if actual_names != set(contract.pins):
        raise CandidateBuildError(
            "Pinned-solver directory does not contain exactly solver/source/libqbasis"
        )
    for name, expected_hash in contract.pins.items():
        path = _require_regular_file(pinned_dir / name, f"pinned artifact {name}")
        if sha256(path) != expected_hash:
            raise CandidateBuildError(f"Pinned artifact hash mismatch: {path}")


def _validate_snapshot_ledger(root: Path) -> None:
    ledger = root / "metadata" / "snapshot_file_sha256.tsv"
    rows = _read_tsv(
        ledger,
        ("sha256", "size_bytes", "relative_path"),
        "snapshot checksum ledger",
    )
    tree = _scan_no_links(root)
    ledger_relative = ledger.relative_to(root).as_posix()
    expected_paths = set(tree) - {ledger_relative}
    ledger_paths: set[str] = set()
    for row in rows:
        relative = row["relative_path"]
        candidate = Path(relative)
        if (
            candidate.is_absolute()
            or ".." in candidate.parts
            or relative in ledger_paths
        ):
            raise CandidateBuildError(
                f"Unsafe/duplicate snapshot-ledger path: {relative!r}"
            )
        ledger_paths.add(relative)
        path = tree.get(relative)
        if path is None:
            raise CandidateBuildError(
                f"Snapshot ledger names a missing file: {relative}"
            )
        if path.stat().st_size != _safe_int(row["size_bytes"], "ledger size"):
            raise CandidateBuildError(f"Snapshot-ledger size mismatch: {relative}")
        if sha256(path) != row["sha256"]:
            raise CandidateBuildError(f"Snapshot-ledger hash mismatch: {relative}")
    if ledger_paths != expected_paths:
        raise CandidateBuildError(
            "Snapshot checksum ledger does not cover the exact snapshot file inventory"
        )


def _validate_raw_ledger(
    path: Path,
    selected_manifest_rows: list[dict[str, str]],
    raw_dir: Path,
) -> None:
    fields = (
        "index",
        "U",
        "V",
        "kx",
        "ky",
        "filename",
        "size_bytes",
        "mtime_ns",
        "sha256",
    )
    rows = _read_tsv(path, fields, "remote raw checksum ledger")
    expected_by_name = {Path(row["result"]).name: row for row in selected_manifest_rows}
    if len(rows) != len(expected_by_name):
        raise CandidateBuildError(
            f"Remote raw checksum ledger must contain exactly {len(expected_by_name)} rows"
        )
    if {row["filename"] for row in rows} != set(expected_by_name):
        raise CandidateBuildError("Remote raw checksum ledger has the wrong filenames")
    for ledger_row in rows:
        manifest_row = expected_by_name[ledger_row["filename"]]
        for field in ("index", "U", "V", "kx", "ky"):
            if ledger_row[field] != manifest_row[field]:
                raise CandidateBuildError(
                    f"Raw ledger/manifest mismatch for {ledger_row['filename']}: {field}"
                )
        raw_path = _require_regular_file(
            raw_dir / ledger_row["filename"], "hash-ledger raw output"
        )
        if raw_path.stat().st_size != _safe_int(ledger_row["size_bytes"], "raw size"):
            raise CandidateBuildError(f"Raw-ledger size mismatch: {raw_path.name}")
        if sha256(raw_path) != ledger_row["sha256"]:
            raise CandidateBuildError(f"Raw-ledger SHA-256 mismatch: {raw_path.name}")


def _parse_raw_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(errors="strict").splitlines()
    except (OSError, UnicodeError) as exc:
        raise CandidateBuildError(f"Could not read raw output as text: {path}") from exc
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise CandidateBuildError(f"Malformed raw line {path}:{line_number}")
        key, value = parts
        if key in values:
            raise CandidateBuildError(f"Duplicate raw key {key!r} in {path}")
        values[key] = value.strip()
    missing = set(RAW_REQUIRED_KEYS) - set(values)
    if missing:
        raise CandidateBuildError(
            f"Raw output {path.name} is missing keys {sorted(missing)}"
        )
    if values["status"] != "COMPLETE":
        raise CandidateBuildError(f"Raw output is not exactly COMPLETE: {path.name}")
    return values


def _parse_and_validate_raw(
    raw_dir: Path,
    selected_manifest_rows: list[dict[str, str]],
    contract: SourceContract,
) -> tuple[pd.DataFrame, str]:
    _require_real_directory(raw_dir, f"{contract.role} raw directory")
    entries = list(raw_dir.iterdir())
    if any(path.is_symlink() or not path.is_file() for path in entries):
        raise CandidateBuildError(
            f"{contract.role} raw directory contains a non-regular entry"
        )
    expected_names = [Path(row["result"]).name for row in selected_manifest_rows]
    actual_names = {path.name for path in entries}
    if len(entries) != contract.raw_count or actual_names != set(expected_names):
        raise CandidateBuildError(
            f"{contract.role} raw inventory must be exactly {contract.raw_count} files; "
            f"missing={sorted(set(expected_names) - actual_names)}, "
            f"unexpected={sorted(actual_names - set(expected_names))}"
        )

    records: list[dict[str, object]] = []
    raw_hashes: list[str] = []
    for manifest_row in selected_manifest_rows:
        V = _safe_float(manifest_row["V"], "manifest V")
        kx = _safe_int(manifest_row["kx"], "manifest kx")
        ky = _safe_int(manifest_row["ky"], "manifest ky")
        path = _require_regular_file(
            raw_dir / Path(manifest_row["result"]).name,
            f"{contract.role} raw output",
        )
        values = _parse_raw_values(path)
        if not (
            math.isclose(
                _safe_float(values["Lx"], "raw Lx"),
                4.0,
                rel_tol=0.0,
                abs_tol=1e-13,
            )
            and math.isclose(
                _safe_float(values["Ly"], "raw Ly"),
                4.0,
                rel_tol=0.0,
                abs_tol=1e-13,
            )
            and math.isclose(
                _safe_float(values["tp"], "raw tp"),
                0.0,
                rel_tol=0.0,
                abs_tol=1e-13,
            )
            and math.isclose(
                _safe_float(values["U"], "raw U"),
                20.0,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            and math.isclose(
                _safe_float(values["V"], "raw V"),
                V,
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            and values["Q"] == "0,0"
        ):
            raise CandidateBuildError(f"Raw physics metadata mismatch: {path.name}")

        E0 = _safe_float(values["E0"], "raw E0")
        nn = _safe_float(values["<nn_NN>"], "raw <nn_NN>")
        delta_nn = _safe_float(
            values["<delta_n_delta_n_NN>"], "raw <delta_n_delta_n_NN>"
        )
        kinetic_nn = _safe_float(
            values["<Kinetic_NN_per_site>"], "raw <Kinetic_NN_per_site>"
        )
        kinetic_nnn = _safe_float(
            values["<Kinetic_NNN_per_site>"], "raw <Kinetic_NNN_per_site>"
        )
        kinetic = _safe_float(values["<Kinetic_per_site>"], "raw <Kinetic_per_site>")
        C_NN = _safe_float(values["<C1_NN>"], "raw <C1_NN>")
        D_site = _safe_float(values["<ni_upni_dn>"], "raw <ni_upni_dn>")
        Sc_pipi = _safe_float(values["<Sc_pipi>"], "raw <Sc_pipi>")
        mCDW2 = _safe_float(values["<mCDW2_pipi>"], "raw <mCDW2_pipi>")
        if not (-0.75 <= C_NN < 0.0):
            raise CandidateBuildError(
                f"Mott-side C_NN is outside [-0.75,0): {path.name}"
            )
        if not (0.0 <= D_site < 0.25):
            raise CandidateBuildError(
                f"Mott-side double occupancy must be <0.25: {path.name}"
            )

        residuals = {
            "identity_energy_per_site_residual": (
                E0 / 16.0 - (kinetic + 20.0 * D_site + 2.0 * V * nn)
            ),
            "identity_connected_density_residual": delta_nn - (nn - 1.0),
            "identity_kinetic_sum_residual": kinetic - (kinetic_nn + kinetic_nnn),
            "identity_charge_Sc_over_N_residual": mCDW2 - Sc_pipi / 16.0,
        }
        worst = max(abs(value) for value in residuals.values())
        if worst > IDENTITY_TOLERANCE:
            raise CandidateBuildError(
                f"Four-identity tolerance exceeded in {path.name}: {worst:.3e}"
            )
        raw_hash = sha256(path)
        raw_hashes.append(raw_hash)
        records.append(
            {
                "source_role": contract.role,
                "source_root": str(raw_dir.parent.resolve()),
                "manifest_index": _safe_int(manifest_row["index"], "manifest index"),
                "U": 20.0,
                "V": V,
                "r": V / 20.0,
                "analytic_phase": "Mott",
                "twist_index": _safe_int(
                    manifest_row["twist_index"], "manifest twist_index"
                ),
                "kx": kx,
                "ky": ky,
                "seed": _safe_int(manifest_row["seed"], "manifest seed"),
                "raw_filename": path.name,
                "raw_size_bytes": path.stat().st_size,
                "raw_sha256": raw_hash,
                "status": "COMPLETE",
                "C_NN": C_NN,
                "D_site": D_site,
                "nn_NN": nn,
                "delta_n_delta_n_NN": delta_nn,
                "kinetic_NN_per_site": kinetic_nn,
                "kinetic_NNN_per_site": kinetic_nnn,
                "kinetic_per_site": kinetic,
                "E0": E0,
                "Sc_pipi": Sc_pipi,
                "mCDW2_pipi": mCDW2,
                **residuals,
                "max_abs_identity_residual": worst,
            }
        )
    digest = hashlib.sha256("".join(sorted(raw_hashes)).encode()).hexdigest()
    if contract.raw_digest_sha256 is not None and digest != contract.raw_digest_sha256:
        raise CandidateBuildError(
            f"{contract.role} raw aggregate digest mismatch: actual={digest}, "
            f"expected={contract.raw_digest_sha256}"
        )
    return pd.DataFrame(records), digest


def validate_source(root: Path, contract: SourceContract) -> ValidatedSource:
    """Validate one exact campaign/snapshot without writing any output."""
    source_input = Path(root).expanduser()
    if not source_input.is_absolute():
        source_input = Path.cwd() / source_input
    _require_real_directory(source_input, f"{contract.role} source root")
    source_root = source_input.resolve()
    if source_root.name != contract.root_name:
        raise CandidateBuildError(
            f"{contract.role} source root must retain the reviewed name "
            f"{contract.root_name!r}; found {source_root.name!r}"
        )
    metadata = _require_real_directory(source_root / "metadata", "source metadata")
    manifest = metadata / "manifest.tsv"
    provenance_path = metadata / "provenance.json"
    twist_panel = metadata / "twist_panel.tsv"
    _require_regular_file(manifest, "campaign manifest")
    _require_regular_file(provenance_path, "campaign provenance")
    _require_regular_file(twist_panel, "twist panel")

    if contract.require_snapshot_ledger:
        _validate_snapshot_ledger(source_root)
    else:
        _scan_no_links(source_root)
    _validate_twist_panel(twist_panel)
    _, selected = _validate_manifest(manifest, contract)
    provenance = _validate_provenance(provenance_path, contract)

    if contract.basename_list_sha256 is not None:
        basename_list = _require_regular_file(
            metadata / "u20_raw_basenames.txt", "reviewed U20 basename list"
        )
        if sha256(basename_list) != contract.basename_list_sha256:
            raise CandidateBuildError("Reviewed U20 basename-list SHA-256 mismatch")
        expected_names = [Path(row["result"]).name for row in selected]
        if basename_list.read_text().splitlines() != expected_names:
            raise CandidateBuildError(
                "Reviewed U20 basename list disagrees with the manifest"
            )

    if contract.require_pin_artifacts:
        _validate_pin_artifacts(metadata, contract)
    if contract.require_raw_ledger:
        _validate_raw_ledger(
            metadata / "remote_results_sha256.tsv", selected, source_root / "raw"
        )
    raw_rows, raw_digest = _parse_and_validate_raw(
        source_root / "raw", selected, contract
    )
    return ValidatedSource(
        root=source_root,
        contract=contract,
        rows=raw_rows,
        provenance=provenance,
        manifest_sha256=sha256(manifest),
        provenance_sha256=sha256(provenance_path),
        twist_panel_sha256=sha256(twist_panel),
        raw_digest_sha256=raw_digest,
    )


def eq10_signed(U: float, V: float, C_NN: float) -> float:
    if not all(math.isfinite(value) for value in (U, V, C_NN)) or math.isclose(
        U, V, rel_tol=0.0, abs_tol=1e-14
    ):
        raise CandidateBuildError("Eq. (10) requires finite U,V,C_NN and U != V")
    return 1.0 + ((2.0 * U - V) / (U - V)) * (2.0 * C_NN - 0.5)


def _load_figure_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    if sha256(SCALE_POINTS) != SCALE_POINTS_SHA256:
        raise CandidateBuildError(
            "GZ scale-point input changed from the reviewed bytes"
        )
    if sha256(BOUNDARY_SOURCE) != BOUNDARY_SOURCE_SHA256:
        raise CandidateBuildError(
            "Transition-boundary input changed from the reviewed bytes"
        )
    points = legacy_fig4.load_scale_data()
    boundary = legacy_fig4.load_boundary_data(write_filtered=False)
    bracket = pd.read_csv(BOUNDARY_SOURCE)
    row = bracket[np.isclose(bracket["U"].to_numpy(dtype=float), 20.0)]
    if len(row) != 1:
        raise CandidateBuildError(
            "Transition source must contain exactly one U=20 bracket"
        )
    endpoint = row.iloc[0]
    if not (
        math.isclose(
            float(endpoint["V_Mott"]),
            V5_MOTT_ENDPOINT,
            rel_tol=0.0,
            abs_tol=1e-13,
        )
        and math.isclose(
            float(endpoint["V_charge"]),
            V5_CHARGE_ENDPOINT,
            rel_tol=0.0,
            abs_tol=1e-13,
        )
        and 5.0 < float(endpoint["V_Mott"])
    ):
        raise CandidateBuildError(
            "U=20,V=5 is not strictly below the reviewed Mott endpoint 5.02"
        )
    return points, boundary


def build_case_summary(raw: pd.DataFrame, points: pd.DataFrame) -> pd.DataFrame:
    """Build the exact six-row axis-anchored measured-C drift product."""
    if len(raw) != 150 or raw.duplicated(["V", "twist_index"]).any():
        raise CandidateBuildError(
            "Combined raw validation must contain exact 150 unique rows"
        )
    observed = points[points["U"].eq(20.0) & points["V"].isin(ALL_CASES)].sort_values(
        "V"
    )
    if len(observed) != 6 or tuple(observed["V"].astype(float)) != ALL_CASES:
        raise CandidateBuildError("GZ input does not contain the exact six U=20 nodes")
    expected_legacy_branches = (
        "U-only",
        "Mott/spin",
        "Mott/spin",
        "Mott/spin",
        "Mott/spin",
        "boundary",
    )
    if tuple(observed["branch"].astype(str)) != expected_legacy_branches:
        raise CandidateBuildError("GZ source branch inventory changed unexpectedly")

    groups = {float(V): group for V, group in raw.groupby("V", sort=True)}
    if tuple(groups) != ALL_CASES or any(len(group) != 25 for group in groups.values()):
        raise CandidateBuildError(
            "Each of the six U=20 cases must contain exactly 25 twists"
        )
    C_means = {
        V: statistics.fmean(group["C_NN"].astype(float)) for V, group in groups.items()
    }
    C0 = C_means[0.0]
    observed_by_V = observed.set_index("V")
    s_observed_v0 = -float(observed_by_V.loc[0.0, "s"])
    C_axis_anchor = s_observed_v0 / 4.0

    rows: list[dict[str, object]] = []
    for V in ALL_CASES:
        group = groups[V]
        C_mean = C_means[V]
        C_drift = C_mean - C0
        C_effective = C_axis_anchor + C_drift
        factor = (40.0 - V) / (20.0 - V)
        s_line = eq10_signed(20.0, V, C_effective)
        direct_s = eq10_signed(20.0, V, C_mean)
        observed_row = observed_by_V.loc[V]
        weights = np.where(group["kx"].eq(group["ky"]), 1.0, 2.0)
        symmetry_C = float(np.average(group["C_NN"].astype(float), weights=weights))
        values = group["C_NN"].astype(float).to_numpy()
        rows.append(
            {
                "U": 20.0,
                "V": V,
                "r": V / 20.0,
                "legacy_source_branch": str(observed_row["branch"]),
                "analytic_phase": "Mott",
                "analytic_phase_basis": (
                    "V=5 < reviewed V_Mott=5.02"
                    if math.isclose(V, 5.0)
                    else "reviewed manifest expected_phase=Mott"
                ),
                "complete_twists": len(group),
                "C_NN_P25_mean": C_mean,
                "C_NN_P25_V0_mean": C0,
                "C_NN_P25_min": float(values.min()),
                "C_NN_P25_max": float(values.max()),
                "C_NN_P25_spread": float(values.max() - values.min()),
                "C_NN_P25_population_std_diagnostic": float(values.std(ddof=0)),
                "C_NN_symmetry_weighted_diagnostic": symmetry_C,
                "C_NN_symmetry_minus_unweighted_diagnostic": symmetry_C - C_mean,
                "twist_spread_is_standard_error": False,
                "s_observed_U20_V0_signed": s_observed_v0,
                "C_NN_axis_anchor_from_s_observed_V0": C_axis_anchor,
                "C_NN_measured_drift_from_V0": C_drift,
                "C_NN_effective_axis_anchored_drift": C_effective,
                "eq10_factor": factor,
                "s_eq10_axis_anchored_measured_C_drift": s_line,
                "s_eq10_direct_P25_diagnostic": direct_s,
                "s_observed_signed": -float(observed_row["s"]),
                "residual_observed_minus_drift_line": -float(observed_row["s"])
                - s_line,
                "V_Mott_reviewed": V5_MOTT_ENDPOINT,
                "V_charge_reviewed": V5_CHARGE_ENDPOINT,
                "line_model": "axis-anchored measured fullobs C_NN drift then Eq. (10)",
            }
        )
    summary = pd.DataFrame(rows)
    if len(summary) != 6 or not math.isclose(
        float(summary.iloc[0]["s_eq10_axis_anchored_measured_C_drift"]),
        s_observed_v0,
        rel_tol=0.0,
        abs_tol=5e-13,
    ):
        raise CandidateBuildError(
            "U=20 drift line does not reproduce its observed V=0 anchor"
        )
    return summary


def _draw_scale_panel(
    ax: plt.Axes, points: pd.DataFrame, summary: pd.DataFrame
) -> None:
    """Draw panel (a) with only U=20 changed from the legacy construction."""
    ax.axvspan(0.0, legacy_fig4.R_BOUNDARY, color="#3b78a8", alpha=0.055, zorder=0)
    ax.axvspan(legacy_fig4.R_BOUNDARY, 0.53, color="#b64a42", alpha=0.05, zorder=0)
    for U in (20.0, 40.0, 80.0):
        group = points[points["U"].eq(U)].sort_values("r")
        ax.plot(
            group["r"],
            -group["s"].to_numpy(dtype=float),
            marker=legacy_fig4.MARKERS[U],
            color=legacy_fig4.COLORS[U],
            lw=0,
            ms=6.5,
            label=rf"$U={U:g}$",
            zorder=4,
        )
        if U in (40.0, 80.0):
            s0 = -float(group.loc[group["V"].eq(0.0), "s_u0"].iloc[0])
            r_values = np.linspace(0.0, 0.245, 220)
            ax.plot(
                r_values,
                legacy_fig4.mott_scale_law_from_axis_anchor(r_values, s0),
                color=legacy_fig4.COLORS[U],
                lw=1.55,
                alpha=0.8,
            )

    ax.plot(
        summary["r"],
        summary["s_eq10_axis_anchored_measured_C_drift"],
        marker=legacy_fig4.MARKERS[20.0],
        markerfacecolor="white",
        markeredgecolor=legacy_fig4.COLORS[20.0],
        markeredgewidth=1.2,
        color=legacy_fig4.COLORS[20.0],
        lw=1.65,
        ms=5.4,
        zorder=5,
    )
    r_cdw = np.linspace(0.255, 0.52, 240)
    ax.plot(
        r_cdw,
        legacy_fig4.cdw_scale_law(r_cdw),
        color="black",
        ls="-.",
        lw=2.0,
    )
    ax.axvline(legacy_fig4.R_BOUNDARY, color="0.35", lw=1.0, ls=":")
    ax.hlines(
        legacy_fig4.S_U_RESOLUTION,
        0.0,
        legacy_fig4.R_BOUNDARY,
        color="0.45",
        ls="--",
        lw=1.0,
    )
    ax.hlines(
        legacy_fig4.S_V,
        legacy_fig4.R_BOUNDARY,
        0.53,
        color="0.15",
        ls=":",
        lw=1.35,
    )
    ax.text(
        0.125,
        legacy_fig4.S_U_RESOLUTION - 0.018,
        r"$U\to\infty,\ 4C_{\mathrm{NN}}$",
        ha="center",
        va="top",
        color="0.38",
    )
    ax.text(
        0.515,
        legacy_fig4.S_V - 0.008,
        r"$V$-only $-8/7$",
        ha="right",
        va="top",
        color="0.1",
    )
    ax.text(0.105, -1.075, "Mott side", color="#1f5278", ha="center", va="top")
    ax.text(0.39, -1.075, "CDW side", color="#8d2d28", ha="center", va="top")
    ax.set_xlabel(r"$V/U$")
    ax.set_ylabel(r"Estimated $s_{\mathrm{NN}}(U,V)$")
    ax.set_xlim(-0.01, 0.53)
    ax.set_ylim(-1.84, -1.06)
    ax.grid(alpha=0.18)
    handles, labels = ax.get_legend_handles_labels()
    handles.append(
        Line2D(
            [],
            [],
            color=legacy_fig4.COLORS[20.0],
            marker=legacy_fig4.MARKERS[20.0],
            markerfacecolor="white",
            markeredgecolor=legacy_fig4.COLORS[20.0],
            lw=1.65,
            ms=5.4,
        )
    )
    labels.append(r"$U=20$ line: fullobs $C_{\mathrm{NN}}$ drift")
    ax.legend(
        handles,
        labels,
        frameon=False,
        ncol=1,
        loc="upper left",
        bbox_to_anchor=(0.005, 0.88),
        borderaxespad=0.0,
        fontsize=8.2,
    )
    legacy_fig4.panel_label(ax, "(a)", -0.13, fontsize=17.0)


def _render_vertical_figure(
    *,
    points: pd.DataFrame,
    boundary: pd.DataFrame,
    summary: pd.DataFrame,
    out_pdf: Path,
    out_png: Path,
    watermark: bool,
) -> None:
    with plt.rc_context(legacy_fig4.STYLE):
        fig, axes = plt.subplots(
            2,
            1,
            figsize=(5.55, 7.8),
            gridspec_kw={"height_ratios": [1.0, 1.0]},
        )
        _draw_scale_panel(axes[0], points, summary)
        legacy_fig4.draw_boundary_panel(
            axes[1],
            boundary,
            mixed_momentum_terms=True,
            panel_label_fontsize=17.0,
            panel_label_x=-0.19,
        )
        for axis in axes:
            axis.xaxis.label.set_fontsize(legacy_fig4.STYLE["axes.labelsize"] * 1.4)
            axis.yaxis.label.set_fontsize(legacy_fig4.STYLE["axes.labelsize"] * 1.4)
            axis.tick_params(
                axis="x", labelsize=legacy_fig4.STYLE["xtick.labelsize"] * 1.4
            )
            axis.tick_params(
                axis="y", labelsize=legacy_fig4.STYLE["ytick.labelsize"] * 1.4
            )
        fig.subplots_adjust(
            left=0.200,
            right=0.995,
            top=0.992 if not watermark else 0.982,
            bottom=0.082,
            hspace=0.20,
        )
        if watermark:
            fig.text(
                0.5,
                0.998,
                "STAGING PREVIEW — U=20 P25 FULL-OBS C_NN DRIFT — NOT FOR PUBLICATION",
                ha="center",
                va="top",
                color="#9b1c1c",
                fontsize=8.4,
                fontweight="bold",
            )
        fig.savefig(out_pdf, bbox_inches="tight")
        fig.savefig(out_png, dpi=280, bbox_inches="tight")
        plt.close(fig)


def _path_state(path: Path) -> dict[str, object]:
    if not os.path.lexists(path):
        return {"state": "absent"}
    info = path.lstat()
    if stat.S_ISREG(info.st_mode):
        return {
            "state": "regular_file",
            "size_bytes": info.st_size,
            "sha256": sha256(path),
        }
    if stat.S_ISLNK(info.st_mode):
        return {"state": "symlink", "target": os.readlink(path)}
    return {"state": "other", "mode": stat.S_IFMT(info.st_mode)}


def _active_artifact_state() -> dict[str, dict[str, object]]:
    return {role: _path_state(Path(path)) for role, path in ACTIVE_ARTIFACTS.items()}


def validate_output_directory(path: Path) -> Path:
    """Require one absent, non-hidden, top-level child of repository tmp/."""
    staging_root = STAGING_ROOT.resolve()
    _require_real_directory(staging_root, "repository staging root")
    output_input = Path(path).expanduser()
    if not output_input.is_absolute():
        output_input = Path.cwd() / output_input
    if os.path.lexists(output_input):
        raise CandidateBuildError(
            f"Output directory already exists; refusing overwrite: {output_input}"
        )
    output = output_input.resolve()
    if output.parent != staging_root:
        raise CandidateBuildError(
            f"Output must be a fresh top-level child of {staging_root}: {output}"
        )
    if not output.name.startswith("fig4_u20_p25_") or output.name.startswith("."):
        raise CandidateBuildError(
            "Output directory name must start with 'fig4_u20_p25_'"
        )
    if os.path.lexists(output):
        raise CandidateBuildError(
            f"Output directory already exists; refusing overwrite: {output}"
        )
    active_resolved = {Path(path).resolve() for path in ACTIVE_ARTIFACTS.values()}
    if output in active_resolved:
        raise CandidateBuildError("Output directory collides with an active artifact")
    return output


def _remove_owned_output(path: Path, identity: tuple[int, int]) -> None:
    if not os.path.lexists(path):
        return
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise CandidateBuildError(f"Refusing cleanup of replaced output path: {path}")
    if (info.st_dev, info.st_ino) != identity:
        raise CandidateBuildError(
            f"Refusing cleanup after output directory identity changed: {path}"
        )
    shutil.rmtree(path)


def _write_provenance(
    *,
    output: Path,
    sources: Iterable[ValidatedSource],
    raw: pd.DataFrame,
    summary: pd.DataFrame,
    publication_candidate: bool,
    active_before: dict[str, dict[str, object]],
) -> Path:
    source_records: list[dict[str, object]] = []
    for source in sources:
        source_records.append(
            {
                "role": source.contract.role,
                "root": str(source.root),
                "manifest_sha256": source.manifest_sha256,
                "provenance_sha256": source.provenance_sha256,
                "twist_panel_sha256": source.twist_panel_sha256,
                "raw_count": len(source.rows),
                "raw_digest_sha256": source.raw_digest_sha256,
                "solver_source_library_pins": source.contract.pins,
            }
        )
    output_hashes = {
        name: sha256(output / name)
        for name in (
            RAW_VALIDATION_BASENAME,
            CASE_SUMMARY_BASENAME,
            FIGURE_PDF_BASENAME,
            FIGURE_PNG_BASENAME,
        )
    }
    max_identity = {
        column: float(raw[column].abs().max())
        for column in (
            "identity_energy_per_site_residual",
            "identity_connected_density_residual",
            "identity_kinetic_sum_residual",
            "identity_charge_Sc_over_N_residual",
        )
    }
    payload = {
        "schema_version": 1,
        "data_product": "fig4_u20_p25_axis_anchored_measured_C_NN_drift_candidate",
        "created_at": dt.datetime.now().astimezone().isoformat(),
        "builder": str(SCRIPT),
        "builder_sha256": sha256(SCRIPT),
        "output_directory": str(output),
        "output_confinement_root": str(STAGING_ROOT.resolve()),
        "publication_candidate": publication_candidate,
        "watermark_applied": not publication_candidate,
        "promotion_supported": False,
        "publication_artifacts_modified": False,
        "sources": source_records,
        "input_files": {
            "GZ_scale_points": {
                "path": str(SCALE_POINTS),
                "sha256": SCALE_POINTS_SHA256,
            },
            "transition_boundary": {
                "path": str(BOUNDARY_SOURCE),
                "sha256": BOUNDARY_SOURCE_SHA256,
            },
        },
        "raw_validation": {
            "row_count": len(raw),
            "case_count": int(raw[["U", "V"]].drop_duplicates().shape[0]),
            "complete_count": int(raw["status"].eq("COMPLETE").sum()),
            "identity_tolerance": IDENTITY_TOLERANCE,
            "max_abs_identity_residuals": max_identity,
        },
        "case_summary": {
            "row_count": len(summary),
            "cases": [
                {"U": 20.0, "V": float(V), "analytic_phase": "Mott"}
                for V in summary["V"]
            ],
            "primary_estimator": (
                "unweighted arithmetic mean over deterministic maximin 25-twist panel"
            ),
            "twist_spread_is_standard_error": False,
        },
        "line_contract": {
            "U20": ("C_eff(V)=s_obs(U20,V0)/4+C_P25(V)-C_P25(0), then signed Eq. (10)"),
            "U40_U80": "unchanged V=0-axis-anchor guides",
            "CDW": "unchanged Eq. (11) checkerboard law",
            "boundary": "unchanged reviewed U>=4 bracket panel",
            "finite_V_GZ_fit_parameters": 0,
            "V5_analytic_phase": "Mott because 5 < V_Mott=5.02",
        },
        "active_artifact_prestate": active_before,
        "outputs_sha256": output_hashes,
    }
    path = output / PROVENANCE_BASENAME
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return path


def build_candidate(
    *,
    u20_source: Path,
    u20v5_source: Path,
    output_dir: Path,
    publication_candidate: bool = False,
) -> dict[str, Path]:
    """Validate all inputs and build the complete confined candidate bundle."""
    output = validate_output_directory(output_dir)
    u20 = validate_source(u20_source, SOURCE_CONTRACTS["u20"])
    u20v5 = validate_source(u20v5_source, SOURCE_CONTRACTS["u20v5"])
    if u20.contract.pins != u20v5.contract.pins:
        raise CandidateBuildError(
            "U20 and U20,V5 sources do not use identical reviewed pins"
        )
    raw = pd.concat([u20.rows, u20v5.rows], ignore_index=True)
    raw = raw.sort_values(["V", "twist_index"], kind="stable").reset_index(drop=True)
    if len(raw) != 150 or tuple(raw.groupby("V", sort=True).size()) != (25,) * 6:
        raise CandidateBuildError(
            "Combined source does not contain exact 150/6 P25 rows"
        )
    points, boundary = _load_figure_inputs()
    summary = build_case_summary(raw, points)

    active_before = _active_artifact_state()
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    info = output.lstat()
    identity = (info.st_dev, info.st_ino)
    paths = {
        "raw_validation": output / RAW_VALIDATION_BASENAME,
        "case_summary": output / CASE_SUMMARY_BASENAME,
        "provenance": output / PROVENANCE_BASENAME,
        "figure_pdf": output / FIGURE_PDF_BASENAME,
        "figure_png": output / FIGURE_PNG_BASENAME,
    }
    try:
        raw.to_csv(paths["raw_validation"], index=False)
        summary.to_csv(paths["case_summary"], index=False)
        _render_vertical_figure(
            points=points,
            boundary=boundary,
            summary=summary,
            out_pdf=paths["figure_pdf"],
            out_png=paths["figure_png"],
            watermark=not publication_candidate,
        )
        _write_provenance(
            output=output,
            sources=(u20, u20v5),
            raw=raw,
            summary=summary,
            publication_candidate=publication_candidate,
            active_before=active_before,
        )
        if {path.name for path in output.iterdir()} != OUTPUT_BASENAMES:
            raise CandidateBuildError(
                "Candidate output directory has the wrong exact inventory"
            )
        for path in paths.values():
            _require_regular_file(path, "candidate output")
            if path.stat().st_size <= 0:
                raise CandidateBuildError(f"Candidate output is empty: {path}")
        if _active_artifact_state() != active_before:
            raise CandidateBuildError(
                "An active/manuscript/results Fig. 4 artifact changed during the confined build"
            )
    except BaseException as build_error:
        try:
            _remove_owned_output(output, identity)
        except BaseException as cleanup_error:
            raise CandidateBuildError(
                f"Candidate build failed and owned-output cleanup also failed: {cleanup_error}"
            ) from build_error
        raise
    return paths


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--u20-source",
        type=Path,
        default=DEFAULT_U20_SOURCE,
        help="Exact reviewed 125-row U=20 staging root",
    )
    parser.add_argument(
        "--u20v5-source",
        type=Path,
        required=True,
        help="Exact finalized 25-row U=20,V=5 snapshot root",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Absent top-level child of repository tmp/ named fig4_u20_p25_*",
    )
    parser.add_argument(
        "--publication-candidate",
        action="store_true",
        help=(
            "Remove the staging watermark after review; output remains confined "
            "to tmp/ and cannot be promoted by this script"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        paths = build_candidate(
            u20_source=args.u20_source,
            u20v5_source=args.u20v5_source,
            output_dir=args.output_dir,
            publication_candidate=args.publication_candidate,
        )
    except CandidateBuildError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "status": "BUILT_CONFINED_PUBLICATION_CANDIDATE"
                if args.publication_candidate
                else "BUILT_WATERMARKED_STAGING_PREVIEW",
                "publication_artifacts_modified": False,
                "outputs": {role: str(path) for role, path in paths.items()},
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
