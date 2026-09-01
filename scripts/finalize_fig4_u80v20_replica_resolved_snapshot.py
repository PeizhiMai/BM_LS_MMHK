#!/usr/bin/env python3
"""Finalize one downloaded U=80,V=20 P25 logical-selection snapshot.

This is deliberately a local, add-only freezer.  It validates 24 canonical
outputs plus exactly one deterministically selected replica for the missing
f17x17 target.  The other four replicas are retained only as seed-consistency
cross-checks and are never averaged into the 25-twist estimator.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path


MANIFEST_SHA = "e5e95fa9b65d312b79f3a6349252a37c9ea60c1ce95df50a3be142b334c97117"
TWIST_SHA = "688132fc91e3decdb83784e71d4a69c9868e1f2ead740d753c2ca7e538b06f4b"
SELECTED_SHA = "c1c9d9950469d25dca82ce2c9b6f3cbc2f775e0e31330dea23c2453a67ed450c"
SELECTED = (4, 5621087, 1, 436887014)  # ordinal, job, index, seed
CANONICAL_PINS = (
    "b85cefa08615ff2bffd46690990c68b4d1297de7a8b11046ebd6c1c29bdd8c0b",
    "f68ecd93e2dee07012d7fda6521fe617775f637fede1da7f3f0cb27a92e6ce73",
    "be10e2a72679b2214735c1e71f55dfc331e395a41a0866ecde35b090ca21ba85",
)
REPLICA_PINS = (
    "d9ddea4afad15aeeed0557b44e1f0ffb292e67e927a8ac01a4df91d2c611f5a7",
    "fcf6ad1f61c294186291afd15ae09fc46551443eab1fbbb1a6ca851fca66521b",
    "8aea806f3791de627de8e9ae876dacacdc378da8ea7e3803d9c1a1c4d47c9efe",
)
RAW_NAME = re.compile(
    r"^L4x4Nup8Ndn8U80V20tp0f(?P<kx>\d+)x(?P<ky>\d+)Q0x0_obs\.dat$"
)


class Refusal(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def parse_output(path: Path) -> tuple[dict[str, float], dict[str, float], float]:
    values: dict[str, str] = {}
    counts: dict[str, int] = {}
    for line in path.read_text().splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2:
            counts[parts[0]] = counts.get(parts[0], 0) + 1
            values[parts[0]] = parts[1].strip()
    required = (
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
        "<Spipi>",
        "<Sc_pipi>",
        "<mCDW2_pipi>",
        "status",
    )
    if any(counts.get(key) != 1 for key in required):
        raise Refusal(f"Missing or nonunique observables in {path}")
    if values["status"] != "COMPLETE" or values["Q"] != "0,0":
        raise Refusal(f"Wrong status/Q in {path}")
    numeric = {
        key: float(values[key]) for key in required if key not in {"Q", "status"}
    }
    if not all(math.isfinite(value) for value in numeric.values()):
        raise Refusal(f"Non-finite observable in {path}")
    if (
        numeric["Lx"],
        numeric["Ly"],
        numeric["tp"],
        numeric["U"],
        numeric["V"],
    ) != (4.0, 4.0, 0.0, 80.0, 20.0):
        raise Refusal(f"Metadata mismatch in {path}")
    residuals = {
        "energy_per_site": numeric["E0"] / 16.0
        - (
            numeric["<Kinetic_per_site>"]
            + 80.0 * numeric["<ni_upni_dn>"]
            + 40.0 * numeric["<nn_NN>"]
        ),
        "connected_density": numeric["<delta_n_delta_n_NN>"]
        - (numeric["<nn_NN>"] - 1.0),
        "kinetic_sum": numeric["<Kinetic_per_site>"]
        - (
            numeric["<Kinetic_NN_per_site>"]
            + numeric["<Kinetic_NNN_per_site>"]
        ),
        "charge_Sc_over_N": numeric["<mCDW2_pipi>"]
        - numeric["<Sc_pipi>"] / 16.0,
    }
    worst = max(abs(value) for value in residuals.values())
    if worst > 1.0e-8:
        raise Refusal(f"Observable identities fail in {path}: {residuals}")
    C = numeric["<C1_NN>"]
    D = numeric["<ni_upni_dn>"]
    mcdw = numeric["<mCDW2_pipi>"]
    if not (-0.75000001 <= C <= 0.25000001 and 0 <= D <= 1 and 0 <= mcdw <= 1):
        raise Refusal(f"Physical bounds fail in {path}")
    return numeric, residuals, worst


def write_csv(path: Path, records: list[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} SNAPSHOT")
    root = Path(sys.argv[1]).expanduser().resolve()
    raw_dir = root / "raw"
    cross_dir = root / "replica_crosscheck"
    metadata = root / "metadata"
    analysis = root / "analysis"
    if not root.is_dir() or root.is_symlink():
        raise Refusal("Snapshot must be a real existing directory")
    if (root / "SNAPSHOT_SHA256SUMS").exists():
        raise Refusal("Snapshot is already frozen")

    manifest_path = metadata / "canonical__manifest.tsv"
    twist_path = metadata / "canonical__twist_panel.tsv"
    if sha256(manifest_path) != MANIFEST_SHA or sha256(twist_path) != TWIST_SHA:
        raise Refusal("Canonical manifest/twist binding mismatch")
    manifest = read_tsv(manifest_path)
    twists = read_tsv(twist_path)
    submission = {
        int(row["index"]): row
        for row in read_tsv(metadata / "canonical__submission.tsv")
    }
    remote = json.loads((metadata / "remote_inventory.json").read_text())
    if len(manifest) != 25 or len(twists) != 25 or len(submission) != 25:
        raise Refusal("Canonical metadata cardinality mismatch")
    remote_canonical = {
        (int(row["kx"]), int(row["ky"])): row
        for row in remote["canonical"]
        if row["exists"]
    }
    replicas = sorted(
        remote["replicas"],
        key=lambda row: (
            int(row["replica_ordinal"]),
            int(row["job_id"]),
            int(row["replica_index"]),
        ),
    )
    if len(remote_canonical) != 24 or len(replicas) != 5:
        raise Refusal("Remote result cardinality mismatch")
    selected = replicas[0]
    selected_tuple = (
        int(selected["replica_ordinal"]),
        int(selected["job_id"]),
        int(selected["replica_index"]),
        int(selected["seed"]),
    )
    if selected_tuple != SELECTED or selected["file"]["sha256"] != SELECTED_SHA:
        raise Refusal("Deterministic replica selection mismatch")

    rows: list[dict[str, object]] = []
    for manifest_row in manifest:
        index = int(manifest_row["index"])
        kx, ky = int(manifest_row["kx"]), int(manifest_row["ky"])
        path = raw_dir / Path(manifest_row["result"]).name
        match = RAW_NAME.fullmatch(path.name)
        if not path.is_file() or path.is_symlink() or not match:
            raise Refusal(f"Unsafe/missing logical raw row {path}")
        if (int(match["kx"]), int(match["ky"])) != (kx, ky):
            raise Refusal(f"Filename/manifest twist mismatch in {path}")
        numeric, residuals, worst = parse_output(path)
        if index == 7:
            expected_hash = SELECTED_SHA
            role = "selected_replica_for_missing_canonical"
            job_id = int(selected["job_id"])
            seed = int(selected["seed"])
            replica_index = int(selected["replica_index"])
            replica_ordinal = int(selected["replica_ordinal"])
            selection_applied = True
            remote_path = selected["file"]["path"]
        else:
            source = remote_canonical[(kx, ky)]
            expected_hash = source["file"]["sha256"]
            role = "canonical_complete"
            job_id = int(submission[index]["job_id"])
            seed = int(manifest_row["seed"])
            replica_index = replica_ordinal = 0
            selection_applied = False
            remote_path = source["file"]["path"]
        if sha256(path) != expected_hash:
            raise Refusal(f"Downloaded raw hash mismatch for {path}")
        rows.append(
            {
                "U": 80.0,
                "V": 20.0,
                "r": 0.25,
                "twist_index": index,
                "kx": kx,
                "ky": ky,
                "C1_NN": numeric["<C1_NN>"],
                "source_role": role,
                "source_job_id": job_id,
                "seed": seed,
                "replica_index": replica_index,
                "replica_ordinal": replica_ordinal,
                "selection_rule_applied": selection_applied,
                "E0": numeric["E0"],
                "D_site": numeric["<ni_upni_dn>"],
                "mCDW2_pipi": numeric["<mCDW2_pipi>"],
                "nn_NN": numeric["<nn_NN>"],
                "kinetic_per_site": numeric["<Kinetic_per_site>"],
                "Spipi": numeric["<Spipi>"],
                "Sc_pipi": numeric["<Sc_pipi>"],
                "max_abs_identity_residual": worst,
                "identity_energy_per_site_residual": residuals["energy_per_site"],
                "identity_connected_density_residual": residuals["connected_density"],
                "identity_kinetic_sum_residual": residuals["kinetic_sum"],
                "identity_charge_Sc_over_N_residual": residuals["charge_Sc_over_N"],
                "local_filename": path.name,
                "local_sha256": expected_hash,
                "remote_source_path": remote_path,
            }
        )
    if (
        len(rows) != 25
        or len({(row["kx"], row["ky"]) for row in rows}) != 25
        or sum(bool(row["selection_rule_applied"]) for row in rows) != 1
    ):
        raise Refusal("Logical row inventory mismatch")

    crosscheck: list[dict[str, object]] = []
    for replica in replicas:
        path = cross_dir / Path(replica["file"]["path"]).name
        if sha256(path) != replica["file"]["sha256"]:
            raise Refusal(f"Replica cross-check hash mismatch for {path}")
        numeric, _, worst = parse_output(path)
        crosscheck.append(
            {
                "replica_index": int(replica["replica_index"]),
                "replica_ordinal": int(replica["replica_ordinal"]),
                "job_id": int(replica["job_id"]),
                "seed": int(replica["seed"]),
                "selected": replica is selected,
                "C1_NN": numeric["<C1_NN>"],
                "D_site": numeric["<ni_upni_dn>"],
                "mCDW2_pipi": numeric["<mCDW2_pipi>"],
                "nn_NN": numeric["<nn_NN>"],
                "kinetic_per_site": numeric["<Kinetic_per_site>"],
                "max_abs_identity_residual": worst,
                "sha256": replica["file"]["sha256"],
                "remote_result": replica["file"]["path"],
                "local_file": str(path.relative_to(root)),
            }
        )

    C = [float(row["C1_NN"]) for row in rows]
    weights = [1 if row["kx"] == row["ky"] else 2 for row in rows]
    mean = statistics.fmean(C)
    symmetry_mean = sum(w * value for w, value in zip(weights, C)) / sum(weights)
    factor = (2.0 * 80.0 - 20.0) / (80.0 - 20.0)
    summary = {
        "U": 80.0,
        "V": 20.0,
        "r": 0.25,
        "complete_twists": 25,
        "C_NN": mean,
        "C_NN_min": min(C),
        "C_NN_max": max(C),
        "C_NN_spread": max(C) - min(C),
        "C_NN_population_std_diagnostic": statistics.pstdev(C),
        "C_NN_symmetry_weighted_diagnostic": symmetry_mean,
        "C_NN_symmetry_weighted_minus_primary": symmetry_mean - mean,
        "s_eq10_signed": 1.0 + factor * (2.0 * mean - 0.5),
        "D_site_panel_mean": statistics.fmean(float(row["D_site"]) for row in rows),
        "mCDW2_pipi_panel_mean": statistics.fmean(
            float(row["mCDW2_pipi"]) for row in rows
        ),
        "nn_NN_panel_mean": statistics.fmean(float(row["nn_NN"]) for row in rows),
        "kinetic_per_site_panel_mean": statistics.fmean(
            float(row["kinetic_per_site"]) for row in rows
        ),
        "Spipi_panel_mean": statistics.fmean(float(row["Spipi"]) for row in rows),
        "max_abs_identity_residual": max(
            float(row["max_abs_identity_residual"]) for row in rows
        ),
        "C_NN_source": (
            "24 canonical fullobs P25 + one deterministically selected true-seed replica"
        ),
        "C_NN_sampling": "25-twist unweighted arithmetic mean",
        "C_NN_fidelity": "P25 logical replica-resolved",
        "twist_spread_is_standard_error": False,
    }
    analysis.mkdir(exist_ok=True)
    write_csv(analysis / "u80v20_raw_validation.csv", rows)
    write_csv(analysis / "u80v20_summary.csv", [summary])
    write_csv(analysis / "u80v20_replica_seed_crosscheck.csv", crosscheck)

    binding_fields = [
        "U",
        "V",
        "kx",
        "ky",
        "twist_index",
        "source_role",
        "original_canonical_job_id",
        "canonical_result",
        "canonical_exists",
        "replica_index",
        "replica_ordinal",
        "selected_job_id",
        "selected_seed",
        "effective_seed_proof",
        "selected_remote_result",
        "selected_result_sha256",
        "selection_rule",
        "duplicate_replicas_not_averaged",
    ]
    with (metadata / "selected_replica_binding.tsv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=binding_fields, delimiter="\t")
        writer.writeheader()
        writer.writerow(
            {
                "U": 80,
                "V": 20,
                "kx": 17,
                "ky": 17,
                "twist_index": 7,
                "source_role": "selected_replica_for_missing_canonical",
                "original_canonical_job_id": 5619905,
                "canonical_result": (
                    "/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs/"
                    "L4x4Nup8Ndn8U80V20tp0f17x17Q0x0_obs.dat"
                ),
                "canonical_exists": False,
                "replica_index": 1,
                "replica_ordinal": 4,
                "selected_job_id": 5621087,
                "selected_seed": 436887014,
                "effective_seed_proof": True,
                "selected_remote_result": selected["file"]["path"],
                "selected_result_sha256": SELECTED_SHA,
                "selection_rule": (
                    "lowest valid (replica_ordinal,numeric job_id,replica_index)"
                ),
                "duplicate_replicas_not_averaged": True,
            }
        )

    replica_C = [float(row["C1_NN"]) for row in crosscheck]
    provenance = {
        "schema": "fig4_cnn_u80v20_p25_replica_resolved_v1",
        "created_at": datetime.now().astimezone().isoformat(),
        "inventory": {
            "logical_rows": 25,
            "cases": 1,
            "twists_per_case": 25,
            "canonical_rows": 24,
            "selected_replica_rows": 1,
            "replica_crosscheck_rows": 5,
        },
        "selection_policy": {
            "rule": "lowest valid (replica_ordinal,numeric job_id,replica_index)",
            "same_target_duplicates_averaged": False,
            "selected_job_id": 5621087,
            "selected_seed": 436887014,
            "selected_replica_index": 1,
            "selected_replica_ordinal": 4,
            "selected_target": {
                "U": 80,
                "V": 20,
                "kx": 17,
                "ky": 17,
                "twist_index": 7,
            },
            "canonical_result_still_absent": True,
        },
        "source_batches": {
            "canonical": remote["canonical_batch"],
            "replica": remote["replica_batch"],
        },
        "bindings": {
            "canonical_manifest_sha256": MANIFEST_SHA,
            "twist_panel_sha256": TWIST_SHA,
            "selected_result_sha256": SELECTED_SHA,
            "canonical_pins": list(CANONICAL_PINS),
            "selected_replica_pins": list(REPLICA_PINS),
            "Hamiltonian_and_observables_unchanged": True,
        },
        "validation": {
            "identity_tolerance": 1.0e-8,
            "max_abs_identity_residual": summary["max_abs_identity_residual"],
            "physical_bounds_pass": True,
            "five_replica_C_NN_spread": max(replica_C) - min(replica_C),
            "alternate_replica_max_effect_on_25twist_mean": max(
                abs(value - replica_C[0]) / 25.0 for value in replica_C
            ),
        },
        "estimator": {
            "primary": "25-twist unweighted arithmetic mean",
            "twist_spread_role": "systematic diagnostic, not SEM",
            "symmetry_weighted_is_diagnostic_only": True,
        },
        "summary": summary,
    }
    (metadata / "provenance.json").write_text(
        json.dumps(provenance, indent=2, sort_keys=True) + "\n"
    )
    (root / "README.md").write_text(
        "Fig. 4 U=80,V=20 logical P25 snapshot: 24 canonical rows plus "
        "exactly one deterministic true-seed replica for missing f17x17. "
        "Other replicas are cross-checks only and are never averaged.\n"
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
