#!/usr/bin/env python3
"""Freeze a reviewed all-F861 analysis candidate as an immutable release.

The scientific analyzer deliberately refuses to write below ``results/``.
This separate release step first runs the strict publication loader (including
the immutable-snapshot hash audit and analyzer replay), copies the complete
six-file analyzer product into a hidden directory, verifies every copied byte,
and finally installs the versioned directory with one atomic rename.  Existing
release directories are never replaced.
"""

from __future__ import annotations

import argparse
import ctypes
import fcntl
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path

from fig4_cnn_prediction_input import (
    ANALYZER_OUTPUT_BASENAMES,
    DATA_PRODUCT,
    DECISION_GATE_ALGORITHM,
    FULL861_FIDELITY,
    POINTWISE_BASENAME,
    PROVENANCE_BASENAME,
    load_validated_fullobs_eq10_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp"
RESULTS_ROOT = ROOT / "results"
SCALE_POINTS = RESULTS_ROOT / "pnas_scale_rule_points_eta0p05.csv"

CANDIDATE_PREFIX = "fig4_cnn_full861_release_candidate_"
RELEASE_PREFIX = "fig4_cnn_full861_release_"
RELEASE_MANIFEST_BASENAME = "fig4_cnn_full861_release_manifest.json"
RELEASE_SCHEMA_VERSION = 2
RELEASE_DATA_PRODUCT = "immutable_fig4_cnn_full861_analysis_release"
ANALYSIS_BASENAMES = (*ANALYZER_OUTPUT_BASENAMES, PROVENANCE_BASENAME)
FREEZE_LOCK_BASENAME = ".fig4_cnn_full861_release_freeze.lock"
RELEASE_MANIFEST_KEYS = frozenset(
    {
        "schema_version",
        "data_product",
        "analysis_data_product",
        "C_NN_fidelity",
        "row_count",
        "immutable_no_overwrite",
        "strict_loader_and_analyzer_replay_passed_before_freeze",
        "analyzer_sha256",
        "snapshot_root",
        "decision_certificate_sha256",
        "decision_gate_algorithm",
        "analysis_files_sha256",
        "analysis_bundle_sha256",
        "pointwise_csv_sha256",
        "analysis_provenance_sha256",
    }
)


class FreezeRefusal(RuntimeError):
    """Raised when a candidate cannot be frozen without weakening the gate."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _bundle_digest(file_hashes: dict[str, str]) -> str:
    payload = "".join(
        f"{basename}\t{file_hashes[basename]}\n" for basename in ANALYSIS_BASENAMES
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _require_direct_child(path: Path, root: Path, prefix: str, label: str) -> None:
    if path.parent != root or not path.name.startswith(prefix):
        raise FreezeRefusal(
            f"{label} must be a direct child of {root} named {prefix}<version>"
        )
    if path.name == prefix or any(character.isspace() for character in path.name):
        raise FreezeRefusal(f"{label} requires a nonempty whitespace-free version")


def _require_exact_candidate_inventory(candidate: Path) -> None:
    expected = set(ANALYSIS_BASENAMES)
    actual = {path.name for path in candidate.iterdir()}
    if actual != expected:
        raise FreezeRefusal(
            "Analysis candidate is not the exact six-file analyzer product; "
            f"missing={sorted(expected - actual)}, unexpected={sorted(actual - expected)}"
        )
    for basename in ANALYSIS_BASENAMES:
        path = candidate / basename
        if path.is_symlink() or not path.is_file() or path.stat().st_size <= 0:
            raise FreezeRefusal(
                f"Analysis candidate contains a missing, empty, or linked file: {basename}"
            )


def _release_manifest(
    *,
    file_hashes: dict[str, str],
    provenance: dict,
) -> dict[str, object]:
    return {
        "schema_version": RELEASE_SCHEMA_VERSION,
        "data_product": RELEASE_DATA_PRODUCT,
        "analysis_data_product": DATA_PRODUCT,
        "C_NN_fidelity": FULL861_FIDELITY,
        "row_count": 16,
        "immutable_no_overwrite": True,
        "strict_loader_and_analyzer_replay_passed_before_freeze": True,
        "analyzer_sha256": provenance.get("analyzer_sha256"),
        "snapshot_root": provenance.get("snapshot_root"),
        "decision_certificate_sha256": provenance.get(
            "decision_certificate_sha256"
        ),
        "decision_gate_algorithm": provenance.get("decision_gate_algorithm"),
        "analysis_files_sha256": file_hashes,
        "analysis_bundle_sha256": _bundle_digest(file_hashes),
        "pointwise_csv_sha256": file_hashes[POINTWISE_BASENAME],
        "analysis_provenance_sha256": file_hashes[PROVENANCE_BASENAME],
    }


def validate_frozen_full861_release(
    release_dir: Path,
    *,
    results_root: Path = RESULTS_ROOT,
) -> dict[str, object]:
    """Revalidate the exact immutable seven-file publication release.

    This is the reusable boundary between the transient analyzer candidate and
    every publication consumer.  A directory merely containing byte-valid
    analyzer outputs is not a release: it must be a direct, correctly named
    child of ``results/`` with the freeze manifest and read-only modes produced
    by :func:`freeze_full861_publication_bundle`.
    """

    supplied = Path(release_dir).expanduser()
    if supplied.is_symlink():
        raise FreezeRefusal(f"Frozen release path must not be a symlink: {supplied}")
    release = supplied.resolve()
    root = Path(results_root).expanduser().resolve()
    _require_direct_child(release, root, RELEASE_PREFIX, "Frozen release directory")
    if not release.is_dir():
        raise FreezeRefusal(f"Frozen release directory not found: {release}")
    if stat.S_IMODE(release.stat().st_mode) != 0o555:
        raise FreezeRefusal("Frozen release directory mode must be exactly 0555")

    expected_names = {*ANALYSIS_BASENAMES, RELEASE_MANIFEST_BASENAME}
    actual_names = {path.name for path in release.iterdir()}
    if actual_names != expected_names:
        raise FreezeRefusal(
            "Frozen release is not the exact seven-file product; "
            f"missing={sorted(expected_names - actual_names)}, "
            f"unexpected={sorted(actual_names - expected_names)}"
        )
    for basename in expected_names:
        path = release / basename
        if (
            path.is_symlink()
            or not path.is_file()
            or path.stat().st_size <= 0
            or stat.S_IMODE(path.stat().st_mode) != 0o444
        ):
            raise FreezeRefusal(
                "Frozen release contains a missing, empty, linked, or writable file: "
                + basename
            )

    manifest_path = release / RELEASE_MANIFEST_BASENAME
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise FreezeRefusal("Frozen release manifest is unreadable") from exc
    if not isinstance(manifest, dict) or set(manifest) != RELEASE_MANIFEST_KEYS:
        raise FreezeRefusal("Frozen release manifest has the wrong exact schema")
    decision_certificate_sha256 = manifest.get("decision_certificate_sha256")
    if (
        manifest.get("schema_version") != RELEASE_SCHEMA_VERSION
        or manifest.get("data_product") != RELEASE_DATA_PRODUCT
        or manifest.get("analysis_data_product") != DATA_PRODUCT
        or manifest.get("C_NN_fidelity") != FULL861_FIDELITY
        or manifest.get("row_count") != 16
        or manifest.get("immutable_no_overwrite") is not True
        or manifest.get("strict_loader_and_analyzer_replay_passed_before_freeze")
        is not True
        or manifest.get("decision_gate_algorithm") != DECISION_GATE_ALGORITHM
        or not isinstance(decision_certificate_sha256, str)
        or len(decision_certificate_sha256) != 64
        or any(
            character not in "0123456789abcdef"
            for character in decision_certificate_sha256
        )
    ):
        raise FreezeRefusal("Frozen release manifest contract is inconsistent")

    file_hashes = {
        basename: _sha256(release / basename) for basename in ANALYSIS_BASENAMES
    }
    if manifest.get("analysis_files_sha256") != file_hashes:
        raise FreezeRefusal("Frozen release analysis-file hashes are stale")
    if manifest.get("analysis_bundle_sha256") != _bundle_digest(file_hashes):
        raise FreezeRefusal("Frozen release analysis-bundle digest is stale")
    if manifest.get("pointwise_csv_sha256") != file_hashes[POINTWISE_BASENAME]:
        raise FreezeRefusal("Frozen release pointwise CSV hash is stale")
    if (
        manifest.get("analysis_provenance_sha256")
        != file_hashes[PROVENANCE_BASENAME]
    ):
        raise FreezeRefusal("Frozen release analysis-provenance hash is stale")

    try:
        provenance = json.loads((release / PROVENANCE_BASENAME).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise FreezeRefusal("Frozen release analysis provenance is unreadable") from exc
    if not isinstance(provenance, dict):
        raise FreezeRefusal("Frozen release analysis provenance must be an object")
    if (
        manifest.get("analyzer_sha256") != provenance.get("analyzer_sha256")
        or manifest.get("snapshot_root") != provenance.get("snapshot_root")
        or manifest.get("decision_certificate_sha256")
        != provenance.get("decision_certificate_sha256")
        or manifest.get("decision_gate_algorithm")
        != provenance.get("decision_gate_algorithm")
    ):
        raise FreezeRefusal(
            "Frozen release manifest is not bound to its analysis provenance"
        )
    return manifest


def _make_release_files_read_only(staged: Path) -> None:
    """Set and verify immutable file modes before atomic installation."""
    for basename in (*ANALYSIS_BASENAMES, RELEASE_MANIFEST_BASENAME):
        path = staged / basename
        path.chmod(0o444)
        if stat.S_IMODE(path.stat().st_mode) != 0o444:
            raise FreezeRefusal(f"Could not make staged release file read-only: {basename}")


def _remove_failed_stage(staged: Path) -> None:
    """Restore owner-write bits as needed, then remove a failed hidden stage."""
    if not staged.exists():
        return
    staged.chmod(0o700)
    for path in staged.iterdir():
        if path.is_dir():
            path.chmod(0o700)
        else:
            path.chmod(0o600)
    shutil.rmtree(staged)


def _rename_directory_no_replace(source: Path, destination: Path) -> None:
    """Atomically rename a directory and refuse every existing destination."""
    libc = ctypes.CDLL(None, use_errno=True)
    source_bytes = os.fsencode(source)
    destination_bytes = os.fsencode(destination)
    if sys.platform == "darwin":
        rename = libc.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        result = rename(source_bytes, destination_bytes, 0x00000004)  # RENAME_EXCL
    elif sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        rename = libc.renameat2
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        result = rename(
            -100,  # AT_FDCWD
            source_bytes,
            -100,
            destination_bytes,
            0x00000001,  # RENAME_NOREPLACE
        )
    else:
        raise FreezeRefusal(
            "This platform lacks a reviewed atomic no-replace directory rename"
        )
    if result != 0:
        error_number = ctypes.get_errno()
        raise OSError(
            error_number,
            os.strerror(error_number),
            str(source),
            str(destination),
        )


def _verify_installed_release(
    release: Path,
    *,
    source_hashes: dict[str, str],
    manifest: dict[str, object],
) -> None:
    expected_names = {*ANALYSIS_BASENAMES, RELEASE_MANIFEST_BASENAME}
    if {path.name for path in release.iterdir()} != expected_names:
        raise FreezeRefusal("Installed release inventory is incomplete")
    for basename, expected_hash in source_hashes.items():
        installed_file = release / basename
        if (
            _sha256(installed_file) != expected_hash
            or stat.S_IMODE(installed_file.stat().st_mode) != 0o444
        ):
            raise FreezeRefusal(f"Installed release hash/mode mismatch: {basename}")
    manifest_path = release / RELEASE_MANIFEST_BASENAME
    if (
        json.loads(manifest_path.read_text()) != manifest
        or stat.S_IMODE(manifest_path.stat().st_mode) != 0o444
        or stat.S_IMODE(release.stat().st_mode) != 0o555
    ):
        raise FreezeRefusal("Installed release manifest/permission check failed")


def freeze_full861_publication_bundle(
    *,
    candidate_dir: Path,
    release_dir: Path,
    scale_points_path: Path = SCALE_POINTS,
) -> Path:
    """Validate, byte-verify, and atomically install one immutable release."""
    candidate = Path(candidate_dir).expanduser().resolve()
    release = Path(release_dir).expanduser().resolve()
    tmp_root = TMP_ROOT.expanduser().resolve()
    results_root = RESULTS_ROOT.expanduser().resolve()

    _require_direct_child(candidate, tmp_root, CANDIDATE_PREFIX, "Candidate directory")
    _require_direct_child(release, results_root, RELEASE_PREFIX, "Release directory")
    if not candidate.is_dir():
        raise FreezeRefusal(f"Analysis candidate directory not found: {candidate}")
    if not results_root.is_dir():
        raise FreezeRefusal(f"Results root not found: {results_root}")
    if os.path.lexists(release):
        raise FreezeRefusal(
            f"Immutable release already exists and will not be replaced: {release}"
        )

    _require_exact_candidate_inventory(candidate)
    # This production-only load binds claims to canonical raw bytes and replays
    # the reviewed analyzer before anything is created under results/.
    bundle = load_validated_fullobs_eq10_bundle(
        candidate,
        allow_fixture=False,
        scale_points_path=Path(scale_points_path),
    )
    source_hashes = {
        basename: _sha256(candidate / basename) for basename in ANALYSIS_BASENAMES
    }
    pinned_outputs = bundle.provenance.get("output_files")
    if not isinstance(pinned_outputs, dict) or any(
        source_hashes[basename] != pinned_outputs.get(basename)
        for basename in ANALYZER_OUTPUT_BASENAMES
    ):
        raise FreezeRefusal(
            "Analysis candidate changed after strict validation or has stale output pins"
        )
    try:
        reread_provenance = json.loads((candidate / PROVENANCE_BASENAME).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise FreezeRefusal("Analysis provenance changed after strict validation") from exc
    if reread_provenance != bundle.provenance:
        raise FreezeRefusal("Analysis provenance changed after strict validation")
    manifest = _release_manifest(
        file_hashes=source_hashes,
        provenance=bundle.provenance,
    )

    staged = Path(
        tempfile.mkdtemp(prefix=f".{release.name}.freeze-", dir=results_root)
    )
    installed = False
    try:
        for basename in ANALYSIS_BASENAMES:
            shutil.copy2(candidate / basename, staged / basename)
        (staged / RELEASE_MANIFEST_BASENAME).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        )

        expected_names = {*ANALYSIS_BASENAMES, RELEASE_MANIFEST_BASENAME}
        if {path.name for path in staged.iterdir()} != expected_names:
            raise FreezeRefusal("Frozen release staging inventory is incomplete")
        for basename, expected_hash in source_hashes.items():
            copied = staged / basename
            if (
                copied.is_symlink()
                or not copied.is_file()
                or _sha256(copied) != expected_hash
            ):
                raise FreezeRefusal(
                    f"Frozen release copy failed byte verification: {basename}"
                )
        if json.loads((staged / RELEASE_MANIFEST_BASENAME).read_text()) != manifest:
            raise FreezeRefusal("Frozen release manifest failed its write/read check")

        # Freeze every file before atomic installation. macOS refuses to rename
        # a source directory with mode 0555, so the directory itself stays 0700
        # through rename and is changed to 0555 immediately afterward while the
        # publication-freeze lock remains held. Its contents are never exposed
        # with writable file modes.
        _make_release_files_read_only(staged)

        # The versioned destination is checked again under a process lock just
        # before the same-filesystem rename. POSIX rename installs the complete
        # directory in one operation; no partially copied release is visible.
        lock_path = tmp_root / FREEZE_LOCK_BASENAME
        with lock_path.open("a+b") as lock_handle:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            if os.path.lexists(release):
                raise FreezeRefusal(
                    "Immutable release appeared during staging and will not be "
                    f"replaced: {release}"
                )
            _rename_directory_no_replace(staged, release)
            try:
                release.chmod(0o555)
                if stat.S_IMODE(release.stat().st_mode) != 0o555:
                    raise FreezeRefusal(
                        "Could not make installed release directory read-only"
                    )
                _verify_installed_release(
                    release,
                    source_hashes=source_hashes,
                    manifest=manifest,
                )
                if (
                    validate_frozen_full861_release(
                        release,
                        results_root=results_root,
                    )
                    != manifest
                ):
                    raise FreezeRefusal(
                        "Installed release failed reusable manifest revalidation"
                    )
            except BaseException:
                _remove_failed_stage(release)
                raise
            installed = True
    finally:
        if not installed and staged.exists():
            _remove_failed_stage(staged)

    return release


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze a strict all-F861 candidate into a versioned results bundle"
    )
    parser.add_argument("--candidate-dir", type=Path, required=True)
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--scale-points", type=Path, default=SCALE_POINTS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    release = freeze_full861_publication_bundle(
        candidate_dir=args.candidate_dir,
        release_dir=args.release_dir,
        scale_points_path=args.scale_points,
    )
    manifest = json.loads((release / RELEASE_MANIFEST_BASENAME).read_text())
    print(f"FROZEN_FULL861_RELEASE={release}")
    print(f"ANALYSIS_BUNDLE_SHA256={manifest['analysis_bundle_sha256']}")


if __name__ == "__main__":
    main()
