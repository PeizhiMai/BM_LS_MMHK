#!/usr/bin/python3.11
"""Dry-run or materialize the conditional Fig. 4 25→861 complement batch.

The default mode is a local, read-only coordinate-plan audit.  Materialization
requires both ``--materialize`` and a valid ``APPROVE_EXPANSION`` decision
certificate.  This program never invokes ``sbatch``.  A generated submission
helper is separately double-armed and defaults to a dry run.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


SCRIPT = Path(__file__).resolve()
PACKAGE = SCRIPT.parent

BASE_DEFAULT = Path("/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs")
SOURCE_BATCH_DEFAULT = BASE_DEFAULT / "fig4_cnn" / "fullobs_25twist_fig4_cnn_20260820"
BATCH_NAME = "fullobs_861expand_fig4_cnn_20260821"
BATCH_DEFAULT = BASE_DEFAULT / "fig4_cnn" / BATCH_NAME
SOLVER_DEFAULT = BASE_DEFAULT / "Hubbard_sym_testobs_UV.x"
SOURCE_DEFAULT = BASE_DEFAULT / "Hubbard_sym_testobs_UV.cc"
QBASIS_DEFAULT = Path("/home/9pm/installs/lib/libqbasis.so")

JOB_NAME = "F4CNN861X"
REPAIR_JOB_NAME = "F4CNN861R"
TEMPLATE_PREFIX = "job_f4cnn861x_"
CONFIRM_ENV = "F4CNN861X_CONFIRM_SUBMIT"
CHAIN_ENV = "F4CNN861X_CHAIN_SUBMIT"

EXPECTED_SOLVER_SHA256 = (
    "b85cefa08615ff2bffd46690990c68b4d1297de7a8b11046ebd6c1c29bdd8c0b"
)
EXPECTED_SOURCE_SHA256 = (
    "f68ecd93e2dee07012d7fda6521fe617775f637fede1da7f3f0cb27a92e6ce73"
)
EXPECTED_QBASIS_SHA256 = (
    "be10e2a72679b2214735c1e71f55dfc331e395a41a0866ecde35b090ca21ba85"
)
EXPECTED_SOURCE_MANIFEST_SHA256 = (
    "baa6f80fd1173165fa36f201c52b6c6f9ec4b1d198ef9169687c5977ffd381e5"
)
EXPECTED_SOURCE_PROVENANCE_SHA256 = (
    "844658183e18445ea49a01e71303782307474072c32b3937a5ebb31058bad322"
)
EXPECTED_SOURCE_PANEL_SHA256 = (
    "688132fc91e3decdb83784e71d4a69c9868e1f2ead740d753c2ca7e538b06f4b"
)
EXPECTED_WEDGE_SHA256 = (
    "9efc7f43498726d7d1b1119e85bf617b24370aa7b2ff9d5127a85859602ca93e"
)
EXPECTED_COMPLEMENT_SHA256 = (
    "15026c80b25c00db6cc530b8ec03319ddbf0e831887e277764e07f752c3ab572"
)
EXPECTED_AUDIT_STATUS_SHA256 = (
    "bc2df46d66ca8bb6ef7df4b366cedfbb1d177585b6bc64fd51e8f2cba84f887a"
)
EXPECTED_HANDOFF_RECEIPT_SHA256 = (
    "2742a98484466babd0d06e7be1b6ca0a2cedce6b858df99812b34ad6f9f86f2c"
)
EXPECTED_CONTRACT_SHA256 = (
    "2f7b898a7670ac96e2f49447e879a2424ce2871c6f4436dcf38c2b4991bbc2c2"
)
EXPECTED_DECISION_INPUT_HASHES = {
    "reviewed_analyzer": "cd6658b8cdd70aed2a597d24ff2b2c1e16fe9b4807dc204e7e8cf1d6a5ba7132",
    "source_manifest": EXPECTED_SOURCE_MANIFEST_SHA256,
    "source_provenance": EXPECTED_SOURCE_PROVENANCE_SHA256,
    "source_twist_panel": EXPECTED_SOURCE_PANEL_SHA256,
    "u40_rows": "81f50b31cffa6581b27f52b9aced792b9d6cacbb64950471594693473194a5d9",
    "u40_summary": "81d45fe4ea75dee1e121dcb22963652c2253cf5e45a61094c3e153f98e4dd5e4",
    "gz_points": "44755fe1c15efce59903044f31ffa0c794da8d9e85f330f89d3683e6ae609c0a",
}

# These are deterministic outputs of the frozen analyzer evaluated on the
# hash-pinned U=40 full-861 controls.  A certificate may not merely *claim* to
# have used those inputs: materialization requires these exact calibration
# values and independently rederives every target decision input from the 300
# source output bytes.
EXPECTED_U40_CALIBRATION = {
    "max_abs_C_NN_panel_minus_full861": 2.6920934537155716e-7,
    "max_abs_bias_to_panel_spread_ratio": 0.008825660518580818,
    "max_abs_bias_to_symmetry_diagnostic_ratio": 0.2683572051938072,
    "max_U40_panel_spread": 5.229141656709624e-5,
    "max_abs_U40_symmetry_weighted_minus_primary": 1.450012748316354e-6,
}

PAIRS = (
    (20, "0"),
    (20, "2"),
    (20, "3"),
    (20, "4"),
    (20, "4.5"),
    (40, "6"),
    (80, "0"),
    (80, "4"),
    (80, "8"),
    (80, "12"),
    (80, "16"),
    (80, "18"),
)
EXPECTED_REUSED_PER_CASE = 25
EXPECTED_COMPLEMENT_PER_CASE = 836
EXPECTED_FULL_PER_CASE = 861
EXPECTED_REUSED_TOTAL = 300
EXPECTED_EXPANSION_TOTAL = 10032
EXPECTED_FULL_TOTAL = 10332
COMPLETE_RE = re.compile(r"(?m)^status\s+COMPLETE\s*$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
FLOAT_REL_TOL = 1.0e-12
FLOAT_ABS_TOL = 1.0e-15


class Refusal(RuntimeError):
    """A safety or provenance condition refused materialization."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_hash(path: Path, expected: str, label: str) -> None:
    if not path.is_file():
        raise Refusal(f"Missing {label}: {path}")
    actual = sha256(path)
    if actual != expected:
        raise Refusal(f"{label} SHA-256 mismatch: actual={actual}, expected={expected}")


def validate_package_ledger() -> None:
    ledger = PACKAGE / "PACKAGE_SHA256SUMS"
    if not ledger.is_file():
        raise Refusal(f"Missing package checksum ledger: {ledger}")
    listed: dict[str, str] = {}
    for line in ledger.read_text().splitlines():
        try:
            digest, relative = line.split("  ", 1)
        except ValueError as exc:
            raise Refusal(f"Malformed package checksum row: {line!r}") from exc
        if not HEX64_RE.fullmatch(digest) or relative in listed:
            raise Refusal(f"Invalid package checksum row: {line!r}")
        listed[relative] = digest
    expected_files = {
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*")
        if path.is_file()
        and path != ledger
        and "__pycache__" not in path.parts
    }
    if set(listed) != expected_files:
        raise Refusal("Package checksum ledger file inventory mismatch")
    for relative, expected in listed.items():
        require_hash(PACKAGE / relative, expected, f"package file {relative}")


def decimal_tag(value: str) -> str:
    return value.replace("-", "m").replace(".", "p")


def result_name(U: int, V: str, kx: int, ky: int) -> str:
    return f"L4x4Nup8Ndn8U{U}V{V}tp0f{kx}x{ky}Q0x0_obs.dat"


def load_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def load_source_manifest(path: Path) -> list[dict[str, str]]:
    require_hash(path, EXPECTED_SOURCE_MANIFEST_SHA256, "source 25 manifest")
    rows = load_tsv(path)
    if len(rows) != EXPECTED_REUSED_TOTAL:
        raise Refusal(f"Source manifest has {len(rows)} rows, expected 300")
    if len({row["index"] for row in rows}) != len(rows):
        raise Refusal("Source manifest indices are not unique")
    if len({row["seed"] for row in rows}) != len(rows):
        raise Refusal("Source manifest seeds are not unique")
    if len({row["result"] for row in rows}) != len(rows):
        raise Refusal("Source manifest result paths are not unique")
    observed_cases = {(int(row["U"]), row["V"]) for row in rows}
    if observed_cases != set(PAIRS):
        raise Refusal("Source manifest does not contain the exact twelve cases")
    expected_twists = source_twists()
    counts = Counter((int(row["U"]), row["V"]) for row in rows)
    if set(counts.values()) != {EXPECTED_REUSED_PER_CASE}:
        raise Refusal("Source manifest does not contain 25 rows per case")
    for pair in PAIRS:
        twists = {
            (int(row["kx"]), int(row["ky"]))
            for row in rows
            if (int(row["U"]), row["V"]) == pair
        }
        if twists != expected_twists:
            raise Refusal(f"Source manifest twist mismatch for U={pair[0]}, V={pair[1]}")
    return rows


def source_twists() -> set[tuple[int, int]]:
    path = PACKAGE / "reviewed_inputs" / "source_25_twist_panel.tsv"
    require_hash(path, EXPECTED_SOURCE_PANEL_SHA256, "reviewed source twist panel")
    rows = load_tsv(path)
    twists = {(int(row["kx"]), int(row["ky"])) for row in rows}
    if len(rows) != 25 or len(twists) != 25:
        raise Refusal("Reviewed source twist panel is not 25 unique coordinates")
    return twists


def load_coordinate_contracts() -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    wedge_path = PACKAGE / "wedge_861.tsv"
    complement_path = PACKAGE / "complement_836.tsv"
    require_hash(wedge_path, EXPECTED_WEDGE_SHA256, "861 wedge contract")
    require_hash(complement_path, EXPECTED_COMPLEMENT_SHA256, "836 complement contract")
    wedge_rows = load_tsv(wedge_path)
    complement_rows = load_tsv(complement_path)
    wedge = [(int(row["kx"]), int(row["ky"])) for row in wedge_rows]
    complement = [(int(row["kx"]), int(row["ky"])) for row in complement_rows]
    reused = source_twists()
    validate_coordinate_contract(reused, wedge, complement)
    wedge_index = {point: index for index, point in enumerate(wedge, 1)}
    for index, row in enumerate(wedge_rows, 1):
        kx, ky = int(row["kx"]), int(row["ky"])
        expected_endpoint = endpoint_weight(kx, ky)
        expected_symmetry = 1 if kx == ky else 2
        if (
            int(row["wedge_index"]) != index
            or (row["reused_in_25"] == "True") != ((kx, ky) in reused)
            or int(row["symmetry_multiplicity"]) != expected_symmetry
            or not math.isclose(float(row["endpoint_weight"]), expected_endpoint)
            or not math.isclose(
                float(row["quadrature_weight"]),
                expected_symmetry * expected_endpoint,
            )
        ):
            raise Refusal(f"Invalid 861 wedge metadata at row {index}")
    for index, row in enumerate(complement_rows, 1):
        point = (int(row["kx"]), int(row["ky"]))
        kx, ky = point
        expected_endpoint = endpoint_weight(kx, ky)
        expected_symmetry = 1 if kx == ky else 2
        if (
            int(row["complement_index"]) != index
            or int(row["wedge_index"]) != wedge_index[point]
            or int(row["symmetry_multiplicity"]) != expected_symmetry
            or not math.isclose(float(row["endpoint_weight"]), expected_endpoint)
            or not math.isclose(
                float(row["quadrature_weight"]),
                expected_symmetry * expected_endpoint,
            )
        ):
            raise Refusal(f"Invalid complement metadata at row {index}")
    if not math.isclose(
        sum(
            (1 if kx == ky else 2) * endpoint_weight(kx, ky)
            for kx, ky in wedge
        ),
        1600.0,
    ):
        raise Refusal("Canonical wedge quadrature weight is not 1600")
    return wedge, complement


def validate_coordinate_contract(
    reused: set[tuple[int, int]],
    wedge: list[tuple[int, int]],
    complement: list[tuple[int, int]],
) -> None:
    expected_wedge = [(kx, ky) for ky in range(41) for kx in range(ky + 1)]
    if wedge != expected_wedge or len(set(wedge)) != EXPECTED_FULL_PER_CASE:
        raise Refusal("861 wedge is not the canonical ordered 0<=kx<=ky<=40 grid")
    if len(reused) != EXPECTED_REUSED_PER_CASE or not reused.issubset(set(wedge)):
        raise Refusal("Reused coordinate set is not an exact 25-point wedge subset")
    if len(complement) != EXPECTED_COMPLEMENT_PER_CASE or len(set(complement)) != len(complement):
        raise Refusal("Complement is not exactly 836 unique coordinates")
    if reused.intersection(complement):
        raise Refusal("Reused and complement coordinate sets collide")
    if reused.union(complement) != set(wedge):
        raise Refusal("Reused and complement coordinates do not reconstruct the 861 wedge")
    expected_complement = [point for point in wedge if point not in reused]
    if complement != expected_complement:
        raise Refusal("Complement ordering differs from canonical wedge order")


def deterministic_seed(
    U: int,
    V: str,
    kx: int,
    ky: int,
    used: set[int],
) -> int:
    nonce = 0
    while True:
        payload = f"{BATCH_NAME}|U={U}|V={V}|f={kx}x{ky}|nonce={nonce}".encode()
        seed = int.from_bytes(hashlib.sha256(payload).digest()[:4], "big") % (2**32 - 1) + 1
        if seed not in used:
            used.add(seed)
            return seed
        nonce += 1


def endpoint_weight(kx: int, ky: int) -> float:
    return (0.5 if kx in (0, 40) else 1.0) * (0.5 if ky in (0, 40) else 1.0)


def build_plan(
    base: Path,
    source_rows: list[dict[str, str]],
    complement: list[tuple[int, int]],
) -> list[dict[str, Any]]:
    source_seeds = {int(row["seed"]) for row in source_rows}
    used_seeds = set(source_seeds)
    source_keys = {
        (int(row["U"]), row["V"], int(row["kx"]), int(row["ky"]))
        for row in source_rows
    }
    source_results = {Path(row["result"]).name for row in source_rows}
    wedge_index = {
        (kx, ky): index
        for index, (kx, ky) in enumerate(
            [(x, y) for y in range(41) for x in range(y + 1)], 1
        )
    }
    rows: list[dict[str, Any]] = []
    for complement_index, (kx, ky) in enumerate(complement, 1):
        for U, V in PAIRS:
            index = len(rows) + 1
            name = result_name(U, V, kx, ky)
            key = (U, V, kx, ky)
            if key in source_keys or name in source_results:
                raise Refusal(f"Expansion/source collision: {key}")
            rows.append(
                {
                    "index": index,
                    "U": U,
                    "V": V,
                    "V_over_U": float(V) / U,
                    "expected_phase": "Mott",
                    "complement_index": complement_index,
                    "wedge_index": wedge_index[(kx, ky)],
                    "kx": kx,
                    "ky": ky,
                    "symmetry_multiplicity": 1 if kx == ky else 2,
                    "endpoint_weight": endpoint_weight(kx, ky),
                    "quadrature_weight": (1 if kx == ky else 2) * endpoint_weight(kx, ky),
                    "seed": deterministic_seed(U, V, kx, ky, used_seeds),
                    "job_name": JOB_NAME,
                    "result": str(base / name),
                    "state_at_generation": "template",
                    "template": "",
                }
            )
    validate_plan(rows, source_rows)
    return rows


def validate_plan(
    rows: list[dict[str, Any]], source_rows: list[dict[str, str]]
) -> None:
    if len(rows) != EXPECTED_EXPANSION_TOTAL:
        raise Refusal(f"Expansion plan has {len(rows)} rows, expected 10032")
    expected_indices = set(range(1, EXPECTED_EXPANSION_TOTAL + 1))
    if {int(row["index"]) for row in rows} != expected_indices:
        raise Refusal("Expansion plan indices are not the exact contiguous range")
    keys = {(row["U"], row["V"], row["kx"], row["ky"]) for row in rows}
    if len(keys) != len(rows):
        raise Refusal("Expansion plan parameter keys collide")
    if len({row["result"] for row in rows}) != len(rows):
        raise Refusal("Expansion result paths collide")
    if len({row["seed"] for row in rows}) != len(rows):
        raise Refusal("Expansion seeds collide")
    if {int(row["seed"]) for row in rows}.intersection(
        int(row["seed"]) for row in source_rows
    ):
        raise Refusal("Expansion seeds collide with reused 25-panel seeds")
    counts = Counter((row["U"], row["V"]) for row in rows)
    if set(counts) != set(PAIRS) or set(counts.values()) != {EXPECTED_COMPLEMENT_PER_CASE}:
        raise Refusal("Expansion plan is not exactly 836 coordinates per case")
    source_keys = {
        (int(row["U"]), row["V"], int(row["kx"]), int(row["ky"]))
        for row in source_rows
    }
    if keys.intersection(source_keys):
        raise Refusal("Expansion plan overlaps a reused source coordinate")
    if len(keys.union(source_keys)) != EXPECTED_FULL_TOTAL:
        raise Refusal("Expansion plus reused coordinates do not total 10,332")


def plan_digest(rows: Iterable[dict[str, Any]]) -> str:
    text = "".join(
        f"{row['index']}\t{row['U']}\t{row['V']}\t{row['kx']}\t{row['ky']}\t"
        f"{row['seed']}\t{Path(str(row['result'])).name}\n"
        for row in rows
    )
    return hashlib.sha256(text.encode()).hexdigest()


def template_hash_ledger_text(paths: Iterable[Path]) -> str:
    entries = sorted((path.name, sha256(path)) for path in paths)
    if len(entries) != len({name for name, _ in entries}):
        raise Refusal("Template basenames collide while building the content ledger")
    return "".join(f"{digest}  {name}\n" for name, digest in entries)


def load_template_hash_ledger(
    path: Path, expected_sha256: str, expected_count: int = EXPECTED_EXPANSION_TOTAL
) -> dict[str, str]:
    require_hash(path, expected_sha256, "template content-hash ledger")
    entries: dict[str, str] = {}
    for line in path.read_text().splitlines():
        try:
            digest, name = line.split("  ", 1)
        except ValueError as exc:
            raise Refusal(f"Malformed template content-hash row: {line!r}") from exc
        if not HEX64_RE.fullmatch(digest) or name in entries or Path(name).name != name:
            raise Refusal(f"Invalid template content-hash row: {line!r}")
        entries[name] = digest
    if len(entries) != expected_count:
        raise Refusal(
            f"Template content-hash ledger has {len(entries)} rows, expected {expected_count}"
        )
    return entries


def current_template_inventory(batch: Path) -> dict[str, Path]:
    current: dict[str, Path] = {}
    for path in sorted((batch / "templates").glob(TEMPLATE_PREFIX + "*.sh")):
        if path.name in current:
            raise Refusal(f"Duplicate pending template basename: {path.name}")
        current[path.name] = path
    for path in sorted((batch / "submitted").glob(TEMPLATE_PREFIX + "*.template")):
        original_name = path.stem + ".sh"
        if original_name in current:
            raise Refusal(f"Template exists as both pending and submitted: {original_name}")
        current[original_name] = path
    return current


def validate_materialized_static_integrity(
    *,
    batch: Path,
    expected_manifest_sha256: str,
    expected_plan_sha256: str,
    expected_template_ledger_sha256: str,
    expected_template_count: int = EXPECTED_EXPANSION_TOTAL,
) -> None:
    """Verify immutable plan and template bytes before a submission is possible."""

    manifest = batch / "manifest.tsv"
    require_hash(manifest, expected_manifest_sha256, "materialized manifest")
    rows = load_tsv(manifest)
    if len(rows) != expected_template_count:
        raise Refusal(
            f"Materialized manifest has {len(rows)} rows, expected {expected_template_count}"
        )
    if plan_digest(rows) != expected_plan_sha256:
        raise Refusal("Materialized manifest plan digest mismatch")
    expected_templates = load_template_hash_ledger(
        batch / "TEMPLATE_SHA256SUMS",
        expected_template_ledger_sha256,
        expected_template_count,
    )
    current = current_template_inventory(batch)
    if set(current) != set(expected_templates):
        missing = sorted(set(expected_templates) - set(current))
        extra = sorted(set(current) - set(expected_templates))
        raise Refusal(
            "Materialized template inventory mismatch: "
            f"missing={missing[:3]}, extra={extra[:3]}"
        )
    for name, path in current.items():
        require_hash(path, expected_templates[name], f"template content {name}")


def validate_decision_certificate(path: Path) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        raise Refusal(f"Missing decision certificate: {path}")
    payload = json.loads(path.read_text())
    if payload.get("decision") != "APPROVE_EXPANSION" or payload.get("approved") is not True:
        raise Refusal("Decision certificate does not approve expansion")
    if payload.get("schema_version") != 2:
        raise Refusal("Decision certificate schema mismatch")
    if payload.get("gate_algorithm") != "fig4_cnn_25_to_861_quadrature_v2":
        raise Refusal("Decision certificate uses an unexpected gate algorithm")
    expected_thresholds = {
        "calibration_safety_factor": 5.0,
        "absolute_propagated_s_tolerance": 5.0e-4,
        "roughness_exit_multiplier": 4.0,
        "symmetry_diagnostic_exit_multiplier": 4.0,
    }
    if payload.get("thresholds") != expected_thresholds:
        raise Refusal("Decision certificate threshold contract mismatch")
    methodology = payload.get("methodology", {})
    if (
        methodology.get("decision_observable") != "dimensionless signed s_NN"
        or methodology.get("eq10_residual_used_for_decision") is not False
        or methodology.get("gz_curve_fit_rmse_used_for_decision") is not False
    ):
        raise Refusal("Decision certificate methodology contract mismatch")
    if payload.get("input_sha256") != EXPECTED_DECISION_INPUT_HASHES:
        raise Refusal("Decision certificate input-hash contract mismatch")
    contract = payload.get("expansion_contract", {})
    expected_contract = {
        "cases": [{"U": float(U), "V": float(V)} for U, V in PAIRS],
        "reused_coordinates_per_case": 25,
        "missing_coordinates_per_case": 836,
        "expansion_target_count": 10032,
        "full_coordinates_per_case": 861,
        "wedge_sha256": EXPECTED_WEDGE_SHA256,
        "complement_sha256": EXPECTED_COMPLEMENT_SHA256,
        "package_contract_sha256": EXPECTED_CONTRACT_SHA256,
    }
    if contract != expected_contract:
        raise Refusal("Decision certificate expansion contract mismatch")
    runtime = payload.get("expected_runtime_provenance", {})
    if runtime.get("solver_sha256") != EXPECTED_SOLVER_SHA256:
        raise Refusal("Decision certificate solver hash mismatch")
    if runtime.get("source_sha256") != EXPECTED_SOURCE_SHA256:
        raise Refusal("Decision certificate source hash mismatch")
    if runtime.get("qbasis_library_sha256") != EXPECTED_QBASIS_SHA256:
        raise Refusal("Decision certificate libqbasis hash mismatch")
    source_pins = payload.get("source_pinned_solver", {})
    if source_pins != {
        "solver_sha256": EXPECTED_SOLVER_SHA256,
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "qbasis_library_sha256": EXPECTED_QBASIS_SHA256,
    }:
        raise Refusal("Decision certificate source pinned-runtime mismatch")
    inventory = payload.get("source_raw_inventory", {})
    digest = str(inventory.get("ordered_filename_sha256_digest", ""))
    if inventory.get("count") != 300 or not HEX64_RE.fullmatch(digest):
        raise Refusal("Decision certificate lacks an exact 300-result source digest")
    if inventory.get("all_status_complete") is not True:
        raise Refusal("Decision certificate source inventory is not COMPLETE")
    if (
        float(inventory.get("max_abs_identity_residual", math.inf)) > 1.0e-8
        or float(inventory.get("identity_tolerance", math.inf)) != 1.0e-8
    ):
        raise Refusal("Decision certificate source identity validation mismatch")
    calibration = payload.get("calibration", {})
    try:
        max_abs_bias = float(calibration["max_abs_C_NN_panel_minus_full861"])
        max_bias_to_spread = float(
            calibration["max_abs_bias_to_panel_spread_ratio"]
        )
        max_bias_to_symmetry = float(
            calibration["max_abs_bias_to_symmetry_diagnostic_ratio"]
        )
        max_u40_spread = float(calibration["max_U40_panel_spread"])
        max_u40_symmetry = float(
            calibration["max_abs_U40_symmetry_weighted_minus_primary"]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise Refusal("Decision certificate U40 calibration is incomplete") from exc
    calibration_numbers = (
        max_abs_bias,
        max_bias_to_spread,
        max_bias_to_symmetry,
        max_u40_spread,
        max_u40_symmetry,
    )
    if not all(math.isfinite(value) and value > 0.0 for value in calibration_numbers):
        raise Refusal("Decision certificate U40 calibration is non-finite")
    if (
        calibration.get("control_count") != 4
        or max_abs_bias > 1.0e-6
        or calibration.get("empirical_calibration_is_not_a_formal_bound") is not True
    ):
        raise Refusal("Decision certificate U40 calibration mismatch")
    observed_calibration = {
        "max_abs_C_NN_panel_minus_full861": max_abs_bias,
        "max_abs_bias_to_panel_spread_ratio": max_bias_to_spread,
        "max_abs_bias_to_symmetry_diagnostic_ratio": max_bias_to_symmetry,
        "max_U40_panel_spread": max_u40_spread,
        "max_abs_U40_symmetry_weighted_minus_primary": max_u40_symmetry,
    }
    for key, expected in EXPECTED_U40_CALIBRATION.items():
        if not math.isclose(
            observed_calibration[key],
            expected,
            rel_tol=FLOAT_REL_TOL,
            abs_tol=FLOAT_ABS_TOL,
        ):
            raise Refusal(
                "Decision certificate does not contain the exact hash-pinned "
                f"U40 calibration: {key}={observed_calibration[key]:.17g}, "
                f"expected={expected:.17g}"
            )

    targets = payload.get("targets")
    if not isinstance(targets, list) or len(targets) != 12:
        raise Refusal("Decision certificate target inventory mismatch")
    try:
        observed_cases = {
            (round(float(row["U"]), 10), round(float(row["V"]), 10))
            for row in targets
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise Refusal("Decision certificate target cases are malformed") from exc
    expected_cases = {(float(U), float(V)) for U, V in PAIRS}
    if observed_cases != expected_cases:
        raise Refusal("Decision certificate does not cover the exact twelve cases")

    slope_count = 0
    roughness_count = 0
    symmetry_count = 0
    delta_s_values: list[float] = []
    roughness_values: list[float] = []
    symmetry_values: list[float] = []
    for row in targets:
        if "gz_fit_rmse" in row or "material_scale_max_residual_or_rmse" in row:
            raise Refusal("Decision target improperly uses GZ curve-fit RMSE")
        try:
            U = float(row["U"])
            V = float(row["V"])
            spread = float(row["C_NN_panel_spread"])
            symmetry = float(
                row["abs_C_NN_symmetry_weighted_minus_primary"]
            )
            components = row["C_NN_bias_components_before_safety_factor"]
            c_bias = float(row["conservative_C_NN_bias_envelope"])
            ds_dcnn = float(row["abs_ds_NN_dC_NN"])
            delta_s = float(row["conservative_abs_delta_s_NN"])
            signed_residual = float(
                row[
                    "secondary_eq10_residual_signed_observed_minus_prediction"
                ]
            )
            abs_residual = float(row["secondary_abs_eq10_residual"])
        except (KeyError, TypeError, ValueError) as exc:
            raise Refusal("Decision certificate target metrics are malformed") from exc
        numeric = (
            U,
            V,
            spread,
            symmetry,
            c_bias,
            ds_dcnn,
            delta_s,
            signed_residual,
            abs_residual,
        )
        if not all(math.isfinite(value) for value in numeric):
            raise Refusal("Decision certificate target metrics are non-finite")
        if min(spread, symmetry, c_bias, ds_dcnn, delta_s, abs_residual) < 0.0:
            raise Refusal("Decision certificate target metrics are negative")

        expected_components = {
            "U40_absolute_bias_floor": max_abs_bias,
            "range_scaled_transfer": max_bias_to_spread * spread,
            "symmetry_scaled_transfer": max_bias_to_symmetry * symmetry,
        }
        if not isinstance(components, dict) or set(components) != set(
            expected_components
        ):
            raise Refusal("Decision certificate C_NN bias components mismatch")
        for key, expected in expected_components.items():
            if not math.isclose(
                float(components[key]), expected, rel_tol=1.0e-12, abs_tol=1.0e-15
            ):
                raise Refusal("Decision certificate C_NN bias transfer mismatch")
        expected_c_bias = 5.0 * max(expected_components.values())
        expected_ds_dcnn = abs(2.0 * (2.0 * U - V) / (U - V))
        expected_delta_s = expected_ds_dcnn * expected_c_bias
        expected_roughness = spread / max_u40_spread
        expected_symmetry_ratio = symmetry / max_u40_symmetry
        checks = (
            (c_bias, expected_c_bias),
            (ds_dcnn, expected_ds_dcnn),
            (delta_s, expected_delta_s),
            (float(row["calibrated_roughness_ratio"]), expected_roughness),
            (
                float(row["calibrated_symmetry_diagnostic_ratio"]),
                expected_symmetry_ratio,
            ),
            (abs_residual, abs(signed_residual)),
        )
        if not all(
            math.isclose(actual, expected, rel_tol=1.0e-12, abs_tol=1.0e-15)
            for actual, expected in checks
        ):
            raise Refusal("Decision certificate propagated target metric mismatch")

        expected_slope = delta_s >= 5.0e-4
        expected_rough_exit = expected_roughness > 4.0
        expected_symmetry_exit = expected_symmetry_ratio > 4.0
        if (
            row.get("exceeds_absolute_s_tolerance") is not expected_slope
            or row.get("exits_roughness_calibrated_domain")
            is not expected_rough_exit
            or row.get("exits_symmetry_calibrated_domain")
            is not expected_symmetry_exit
            or row.get("eq10_residual_used_for_decision") is not False
        ):
            raise Refusal("Decision certificate target trigger mismatch")
        secondary_ratio = row.get(
            "secondary_abs_delta_s_to_abs_eq10_residual_ratio"
        )
        if abs_residual == 0.0:
            if secondary_ratio is not None:
                raise Refusal("Decision certificate zero-residual diagnostic mismatch")
        elif not math.isclose(
            float(secondary_ratio),
            delta_s / abs_residual,
            rel_tol=1.0e-12,
            abs_tol=1.0e-15,
        ):
            raise Refusal("Decision certificate Eq.10 secondary diagnostic mismatch")

        slope_count += int(expected_slope)
        roughness_count += int(expected_rough_exit)
        symmetry_count += int(expected_symmetry_exit)
        delta_s_values.append(delta_s)
        roughness_values.append(expected_roughness)
        symmetry_values.append(expected_symmetry_ratio)

    diagnostics = payload.get("quadrature_diagnostics", {})
    expected_counts = {
        "target_count": 12,
        "slope_tolerance_exceedance_count": slope_count,
        "roughness_calibrated_domain_exit_count": roughness_count,
        "symmetry_calibrated_domain_exit_count": symmetry_count,
    }
    if any(diagnostics.get(key) != value for key, value in expected_counts.items()):
        raise Refusal("Decision certificate quadrature counts mismatch")
    summary_checks = (
        (diagnostics.get("max_conservative_abs_delta_s_NN"), max(delta_s_values)),
        (diagnostics.get("max_target_roughness_ratio"), max(roughness_values)),
        (
            diagnostics.get("max_target_symmetry_diagnostic_ratio"),
            max(symmetry_values),
        ),
    )
    try:
        summaries_match = all(
            math.isclose(
                float(actual), expected, rel_tol=1.0e-12, abs_tol=1.0e-15
            )
            for actual, expected in summary_checks
        )
    except (TypeError, ValueError):
        summaries_match = False
    if not summaries_match:
        raise Refusal("Decision certificate quadrature summary mismatch")

    secondary = payload.get("secondary_eq10_diagnostics", {})
    if (
        secondary.get("used_for_decision") is not False
        or secondary.get("residual_units") != "dimensionless signed s_NN"
    ):
        raise Refusal("Decision certificate Eq.10 residual role mismatch")
    if not (slope_count or roughness_count or symmetry_count):
        raise Refusal(
            "Decision certificate says APPROVE but its quantitative metrics do not"
        )
    return payload, sha256(path)


def validate_source_results(
    rows: list[dict[str, str]], base: Path, expected_digest: str
) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    for row in rows:
        name = result_name(
            int(row["U"]), row["V"], int(row["kx"]), int(row["ky"])
        )
        path = Path(row["result"])
        expected_path = base / name
        if path != expected_path:
            raise Refusal(f"Source result path mismatch: {path} != {expected_path}")
        if not path.is_file():
            raise Refusal(f"Missing reused source output: {path}")
        text = path.read_text(errors="replace")
        if not COMPLETE_RE.search(text):
            raise Refusal(f"Reused source output is not COMPLETE: {path}")
        values: dict[str, str] = {}
        for line in text.splitlines():
            fields = line.split(None, 1)
            if len(fields) == 2:
                values[fields[0]] = fields[1].strip()
        try:
            C_NN = float(values["<C1_NN>"])
        except (KeyError, ValueError) as exc:
            raise Refusal(f"Invalid <C1_NN> in reused source output: {path}") from exc
        if not math.isfinite(C_NN) or not (-0.75 - 1.0e-10 <= C_NN < 0.0):
            raise Refusal(f"Non-Mott/unphysical <C1_NN> in reused source output: {path}")
        inventory.append(
            {
                "index": int(row["index"]),
                "U": int(row["U"]),
                "V": row["V"],
                "kx": int(row["kx"]),
                "ky": int(row["ky"]),
                "seed": int(row["seed"]),
                "filename": name,
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
                "C_NN": C_NN,
            }
        )
    actual_digest = hashlib.sha256(
        "".join(
            f"{row['filename']}\t{row['sha256']}\n"
            for row in sorted(inventory, key=lambda item: item["filename"])
        ).encode()
    ).hexdigest()
    if actual_digest != expected_digest:
        raise Refusal(
            "Remote reused-result digest differs from the approved 25-panel certificate: "
            f"actual={actual_digest}, expected={expected_digest}"
        )
    return inventory


def validate_source_decision_inputs(
    decision: dict[str, Any],
    source_rows: list[dict[str, str]],
    source_inventory: list[dict[str, Any]],
) -> dict[str, Any]:
    """Bind all decision-driving target metrics to the exact 300 raw bytes.

    The decision certificate's raw inventory digest is necessary but not
    sufficient by itself because a hand-authored certificate could self-assert
    any 64-hex digest.  Materialization therefore rederives the two target
    quantities that enter the gate (panel range and symmetry-weighting
    diagnostic) directly from the exact output files whose bytes just matched
    that digest.  The remaining target quantities and triggers are already
    independently regenerated by :func:`validate_decision_certificate`.
    """

    if len(source_rows) != EXPECTED_REUSED_TOTAL or len(source_inventory) != EXPECTED_REUSED_TOTAL:
        raise Refusal("Cannot rederive decision inputs without exactly 300 source rows")
    inventory_by_index = {int(row["index"]): row for row in source_inventory}
    if len(inventory_by_index) != EXPECTED_REUSED_TOTAL:
        raise Refusal("Source decision-input inventory indices are not unique")
    target_by_case = {
        (round(float(row["U"]), 10), round(float(row["V"]), 10)): row
        for row in decision.get("targets", [])
    }
    if set(target_by_case) != {(float(U), float(V)) for U, V in PAIRS}:
        raise Refusal("Decision target inventory changed before source revalidation")

    groups: dict[tuple[float, float], list[tuple[int, int, float]]] = {}
    for row in source_rows:
        index = int(row["index"])
        inventory = inventory_by_index.get(index)
        if inventory is None:
            raise Refusal(f"Source decision-input inventory lacks index {index}")
        case = (round(float(row["U"]), 10), round(float(row["V"]), 10))
        groups.setdefault(case, []).append(
            (int(row["kx"]), int(row["ky"]), float(inventory["C_NN"]))
        )

    rederived: list[dict[str, Any]] = []
    for case in sorted(groups):
        values = groups[case]
        if len(values) != EXPECTED_REUSED_PER_CASE or len(
            {(kx, ky) for kx, ky, _ in values}
        ) != EXPECTED_REUSED_PER_CASE:
            raise Refusal(f"Source decision-input panel is incomplete at case {case}")
        C = [value for _, _, value in values]
        primary = sum(C) / len(C)
        symmetry_weights = [1.0 if kx == ky else 2.0 for kx, ky, _ in values]
        symmetry_weighted = sum(
            weight * value
            for weight, (_, _, value) in zip(symmetry_weights, values)
        ) / sum(symmetry_weights)
        spread = max(C) - min(C)
        symmetry_diagnostic = abs(symmetry_weighted - primary)
        target = target_by_case[case]
        checks = {
            "C_NN_panel_spread": spread,
            "abs_C_NN_symmetry_weighted_minus_primary": symmetry_diagnostic,
        }
        for key, expected in checks.items():
            try:
                observed = float(target[key])
            except (KeyError, TypeError, ValueError) as exc:
                raise Refusal(f"Decision target lacks source-derived {key} at {case}") from exc
            if not math.isclose(
                observed,
                expected,
                rel_tol=FLOAT_REL_TOL,
                abs_tol=FLOAT_ABS_TOL,
            ):
                raise Refusal(
                    "Decision target metric differs from the exact 300 source bytes: "
                    f"case={case}, {key}={observed:.17g}, expected={expected:.17g}"
                )
        rederived.append(
            {
                "U": case[0],
                "V": case[1],
                "C_NN_primary": primary,
                "C_NN_panel_spread": spread,
                "abs_C_NN_symmetry_weighted_minus_primary": symmetry_diagnostic,
            }
        )

    canonical = json.dumps(rederived, sort_keys=True, separators=(",", ":"))
    return {
        "case_count": len(rederived),
        "source_decision_inputs_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "all_decision_driving_target_metrics_match_source_bytes": True,
    }


def active_source_jobs() -> list[str]:
    proc = subprocess.run(
        ["squeue", "-h", "-r", "-u", os.environ.get("USER", ""), "-o", "%i|%j|%a|%T"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode:
        raise Refusal(f"squeue failed during materialization: {proc.stderr.strip()}")
    active = []
    for line in proc.stdout.splitlines():
        fields = [item.strip() for item in line.split("|")]
        if len(fields) == 4 and fields[1] in {"F4CNN25", "F4CNN25R", JOB_NAME, REPAIR_JOB_NAME}:
            active.append(line)
    return active


def make_executable(path: Path) -> None:
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)


def template_text(
    row: dict[str, Any], batch: Path, base: Path, solver: Path, qbasis: Path
) -> str:
    result = Path(str(row["result"]))
    return f"""#!/bin/bash
#SBATCH -A __ACCOUNT__
#SBATCH -p burst
#SBATCH -N 1
#SBATCH -n 32
#SBATCH -c 1
#SBATCH -J {JOB_NAME}
#SBATCH --mem=100G
#SBATCH -t 08:00:00
#SBATCH --signal=B:TERM@120
#SBATCH -o {batch}/logs/%x-%j.out
#SBATCH -e {batch}/logs/%x-%j.err

set -Eeuo pipefail
umask 077
BATCH='{batch}'
BASE='{base}'
SOLVER='{solver}'
EXPECTED_SOLVER_SHA256='{EXPECTED_SOLVER_SHA256}'
PINNED_LIBQBASIS='{qbasis}'
EXPECTED_QBASIS_SHA256='{EXPECTED_QBASIS_SHA256}'
INDEX='{row['index']}'
U='{row['U']}'
V='{row['V']}'
KX='{row['kx']}'
KY='{row['ky']}'
SEED='{row['seed']}'
RESULT_NAME='{result.name}'
RESULT="${{BASE}}/${{RESULT_NAME}}"
WORK="${{BATCH}}/work/task_${{INDEX}}_${{SLURM_JOB_ID:-manual}}"
LOCK="${{BATCH}}/locks/${{RESULT_NAME}}.lock"

refill() {{
  if [[ "${{{CHAIN_ENV}:-NO}}" == YES && "${{{CONFIRM_ENV}:-NO}}" == YES ]]; then
    /usr/bin/python3.11 "${{BATCH}}/submit_fill.py" --submit --one \
      --account "${{SLURM_JOB_ACCOUNT:-ccsd}}" \
      --submission-kind chain_refill \
      --action-id "slurm-${{SLURM_JOB_ID:-unknown}}" || true
  fi
}}
trap refill EXIT
trap 'exit 143' TERM INT

mkdir -p "${{WORK}}"
exec 9>"${{LOCK}}"
flock -x 9
if [[ -s "${{RESULT}}" ]] && grep -Eq '^status[[:space:]]+COMPLETE$' "${{RESULT}}"; then
  echo '{JOB_NAME}_RESULT ALREADY_COMPLETE index={row['index']} U={row['U']} V={row['V']} kx={row['kx']} ky={row['ky']}'
  exit 0
fi
if [[ -e "${{RESULT}}" ]]; then
  echo '{JOB_NAME}_RESULT CONFLICT_INCOMPLETE index={row['index']} path='"${{RESULT}}" >&2
  exit 92
fi
[[ "$(sha256sum "${{SOLVER}}" | awk '{{print $1}}')" == "${{EXPECTED_SOLVER_SHA256}}" ]] || exit 96
[[ "$(sha256sum "${{PINNED_LIBQBASIS}}" | awk '{{print $1}}')" == "${{EXPECTED_QBASIS_SHA256}}" ]] || exit 97

cd "${{WORK}}"
ln -sfn "${{SOLVER}}" ./Hubbard_sym_testobs_UV.x
export OMP_NUM_THREADS=32
export MKL_NUM_THREADS=32
export QBASIS_LANCZOS_SEED="${{SEED}}"
export LD_LIBRARY_PATH={batch}/pinned_solver:/home/9pm/installs/lib:/home/9pm/intel/oneapi/mkl/2024.2/lib/intel64:/home/9pm/intel/oneapi/tbb/latest/lib:/sw/cades-open/gcc/12.2.0/lib64:${{LD_LIBRARY_PATH:-}}
resolved_qbasis="$(ldd "${{SOLVER}}" | awk '$1=="libqbasis.so" {{print $3}}')"
[[ "$(readlink -f "${{resolved_qbasis}}")" == "$(readlink -f "${{PINNED_LIBQBASIS}}")" ]] || exit 98

set +e
time ./Hubbard_sym_testobs_UV.x 8 8 "${{KX}}" "${{KY}}" 0 0 "${{U}}" "${{V}}" 0
job_rc=$?
set -e
LOCAL_RESULT="${{WORK}}/${{RESULT_NAME}}"
if (( job_rc != 0 )) || [[ ! -s "${{LOCAL_RESULT}}" ]] || ! grep -Eq '^status[[:space:]]+COMPLETE$' "${{LOCAL_RESULT}}"; then
  echo '{JOB_NAME}_RESULT FAILED rc='"${{job_rc}}"' index={row['index']} U={row['U']} V={row['V']} kx={row['kx']} ky={row['ky']} seed={row['seed']}' >&2
  (( job_rc == 0 )) && job_rc=90
  exit "${{job_rc}}"
fi
if [[ -s "${{RESULT}}" ]] && grep -Eq '^status[[:space:]]+COMPLETE$' "${{RESULT}}"; then
  echo '{JOB_NAME}_RESULT DUPLICATE_COMPLETE index={row['index']}'
  exit 0
fi
[[ ! -e "${{RESULT}}" ]] || exit 93
INSTALL_TMP="${{RESULT}}.install.${{SLURM_JOB_ID:-manual}}.tmp"
cp -p "${{LOCAL_RESULT}}" "${{INSTALL_TMP}}"
grep -Eq '^status[[:space:]]+COMPLETE$' "${{INSTALL_TMP}}"
mv "${{INSTALL_TMP}}" "${{RESULT}}"
echo '{JOB_NAME}_RESULT COMPLETE index={row['index']} U={row['U']} V={row['V']} kx={row['kx']} ky={row['ky']} seed={row['seed']}'
"""


def submit_helper_text(
    batch: Path,
    decision_hash: str,
    plan_sha: str,
    manifest_sha: str,
    template_ledger_sha: str,
    preflight_sha: str,
    *,
    expected_template_count: int = EXPECTED_EXPANSION_TOTAL,
    expected_solver_sha: str = EXPECTED_SOLVER_SHA256,
    expected_source_sha: str = EXPECTED_SOURCE_SHA256,
    expected_qbasis_sha: str = EXPECTED_QBASIS_SHA256,
) -> str:
    return f'''#!/usr/bin/python3.11
import argparse, csv, fcntl, hashlib, io, json, os, re, subprocess, sys
from collections import defaultdict
from pathlib import Path
BATCH=Path(r"{batch}")
PREFIX="{TEMPLATE_PREFIX}"
CONFIRM_ENV="{CONFIRM_ENV}"
EXPECTED_CASES={tuple((str(U), V) for U, V in PAIRS)!r}
HANDOFF_KINDS={{"initial_launch","rebalance_10m","rebalance_20m"}}
SUBMISSION_KINDS=HANDOFF_KINDS|{{"chain_refill","heartbeat_refill"}}
EXPECTED_DECISION_SHA256="{decision_hash}"
EXPECTED_PLAN_SHA256="{plan_sha}"
EXPECTED_MANIFEST_SHA256="{manifest_sha}"
EXPECTED_TEMPLATE_LEDGER_SHA256="{template_ledger_sha}"
EXPECTED_PREFLIGHT_SHA256="{preflight_sha}"
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()
def checked_bytes(path,expected,label):
    data=path.read_bytes()
    actual=hashlib.sha256(data).hexdigest()
    if actual!=expected: raise SystemExit(label+" hash mismatch: "+actual)
    return data
def template_hashes():
    data=checked_bytes(BATCH/"TEMPLATE_SHA256SUMS",EXPECTED_TEMPLATE_LEDGER_SHA256,"template ledger")
    out={{}}
    for line in data.decode().splitlines():
        fields=line.split("  ",1)
        if len(fields)!=2 or not re.fullmatch(r"[0-9a-f]{{64}}",fields[0]) or fields[1] in out:
            raise SystemExit("malformed template content-hash ledger")
        out[fields[1]]=fields[0]
    if len(out)!={expected_template_count}: raise SystemExit("template content-hash count mismatch")
    return out
def template_index(path):
    match=re.match(r"^"+re.escape(PREFIX)+r"(\\d{{5}})_",path.name)
    if not match: raise SystemExit("malformed template basename: "+path.name)
    return str(int(match.group(1)))
def interleaved_templates(templates,manifest):
    groups=defaultdict(list)
    for index,row in manifest.items():
        case=(row["U"],row["V"])
        if case not in EXPECTED_CASES: raise SystemExit("manifest has unexpected physics case: "+repr(case))
        groups[case].append(int(index))
    for values in groups.values(): values.sort()
    full_order=[]
    depth=max((len(values) for values in groups.values()),default=0)
    for position in range(depth):
        for case in EXPECTED_CASES:
            values=groups.get(case,())
            if position<len(values): full_order.append(str(values[position]))
    available={{template_index(path):path for path in templates}}
    if len(available)!=len(templates): raise SystemExit("available template index collision")
    ordered=[available[index] for index in full_order if index in available]
    if len(ordered)!=len(templates) or len({{path.name for path in ordered}})!=len(templates):
        raise SystemExit("interleaved template selection cardinality mismatch")
    return ordered
def parse():
    p=argparse.ArgumentParser()
    p.add_argument("--account",choices=("ccsd","cnms"),default="ccsd")
    p.add_argument("--submit",action="store_true")
    p.add_argument("--submission-kind",choices=sorted(SUBMISSION_KINDS))
    p.add_argument("--action-id")
    p.add_argument("--expected-indices")
    quantity=p.add_mutually_exclusive_group()
    quantity.add_argument("--one",action="store_true")
    quantity.add_argument("--limit",type=int)
    return p.parse_args()
args=parse()
if (BATCH/"MATERIALIZATION_INCOMPLETE").exists():
    raise SystemExit("Submission refused: materialization-incomplete marker exists")
if args.limit is not None and args.limit < 1:
    raise SystemExit("--limit must be a positive integer")
if args.submit:
    if not args.submission_kind or not args.action_id:
        raise SystemExit("submission requires --submission-kind and --action-id")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{{1,128}}",args.action_id):
        raise SystemExit("invalid --action-id")
    if args.submission_kind in HANDOFF_KINDS and not re.fullmatch(r"[0-9a-f]{{64}}",args.action_id):
        raise SystemExit("handoff submission action id must be the 64-hex policy-state digest")
    if args.submission_kind in HANDOFF_KINDS and not args.expected_indices:
        raise SystemExit("handoff submission requires --expected-indices from the policy state")
    if args.submission_kind not in HANDOFF_KINDS and args.expected_indices:
        raise SystemExit("only a handoff submission may use --expected-indices")
elif args.submission_kind or args.action_id or args.expected_indices:
    raise SystemExit("dry run does not accept submission action metadata")
cap=int(os.environ.get("F4CNN861X_"+args.account.upper()+"_USER_CAP","150"))
if cap<1: raise SystemExit("account cap must be a positive integer")
def queue_inventory():
    templates=sorted((BATCH/"templates").glob(PREFIX+"*.sh"))
    out=subprocess.run(["squeue","-h","-r","-u",os.environ["USER"],"-o","%a"],text=True,capture_output=True,check=True).stdout
    current=sum(line.strip()==args.account for line in out.splitlines())
    slots=max(0,cap-current)
    requested=1 if args.one else (args.limit if args.limit is not None else len(templates))
    limit=min(slots,len(templates),requested)
    return templates,current,limit
lock=(BATCH/".queue.lock").open("a+")
fcntl.flock(lock,fcntl.LOCK_EX)
checked_bytes(BATCH/"preflight.py",EXPECTED_PREFLIGHT_SHA256,"preflight")
manifest_bytes=checked_bytes(BATCH/"manifest.tsv",EXPECTED_MANIFEST_SHA256,"manifest")
ledger=template_hashes()
provenance=json.loads((BATCH/"provenance.json").read_text())
if provenance.get("plan_sha256")!=EXPECTED_PLAN_SHA256: raise SystemExit("provenance plan hash mismatch")
preflight=subprocess.run([sys.executable,str(BATCH/"preflight.py")],text=True,capture_output=True)
if preflight.returncode:
    raise SystemExit("PREFLIGHT REFUSED BEFORE SBATCH\\n"+preflight.stdout+preflight.stderr)
templates,current,limit=queue_inventory()
manifest={{row["index"]:row for row in csv.DictReader(io.StringIO(manifest_bytes.decode()),delimiter="\t")}}
with (BATCH/"submission.tsv").open(newline="") as handle:
    existing_submissions=list(csv.DictReader(handle,delimiter="\t"))
if args.submit and any(row.get("action_id")==args.action_id for row in existing_submissions):
    raise SystemExit("submission action id already exists in the immutable ledger")
templates=interleaved_templates(templates,manifest)
selected=templates[:limit]
if not args.submit:
    print(f"DRY RUN ONLY account={{args.account}} current={{current}} cap={{cap}} templates={{len(templates)}} would_submit={{limit}} selection=interleaved")
    for path in selected: print("WOULD_SBATCH",path)
    raise SystemExit(0)
if os.environ.get(CONFIRM_ENV)!="YES":
    raise SystemExit("Submission disarmed; also set "+CONFIRM_ENV+"=YES")
if sha(BATCH/"decision_certificate.json")!=EXPECTED_DECISION_SHA256:
    raise SystemExit("Decision certificate hash mismatch")
if sha(BATCH/"pinned_solver/Hubbard_sym_testobs_UV.x")!="{expected_solver_sha}": raise SystemExit("solver hash mismatch")
if sha(BATCH/"pinned_solver/Hubbard_sym_testobs_UV.cc")!="{expected_source_sha}": raise SystemExit("source hash mismatch")
if sha(BATCH/"pinned_solver/libqbasis.so")!="{expected_qbasis_sha}": raise SystemExit("libqbasis hash mismatch")
expected_indices=[item for item in (args.expected_indices or "").split(",") if item]
if args.submission_kind in HANDOFF_KINDS:
    if not all(item.isdigit() and str(int(item))==item for item in expected_indices):
        raise SystemExit("invalid canonical --expected-indices list")
    selected_indices=[template_index(path) for path in selected]
    if selected_indices!=expected_indices:
        raise SystemExit("live interleaved selection differs from policy-state expected indices")
submitted=0
for selection_rank,template in enumerate(selected,1):
    base=template.name
    content=template.read_bytes()
    if hashlib.sha256(content).hexdigest()!=ledger.get(base):
        raise SystemExit("selected template content hash mismatch: "+str(template))
    run=BATCH/"submitted"/(template.stem+"_"+args.account+".sh")
    claim=BATCH/"submitted"/(template.stem+".claim")
    archive=BATCH/"submitted"/(template.stem+".template")
    text=content.decode().replace("#SBATCH -A __ACCOUNT__","#SBATCH -A "+args.account)
    index_match=re.search(r"^INDEX='(\\d+)'$",text,re.M)
    if not index_match or index_match.group(1) not in manifest:
        raise SystemExit("selected template index does not match the pinned manifest")
    index=index_match.group(1)
    row=manifest[index]
    if run.exists() or claim.exists() or archive.exists():
        raise SystemExit("submitted-path collision for "+str(template))
    template.rename(claim)
    run.write_text(text); run.chmod(0o700)
    syntax=subprocess.run(["bash","-n",str(run)],text=True,capture_output=True)
    if syntax.returncode:
        run.unlink(); claim.rename(template)
        raise SystemExit("selected template syntax failure: "+syntax.stderr)
    proc=subprocess.run(["sbatch",str(run)],text=True,capture_output=True)
    if proc.returncode:
        run.unlink(); claim.rename(template)
        raise SystemExit(proc.stdout+proc.stderr)
    match=re.search(r"Submitted batch job (\\d+)",proc.stdout)
    if not match:
        raise SystemExit("unparsed sbatch output; template remains claimed to prevent duplicate: "+proc.stdout)
    claim.rename(archive)
    with (BATCH/"submission.tsv").open("a",newline="") as f:
        csv.writer(f,delimiter="\t").writerow([__import__("datetime").datetime.now().astimezone().isoformat(),args.account,match.group(1),index,row["U"],row["V"],row["kx"],row["ky"],str(run),row["result"],args.submission_kind,args.action_id,selection_rank])
    submitted+=1
print(f"SUBMITTED account={{args.account}} count={{submitted}} cap={{cap}} kind={{args.submission_kind}} action_id={{args.action_id}} selection=interleaved")
'''
def status_text(batch: Path) -> str:
    return f'''#!/usr/bin/python3.11
import csv,re
from collections import Counter
from pathlib import Path
BATCH=Path(r"{batch}")
RX=re.compile(r"(?m)^status\\s+COMPLETE\\s*$")
rows=list(csv.DictReader((BATCH/"manifest.tsv").open(),delimiter="\\t"))
def state(row):
    p=Path(row["result"])
    if not p.exists(): return "MISSING"
    if p.is_file() and RX.search(p.read_text(errors="replace")): return "COMPLETE"
    return "CONFLICT"
c=Counter(state(row) for row in rows)
print("EXPANSION",len(rows),dict(sorted(c.items())))
for pair in {list(PAIRS)!r}:
    group=[row for row in rows if int(row["U"])==pair[0] and row["V"]==pair[1]]
    cc=Counter(state(row) for row in group)
    print("U={{}} V={{}} COMPLETE={{}}/836 MISSING={{}} CONFLICT={{}}".format(pair[0],pair[1],cc["COMPLETE"],cc["MISSING"],cc["CONFLICT"]))
'''


def preflight_text(
    batch: Path,
    decision_hash: str,
    plan_sha: str,
    manifest_sha: str,
    template_ledger_sha: str,
    *,
    expected_expansion_total: int = EXPECTED_EXPANSION_TOTAL,
    expected_reused_total: int = EXPECTED_REUSED_TOTAL,
    expected_combined_total: int = EXPECTED_FULL_TOTAL,
    expected_per_case: int = EXPECTED_COMPLEMENT_PER_CASE,
    expected_solver_sha: str = EXPECTED_SOLVER_SHA256,
    expected_source_sha: str = EXPECTED_SOURCE_SHA256,
    expected_qbasis_sha: str = EXPECTED_QBASIS_SHA256,
    expected_audit_status_sha: str = EXPECTED_AUDIT_STATUS_SHA256,
    expected_handoff_receipt_sha: str = EXPECTED_HANDOFF_RECEIPT_SHA256,
) -> str:
    return f'''#!/usr/bin/python3.11
import csv,hashlib,io,json,re,sys
from collections import Counter
from pathlib import Path
BATCH=Path(r"{batch}")
PREFIX="{TEMPLATE_PREFIX}"
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()
def need(condition,message):
    if not condition: raise SystemExit("PREFLIGHT REFUSED: "+message)
manifest_bytes=(BATCH/"manifest.tsv").read_bytes()
need(hashlib.sha256(manifest_bytes).hexdigest()=="{manifest_sha}","manifest byte hash mismatch")
rows=list(csv.DictReader(io.StringIO(manifest_bytes.decode()),delimiter="\\t"))
need(len(rows)=={expected_expansion_total},"manifest row count mismatch")
need(len({{row["index"] for row in rows}})=={expected_expansion_total},"manifest index collision")
need(len({{row["seed"] for row in rows}})=={expected_expansion_total},"manifest seed collision")
need(len({{row["result"] for row in rows}})=={expected_expansion_total},"manifest result collision")
need(set(Counter((row["U"],row["V"]) for row in rows).values())=={{{expected_per_case}}},"manifest case count mismatch")
plan_text="".join(f'{{row["index"]}}\\t{{row["U"]}}\\t{{row["V"]}}\\t{{row["kx"]}}\\t{{row["ky"]}}\\t{{row["seed"]}}\\t{{Path(row["result"]).name}}\\n' for row in rows)
need(hashlib.sha256(plan_text.encode()).hexdigest()=="{plan_sha}","manifest plan digest mismatch")
reused=list(csv.DictReader((BATCH/"reused_25.tsv").open(),delimiter="\\t"))
need(len(reused)=={expected_reused_total},"reused source row count mismatch")
need(len({{(row["U"],row["V"],row["kx"],row["ky"]) for row in rows}} | {{(row["U"],row["V"],row["kx"],row["ky"]) for row in reused}})=={expected_combined_total},"combined coordinate inventory mismatch")
rx=re.compile(r"(?m)^status\\s+COMPLETE\\s*$")
for row in reused:
    path=Path(row["result"])
    need(path.is_file() and sha(path)==row["sha256"],"reused source byte mismatch: "+str(path))
    need(bool(rx.search(path.read_text(errors="replace"))),"reused source is not COMPLETE: "+str(path))
need(sha(BATCH/"decision_certificate.json")=="{decision_hash}","decision certificate hash mismatch")
need(sha(BATCH/"pinned_solver/Hubbard_sym_testobs_UV.x")=="{expected_solver_sha}","solver hash mismatch")
need(sha(BATCH/"pinned_solver/Hubbard_sym_testobs_UV.cc")=="{expected_source_sha}","source hash mismatch")
need(sha(BATCH/"pinned_solver/libqbasis.so")=="{expected_qbasis_sha}","libqbasis hash mismatch")
need(sha(BATCH/"audit_status.py")=="{expected_audit_status_sha}","installed audit tool hash mismatch")
need(sha(BATCH/"tools/audit_status.py")=="{expected_audit_status_sha}","archived audit tool hash mismatch")
need(sha(BATCH/"tools/handoff_receipt.py")=="{expected_handoff_receipt_sha}","archived handoff-receipt tool hash mismatch")
provenance=json.loads((BATCH/"provenance.json").read_text())
need(provenance.get("plan_sha256")=="{plan_sha}","provenance plan hash mismatch")
need(provenance.get("manifest_sha256")=="{manifest_sha}","provenance manifest hash mismatch")
need(provenance.get("template_content_ledger_sha256")=="{template_ledger_sha}","provenance template-ledger hash mismatch")
need(provenance.get("package_tools_sha256",{{}}).get("audit_status.py")=="{expected_audit_status_sha}","provenance audit-tool hash mismatch")
need(provenance.get("package_tools_sha256",{{}}).get("handoff_receipt.py")=="{expected_handoff_receipt_sha}","provenance handoff-receipt tool hash mismatch")
ledger_path=BATCH/"TEMPLATE_SHA256SUMS"
need(sha(ledger_path)=="{template_ledger_sha}","template content-ledger hash mismatch")
expected={{}}
for line in ledger_path.read_text().splitlines():
    fields=line.split("  ",1)
    need(len(fields)==2 and bool(re.fullmatch(r"[0-9a-f]{{64}}",fields[0])) and fields[1] not in expected,"malformed template content-hash row")
    expected[fields[1]]=fields[0]
need(len(expected)=={expected_expansion_total},"template content-hash row count mismatch")
current={{}}
archive_names=set()
for path in sorted((BATCH/"templates").glob(PREFIX+"*.sh")):
    need(path.name not in current,"duplicate pending template: "+path.name)
    current[path.name]=path
for path in sorted((BATCH/"submitted").glob(PREFIX+"*.template")):
    original=path.stem+".sh"
    need(original not in current,"template present as pending and submitted: "+original)
    current[original]=path
    archive_names.add(path.name)
need(set(current)==set(expected),"pending/submitted template inventory differs from immutable ledger")
for name,path in current.items():
    need(sha(path)==expected[name],"template content mismatch: "+name)
with (BATCH/"submission.tsv").open(newline="") as handle:
    submission_reader=csv.DictReader(handle,delimiter="\t")
    required=["submitted_at","account","job_id","index","U","V","kx","ky","run_script","result","submission_kind","action_id","selection_rank"]
    need(submission_reader.fieldnames==required,"submission ledger schema mismatch")
    submissions=list(submission_reader)
need(len(submissions)==len(archive_names),"submission/archive row-count mismatch")
need(len({{row["index"] for row in submissions}})==len(submissions),"submission index collision")
need(len({{row["job_id"] for row in submissions}})==len(submissions),"submission job-id collision")
need(all(row["account"] in {{"ccsd","cnms"}} for row in submissions),"submission account mismatch")
need(all(row["submission_kind"] in {{"initial_launch","rebalance_10m","rebalance_20m","chain_refill","heartbeat_refill"}} for row in submissions),"submission kind mismatch")
need(all(bool(row["action_id"]) for row in submissions),"empty submission action id")
need(all(row["selection_rank"].isdigit() and int(row["selection_rank"])>=1 for row in submissions),"invalid submission selection rank")
print("PREFLIGHT PASS expansion={expected_expansion_total} reused={expected_reused_total} combined={expected_combined_total} templates={expected_expansion_total}")
print("submission defaults to DRY RUN and remains double-armed")
'''


def analyze_text(batch: Path, *, expected_case_count: int = 12) -> str:
    return f'''#!/usr/bin/python3.11
import csv,hashlib,io,json,math,re,subprocess,sys
from collections import defaultdict
from pathlib import Path
BATCH=Path(r"{batch}")
RX=re.compile(r"(?m)^status\\s+COMPLETE\\s*$")
preflight=subprocess.run([sys.executable,str(BATCH/"preflight.py")],text=True,capture_output=True)
if preflight.returncode:
    raise SystemExit("ANALYSIS REFUSED BY PREFLIGHT\\n"+preflight.stdout+preflight.stderr)
rows=list(csv.DictReader((BATCH/"manifest.tsv").open(),delimiter="\\t"))+list(csv.DictReader((BATCH/"reused_25.tsv").open(),delimiter="\\t"))
groups=defaultdict(list)
for row in rows:
    p=Path(row["result"]); text=p.read_text(errors="replace") if p.is_file() else ""
    if not RX.search(text): raise SystemExit("Not ready: "+str(p))
    values={{}}
    for line in text.splitlines():
        parts=line.split(None,1)
        if len(parts)==2: values[parts[0]]=parts[1]
    try: C=float(values["<C1_NN>"])
    except (KeyError,ValueError): raise SystemExit("bad C_NN: "+str(p))
    if not math.isfinite(C) or not (-0.75000001 <= C < 0.0): raise SystemExit("unphysical C_NN: "+str(p))
    groups[(int(row["U"]),row["V"])].append((int(row["kx"]),int(row["ky"]),C))
out=[]
for (U,V),group in sorted(groups.items(),key=lambda item:(item[0][0],float(item[0][1]))):
    if len(group)!=861 or len({{(kx,ky) for kx,ky,_ in group}})!=861: raise SystemExit("bad wedge")
    weighted=[]
    for kx,ky,C in group:
        w=(1 if kx==ky else 2)*(0.5 if kx in (0,40) else 1)*(0.5 if ky in (0,40) else 1)
        weighted.append((w,C))
    if not math.isclose(sum(w for w,_ in weighted),1600.0): raise SystemExit("bad weight")
    mean=sum(w*C for w,C in weighted)/1600.0
    weighted_std=math.sqrt(sum(w*(C-mean)**2 for w,C in weighted)/1600.0)
    factor=(2*U-float(V))/(U-float(V))
    out.append({{"U":U,"V":V,"V_over_U":float(V)/U,"complete_wedge":861,"quadrature_weight":1600.0,"C_NN_full_861":mean,"C_NN_full_quadrature_weighted_population_std":weighted_std,"s_eq10_signed":1+factor*(2*mean-0.5)}})
if len(out)!={expected_case_count}: raise SystemExit("bad case count")
(BATCH/"analysis").mkdir(exist_ok=True)
buffer=io.StringIO(newline="")
w=csv.DictWriter(buffer,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
summary_text=buffer.getvalue()
summary=BATCH/"analysis/fig4_cnn_full861_summary.csv"
if summary.exists():
    if summary.read_bytes()!=summary_text.encode(): raise SystemExit("existing analysis summary differs; refusing overwrite")
else:
    with summary.open("x") as f: f.write(summary_text)
def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda:f.read(1024*1024),b""): h.update(block)
    return h.hexdigest()
provenance_payload={{
    "schema_version":1,
    "data_product":"fig4_cnn_full861_direct_fullobs_C_NN_eq10",
    "combined_raw_output_count":len(rows),
    "case_count":len(out),
    "coordinates_per_case":861,
    "quadrature_weight_per_case":1600.0,
    "C_NN_observable":"<C1_NN>",
    "C_NN_estimator":"861-point wedge with exchange and trapezoidal endpoint weights",
    "spread_is_standard_error":False,
    "spread_diagnostic":"quadrature-weighted population standard deviation",
    "signed_eq10_formula":"1 + (2U-V)/(U-V) * (2*C_NN-1/2)",
    "manifest_sha256":sha(BATCH/"manifest.tsv"),
    "reused_25_sha256":sha(BATCH/"reused_25.tsv"),
    "decision_certificate_sha256":sha(BATCH/"decision_certificate.json"),
    "summary_sha256":hashlib.sha256(summary_text.encode()).hexdigest(),
}}
provenance_text=json.dumps(provenance_payload,indent=2,sort_keys=True)+"\\n"
provenance=BATCH/"analysis/fig4_cnn_full861_provenance.json"
if provenance.exists():
    if provenance.read_text()!=provenance_text: raise SystemExit("existing analysis provenance differs; refusing overwrite")
else:
    with provenance.open("x") as f: f.write(provenance_text)
print("ANALYSIS COMPLETE cases={expected_case_count} rows="+str(len(rows)))
'''


def write_tsv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, delimiter="\t", fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def materialize(
    *,
    base: Path,
    source_batch: Path,
    batch: Path,
    solver: Path,
    source: Path,
    qbasis: Path,
    certificate_path: Path,
) -> None:
    if os.path.lexists(batch):
        raise Refusal(f"Refusing to overwrite batch: {batch}")
    decision, decision_hash = validate_decision_certificate(certificate_path)
    require_hash(source_batch / "manifest.tsv", EXPECTED_SOURCE_MANIFEST_SHA256, "remote source manifest")
    require_hash(source_batch / "twist_panel.tsv", EXPECTED_SOURCE_PANEL_SHA256, "remote source twist panel")
    require_hash(source_batch / "provenance.json", EXPECTED_SOURCE_PROVENANCE_SHA256, "remote source provenance")
    require_hash(solver, EXPECTED_SOLVER_SHA256, "solver")
    require_hash(source, EXPECTED_SOURCE_SHA256, "solver source")
    require_hash(qbasis, EXPECTED_QBASIS_SHA256, "libqbasis")
    active = active_source_jobs()
    if active:
        raise Refusal("Source or expansion job names are still active:\n" + "\n".join(active))
    source_rows = load_source_manifest(source_batch / "manifest.tsv")
    source_inventory = validate_source_results(
        source_rows,
        base,
        decision["source_raw_inventory"]["ordered_filename_sha256_digest"],
    )
    source_decision_revalidation = validate_source_decision_inputs(
        decision,
        source_rows,
        source_inventory,
    )
    _, complement = load_coordinate_contracts()
    plan = build_plan(base, source_rows, complement)
    collisions = [row["result"] for row in plan if os.path.lexists(str(row["result"]))]
    if collisions:
        raise Refusal(
            f"Found {len(collisions)} pre-existing complement result paths; first: {collisions[0]}"
        )
    plan_sha = plan_digest(plan)

    # From this point onward every write is confined to the previously absent
    # batch tree.  A caught Python exception removes that incomplete tree, so a
    # failed materialization never leaves a plausible-looking final batch that
    # blocks a clean retry.  The generator contains no sbatch call, hence this
    # cleanup cannot erase submitted work.  An uncatchable host/process failure
    # is still made obvious by this marker and requires manual inspection.
    batch.mkdir(parents=True, exist_ok=False)
    incomplete_marker = batch / "MATERIALIZATION_INCOMPLETE"
    incomplete_marker.write_text(
        "No submission is authorized while this marker exists.\n"
    )
    try:
        _materialize_created_tree(
            base=base,
            source_batch=source_batch,
            batch=batch,
            solver=solver,
            source=source,
            qbasis=qbasis,
            certificate_path=certificate_path,
            decision=decision,
            decision_hash=decision_hash,
            source_rows=source_rows,
            source_inventory=source_inventory,
            source_decision_revalidation=source_decision_revalidation,
            plan=plan,
            plan_sha=plan_sha,
        )
        incomplete_marker.unlink()
    except BaseException:
        try:
            shutil.rmtree(batch)
        except OSError as cleanup_error:
            raise Refusal(
                "Materialization failed and its incomplete batch could not be "
                f"removed; inspect {batch}: {cleanup_error}"
            ) from cleanup_error
        raise
    print(f"MATERIALIZED WITHOUT SUBMISSION: {batch}")
    print(
        f"expansion={len(plan)} reused={len(source_inventory)} "
        f"combined={len(plan) + len(source_inventory)}"
    )
    print(f"plan_sha256={plan_sha}")
    print(f"decision_certificate_sha256={decision_hash}")


def _materialize_created_tree(
    *,
    base: Path,
    source_batch: Path,
    batch: Path,
    solver: Path,
    source: Path,
    qbasis: Path,
    certificate_path: Path,
    decision: dict[str, Any],
    decision_hash: str,
    source_rows: list[dict[str, str]],
    source_inventory: list[dict[str, Any]],
    source_decision_revalidation: dict[str, Any],
    plan: list[dict[str, Any]],
    plan_sha: str,
) -> None:
    """Populate a batch root already owned by the materialization transaction."""

    for dirname in (
        "templates",
        "submitted",
        "logs",
        "analysis",
        "work",
        "locks",
        "pinned_solver",
        "reviewed_inputs",
        "tools",
    ):
        (batch / dirname).mkdir(exist_ok=False)
    pinned_solver = batch / "pinned_solver" / solver.name
    pinned_source = batch / "pinned_solver" / source.name
    pinned_qbasis = batch / "pinned_solver" / qbasis.name
    shutil.copy2(solver, pinned_solver)
    shutil.copy2(source, pinned_source)
    shutil.copy2(qbasis, pinned_qbasis)
    pinned_solver.chmod(0o700)
    pinned_source.chmod(0o600)
    pinned_qbasis.chmod(0o700)
    require_hash(pinned_solver, EXPECTED_SOLVER_SHA256, "copied pinned solver")
    require_hash(pinned_source, EXPECTED_SOURCE_SHA256, "copied pinned source")
    require_hash(pinned_qbasis, EXPECTED_QBASIS_SHA256, "copied pinned libqbasis")
    (batch / "PINNED_SHA256SUMS").write_text(
        f"{EXPECTED_SOLVER_SHA256}  pinned_solver/{solver.name}\n"
        f"{EXPECTED_SOURCE_SHA256}  pinned_solver/{source.name}\n"
        f"{EXPECTED_QBASIS_SHA256}  pinned_solver/{qbasis.name}\n"
    )
    shutil.copy2(certificate_path, batch / "decision_certificate.json")
    for name in ("wedge_861.tsv", "complement_836.tsv", "contract.json"):
        shutil.copy2(PACKAGE / name, batch / "reviewed_inputs" / name)
    for name in (
        "source_25_manifest.tsv",
        "source_25_twist_panel.tsv",
        "source_25_provenance.json",
    ):
        shutil.copy2(PACKAGE / "reviewed_inputs" / name, batch / "reviewed_inputs" / name)
    audit_status = PACKAGE / "audit_status.py"
    require_hash(audit_status, EXPECTED_AUDIT_STATUS_SHA256, "scheduler-aware audit tool")
    handoff_receipt = PACKAGE / "handoff_receipt.py"
    require_hash(
        handoff_receipt,
        EXPECTED_HANDOFF_RECEIPT_SHA256,
        "immutable handoff-receipt tool",
    )
    for path in (
        SCRIPT,
        PACKAGE / "decision_gate.py",
        PACKAGE / "reviewed_analyze_fig4_cnn_campaign.py",
        audit_status,
        handoff_receipt,
    ):
        shutil.copy2(path, batch / "tools" / path.name)
    shutil.copy2(audit_status, batch / "audit_status.py")
    make_executable(batch / "audit_status.py")

    for row in plan:
        template = batch / "templates" / (
            f"{TEMPLATE_PREFIX}{row['index']:05d}_U{row['U']}_V{decimal_tag(row['V'])}_"
            f"f{row['kx']}x{row['ky']}.sh"
        )
        template.write_text(template_text(row, batch, base, pinned_solver, pinned_qbasis))
        make_executable(template)
        row["template"] = str(template)

    fields = list(plan[0])
    write_tsv(batch / "manifest.tsv", plan, fields)
    manifest_sha = sha256(batch / "manifest.tsv")
    template_paths = sorted((batch / "templates").glob(TEMPLATE_PREFIX + "*.sh"))
    if len(template_paths) != EXPECTED_EXPANSION_TOTAL:
        raise Refusal(
            f"Materialization produced {len(template_paths)} templates, expected 10032"
        )
    (batch / "TEMPLATE_SHA256SUMS").write_text(
        template_hash_ledger_text(template_paths)
    )
    template_ledger_sha = sha256(batch / "TEMPLATE_SHA256SUMS")
    validate_materialized_static_integrity(
        batch=batch,
        expected_manifest_sha256=manifest_sha,
        expected_plan_sha256=plan_sha,
        expected_template_ledger_sha256=template_ledger_sha,
    )
    reused_rows = []
    by_index = {item["index"]: item for item in source_inventory}
    for row in source_rows:
        inventory = by_index[int(row["index"])]
        reused_rows.append(
            {
                "source_index": row["index"],
                "U": row["U"],
                "V": row["V"],
                "V_over_U": row["V_over_U"],
                "expected_phase": row["expected_phase"],
                "source_twist_index": row["twist_index"],
                "kx": row["kx"],
                "ky": row["ky"],
                "seed": row["seed"],
                "result": row["result"],
                "size_bytes": inventory["size_bytes"],
                "sha256": inventory["sha256"],
                "state": "reused_complete_25",
            }
        )
    write_tsv(batch / "reused_25.tsv", reused_rows, list(reused_rows[0]))
    (batch / "submission.tsv").write_text(
        "submitted_at\taccount\tjob_id\tindex\tU\tV\tkx\tky\trun_script\tresult\t"
        "submission_kind\taction_id\tselection_rank\n"
    )
    (batch / "repair_submission.tsv").write_text(
        "submitted_at\taccount\tjob_id\tindex\tU\tV\tkx\tky\trun_script\tresult\t"
        "old_job_id\tfailure_class\trepair_seed\n"
    )

    preflight_path = batch / "preflight.py"
    preflight_path.write_text(
        preflight_text(
            batch,
            decision_hash,
            plan_sha,
            manifest_sha,
            template_ledger_sha,
        )
    )
    make_executable(preflight_path)
    preflight_sha = sha256(preflight_path)

    provenance = {
        "schema_version": 1,
        "batch": str(batch),
        "batch_name": BATCH_NAME,
        "job_names": [JOB_NAME, REPAIR_JOB_NAME],
        "source_batch": str(source_batch),
        "source_manifest_sha256": EXPECTED_SOURCE_MANIFEST_SHA256,
        "source_result_inventory_digest": decision["source_raw_inventory"]["ordered_filename_sha256_digest"],
        "decision_certificate_sha256": decision_hash,
        "decision_gate_algorithm": decision["gate_algorithm"],
        "plan_sha256": plan_sha,
        "manifest_sha256": manifest_sha,
        "template_content_ledger_sha256": template_ledger_sha,
        "preflight_sha256": preflight_sha,
        "source_decision_revalidation": source_decision_revalidation,
        "wedge_sha256": EXPECTED_WEDGE_SHA256,
        "complement_sha256": EXPECTED_COMPLEMENT_SHA256,
        "solver_sha256": EXPECTED_SOLVER_SHA256,
        "source_sha256": EXPECTED_SOURCE_SHA256,
        "qbasis_library_sha256": EXPECTED_QBASIS_SHA256,
        "locate_E0_lanczos_maxit": 10000,
        "physics": {"Lx": 4, "Ly": 4, "Nup": 8, "Ndn": 8, "Qm": 0, "Qn": 0, "tp": 0},
        "resources": {
            "partition": "burst",
            "nodes": 1,
            "tasks": 32,
            "cpus_per_task": 1,
            "memory": "100G",
            "time_limit": "08:00:00",
            "default_total_user_account_cap": 150,
        },
        "pairs": [{"U": U, "V": V, "V_over_U": float(V) / U} for U, V in PAIRS],
        "reused_coordinates_per_case": 25,
        "complement_coordinates_per_case": 836,
        "full_coordinates_per_case": 861,
        "reused_total": 300,
        "expansion_total": 10032,
        "combined_total": 10332,
        "submission_performed_by_generator": False,
        "submission_default": "dry-run",
        "package_tools_sha256": {
            "generate_batch.py": sha256(SCRIPT),
            "decision_gate.py": sha256(PACKAGE / "decision_gate.py"),
            "reviewed_analyze_fig4_cnn_campaign.py": sha256(
                PACKAGE / "reviewed_analyze_fig4_cnn_campaign.py"
            ),
            "audit_status.py": sha256(audit_status),
            "handoff_receipt.py": sha256(handoff_receipt),
        },
    }
    (batch / "provenance.json").write_text(json.dumps(provenance, indent=2, sort_keys=True) + "\n")
    (batch / "submit_fill.py").write_text(
        submit_helper_text(
            batch,
            decision_hash,
            plan_sha,
            manifest_sha,
            template_ledger_sha,
            preflight_sha,
        )
    )
    (batch / "status.py").write_text(status_text(batch))
    (batch / "analyze.py").write_text(analyze_text(batch))
    for name in ("submit_fill.py", "status.py", "analyze.py"):
        make_executable(batch / name)
    preflight_check = subprocess.run(
        [sys.executable, str(preflight_path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if preflight_check.returncode:
        raise Refusal(
            "Materialized batch failed its immutable preflight before any submission:\n"
            + preflight_check.stdout
            + preflight_check.stderr
        )
    readme = f"""# Conditional Fig. 4 C_NN 25→861 expansion

This batch exists only because decision certificate `{decision_hash}` returned
`APPROVE_EXPANSION`.  It targets the exact original twelve cases.  The exact
25 COMPLETE source coordinates per case are hash-pinned in `reused_25.tsv`;
only their canonical 836-coordinate wedge complement has templates.  During
materialization, every decision-driving target metric was independently
rederived from those exact 300 source bytes and compared with the certificate.

- reused: 12 x 25 = 300
- new complement: 12 x 836 = 10,032
- combined full wedge: 12 x 861 = 10,332
- solver/source/libqbasis: the same reviewed 10k runtime hashes as the source
- physics: 4x4, Nup=Ndn=8, Q=(0,0), t'=0
- job prefix: `{JOB_NAME}` (repair reserve `{REPAIR_JOB_NAME}`)
- immutable manifest byte hash and semantic plan digest: pinned in provenance
- all 10,032 original template byte hashes: pinned by `TEMPLATE_SHA256SUMS`

The generator ran no `sbatch`.  Submission defaults to a dry run:

```
/usr/bin/python3.11 preflight.py
/usr/bin/python3.11 submit_fill.py --account ccsd
```

Actual submission is double-armed and is not authorized by batch creation:

```
{CONFIRM_ENV}=YES {CHAIN_ENV}=YES F4CNN861X_CCSD_USER_CAP=150 \\
  /usr/bin/python3.11 submit_fill.py --submit --account ccsd \\
  --limit EFFECTIVE_N --submission-kind initial_launch \\
  --action-id POLICY_STATE_DIGEST --expected-indices COMMA_SEPARATED_INDICES
```

`POLICY_STATE_DIGEST` and `EFFECTIVE_N` must come from the fresh, immutable
pre-action artifact written by the pinned `handoff_receipt.py`; see the
reviewed holding package `HANDOFF.md`.  The helper refuses unclassified
submissions.  It selects still-unsubmitted templates round-robin across the
twelve physics cases and records submission kind, action ID, and selection
rank beside every Slurm job ID in `submission.tsv`.

Before any `sbatch`, `submit_fill.py` verifies the pinned preflight program,
runs it, rechecks the manifest and aggregate template ledger, and verifies the
selected template bytes and rendered Bash syntax.  Any manifest, archived or
pending template, certificate, solver, or reused-source byte change refuses
submission.

Automatic one-for-one refill is additionally off unless both
`{CHAIN_ENV}=YES` and `{CONFIRM_ENV}=YES` are exported into submitted jobs.

The scheduler-aware read-only audit is:

```
/usr/bin/python3.11 audit_status.py --batch {batch} \\
  --job-name {JOB_NAME} --job-name {REPAIR_JOB_NAME} \\
  --pin-file PINNED_SHA256SUMS --require-pins \\
  --submission-log repair_submission.tsv --since 2026-08-21 \\
  --expect-targets 10032 --expect-per-case 836 \\
  --expect-account ccsd --expect-account cnms \\
  --expect-partition burst --expect-cpus 32 --expect-nodes 1 \\
  --expect-memory 100G --expect-time-limit 08:00:00
```
"""
    (batch / "README.md").write_text(readme)


def dry_run(base: Path) -> dict[str, Any]:
    source_manifest = PACKAGE / "reviewed_inputs" / "source_25_manifest.tsv"
    require_hash(
        PACKAGE / "reviewed_inputs" / "source_25_provenance.json",
        EXPECTED_SOURCE_PROVENANCE_SHA256,
        "reviewed source provenance",
    )
    require_hash(PACKAGE / "contract.json", EXPECTED_CONTRACT_SHA256, "package contract")
    source_rows = load_source_manifest(source_manifest)
    wedge, complement = load_coordinate_contracts()
    plan = build_plan(base, source_rows, complement)
    return {
        "mode": "DRY_RUN_ONLY",
        "submission_performed": False,
        "batch_would_be": str(BATCH_DEFAULT),
        "job_names": [JOB_NAME, REPAIR_JOB_NAME],
        "case_count": len(PAIRS),
        "reused_per_case": EXPECTED_REUSED_PER_CASE,
        "complement_per_case": EXPECTED_COMPLEMENT_PER_CASE,
        "full_per_case": EXPECTED_FULL_PER_CASE,
        "reused_total": EXPECTED_REUSED_TOTAL,
        "expansion_total": len(plan),
        "combined_total": EXPECTED_FULL_TOTAL,
        "wedge_count": len(wedge),
        "complement_count": len(complement),
        "source_manifest_sha256": EXPECTED_SOURCE_MANIFEST_SHA256,
        "wedge_sha256": EXPECTED_WEDGE_SHA256,
        "complement_sha256": EXPECTED_COMPLEMENT_SHA256,
        "package_contract_sha256": EXPECTED_CONTRACT_SHA256,
        "plan_sha256": plan_digest(plan),
        "unique_expansion_seeds": len({row["seed"] for row in plan}),
        "result_collisions_with_reused": 0,
        "coordinate_collisions_with_reused": 0,
        "materialization_requires_approved_certificate": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Default; audit plan only.")
    mode.add_argument(
        "--verify-certificate",
        action="store_true",
        help="Read-only validation of an APPROVE certificate; create nothing.",
    )
    mode.add_argument("--materialize", action="store_true", help="Create the guarded CADES batch.")
    parser.add_argument("--base", type=Path, default=BASE_DEFAULT)
    parser.add_argument("--source-batch", type=Path, default=SOURCE_BATCH_DEFAULT)
    parser.add_argument("--batch", type=Path, default=BATCH_DEFAULT)
    parser.add_argument("--solver", type=Path, default=SOLVER_DEFAULT)
    parser.add_argument("--source", type=Path, default=SOURCE_DEFAULT)
    parser.add_argument("--qbasis", type=Path, default=QBASIS_DEFAULT)
    parser.add_argument("--decision-certificate", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        validate_package_ledger()
        if args.verify_certificate:
            if args.decision_certificate is None:
                raise Refusal("--verify-certificate requires --decision-certificate")
            decision, decision_hash = validate_decision_certificate(
                args.decision_certificate
            )
            print(
                json.dumps(
                    {
                        "mode": "VERIFY_CERTIFICATE_ONLY",
                        "submission_performed": False,
                        "certificate": str(args.decision_certificate),
                        "certificate_sha256": decision_hash,
                        "decision": decision["decision"],
                        "gate_algorithm": decision["gate_algorithm"],
                        "source_raw_inventory": decision["source_raw_inventory"],
                        "quadrature_diagnostics": decision[
                            "quadrature_diagnostics"
                        ],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if not args.materialize:
            print(json.dumps(dry_run(args.base), indent=2, sort_keys=True))
            return 0
        if args.decision_certificate is None:
            raise Refusal("--materialize requires --decision-certificate")
        materialize(
            base=args.base,
            source_batch=args.source_batch,
            batch=args.batch,
            solver=args.solver,
            source=args.source,
            qbasis=args.qbasis,
            certificate_path=args.decision_certificate,
        )
        return 0
    except (Refusal, OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
