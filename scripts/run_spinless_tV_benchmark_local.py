#!/usr/bin/env python3
"""Run the complete spinless 16-MMHK t-V benchmark on the local Mac."""

from __future__ import annotations

import argparse
import concurrent.futures
import os
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


V_VALUES = (0.45, 1.0, 2.0)
EXPECTED_TARGETS = 3 * 861


@dataclass(frozen=True)
class Target:
    task_id: int
    V: float
    kx: int
    ky: int
    seed: int

    @property
    def v_label(self) -> str:
        return f"{self.V:g}"

    @property
    def filename(self) -> str:
        return (
            f"L4x4N8V{self.v_label}tp0f{self.kx}x{self.ky}"
            "Q0x0_E0_spinless.dat"
        )


def targets() -> list[Target]:
    rows = []
    task_id = 0
    # Interleave interaction values so partial runs sample every V family.
    for kx in range(41):
        for ky in range(kx, 41):
            for V in V_VALUES:
                task_id += 1
                rows.append(Target(task_id, V, kx, ky, 280_000_000 + task_id))
    if len(rows) != EXPECTED_TARGETS:
        raise RuntimeError(f"Expected {EXPECTED_TARGETS} targets, got {len(rows)}")
    return rows


def is_complete(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size == 0:
        return False
    text = path.read_text(errors="replace")
    return (
        "status\tCOMPLETE" in text
        and "max_iterations\t10000" in text
        and "N\t8" in text
        and "Qx\t0" in text
        and "Qy\t0" in text
    )


def run_one(payload: tuple[Target, str, str, str]) -> tuple:
    target, binary_text, output_text, work_text = payload
    binary = Path(binary_text)
    output_dir = Path(output_text)
    work_dir = Path(work_text)
    destination = output_dir / target.filename
    if is_complete(destination):
        return target.task_id, target.V, target.kx, target.ky, "cached", 0.0, ""

    env = os.environ.copy()
    env.update(
        {
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "MKL_DYNAMIC": "FALSE",
            "OMP_DYNAMIC": "FALSE",
            "DYLD_LIBRARY_PATH": (
                "/Users/cosdis/Downloads/ED/ED_Zhentao/installs/lib:"
                "/opt/intel/oneapi/mkl/latest/lib:"
                "/opt/intel/oneapi/tbb/latest/lib:"
                + env.get("DYLD_LIBRARY_PATH", "")
            ),
        }
    )
    started = time.monotonic()
    with tempfile.TemporaryDirectory(
        prefix=f"sltv_{target.task_id:04d}_", dir=work_dir
    ) as temporary:
        completed = subprocess.run(
            [
                str(binary),
                "8",
                str(target.kx),
                str(target.ky),
                "0",
                "0",
                target.v_label,
                "0",
                str(target.seed),
            ],
            cwd=temporary,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        source = Path(temporary) / target.filename
        elapsed = time.monotonic() - started
        if completed.returncode != 0 or not is_complete(source):
            message = completed.stdout[-12000:]
            return (
                target.task_id,
                target.V,
                target.kx,
                target.ky,
                "failed",
                elapsed,
                message,
            )
        shutil.copy2(source, destination)
    return target.task_id, target.V, target.kx, target.ky, "complete", elapsed, ""


def parse_args():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--binary",
        type=Path,
        default=root / ".codex_tmp/spinless_local/bin/Spinless_tV_sym_E0.x",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "data/spinless_tV_mmhk/raw_20260820",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=root / ".codex_tmp/spinless_local/work",
    )
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--limit", type=int, help="Run only the first N missing targets")
    return parser.parse_args()


def main():
    args = parse_args()
    args.binary = args.binary.resolve()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.work_dir.mkdir(parents=True, exist_ok=True)
    if not args.binary.is_file():
        raise FileNotFoundError(args.binary)

    all_targets = targets()
    cached = sum(is_complete(args.output_dir / row.filename) for row in all_targets)
    pending = [row for row in all_targets if not is_complete(args.output_dir / row.filename)]
    if args.limit is not None:
        pending = pending[: args.limit]
    print(
        f"spinless local batch: total={len(all_targets)} cached={cached} "
        f"launching={len(pending)} workers={args.workers}",
        flush=True,
    )
    if not pending:
        return

    started = time.monotonic()
    completed_count = failed_count = 0
    durations = []
    payloads = [
        (row, str(args.binary), str(args.output_dir), str(args.work_dir))
        for row in pending
    ]
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(run_one, payload): payload[0] for payload in payloads}
        for future in concurrent.futures.as_completed(futures):
            row = futures[future]
            try:
                task_id, V, kx, ky, status, elapsed, message = future.result()
            except Exception as error:  # pragma: no cover - operational guard
                task_id, V, kx, ky = row.task_id, row.V, row.kx, row.ky
                status, elapsed, message = "failed", 0.0, repr(error)
            durations.append(elapsed)
            if status in {"complete", "cached"}:
                completed_count += 1
            else:
                failed_count += 1
                failure = args.work_dir / f"failure_{task_id:04d}_V{V:g}_f{kx}x{ky}.log"
                failure.write_text(message + "\n")
                print(f"FAILED task={task_id} V={V:g} f={kx}x{ky}: {failure}", flush=True)
            done = completed_count + failed_count
            if done % 50 == 0 or done == len(pending):
                wall = time.monotonic() - started
                mean = sum(durations) / len(durations)
                rate = done / wall if wall else 0.0
                eta = (len(pending) - done) / rate if rate else 0.0
                print(
                    f"progress={done}/{len(pending)} complete={completed_count} "
                    f"failed={failed_count} mean_target={mean:.2f}s "
                    f"wall={wall/60:.1f}m eta={eta/60:.1f}m",
                    flush=True,
                )

    total_complete = sum(
        is_complete(args.output_dir / row.filename) for row in all_targets
    )
    print(
        f"FINAL complete={total_complete}/{len(all_targets)} "
        f"new_failures={failed_count} wall={(time.monotonic()-started)/60:.2f}m",
        flush=True,
    )
    if failed_count or (args.limit is None and total_complete != len(all_targets)):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
