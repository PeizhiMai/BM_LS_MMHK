#!/usr/bin/env python3
"""Build an approval-only Figure 1 with labels (a) and (c) shifted left."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import plot_combined_density_benchmark as fig1  # noqa: E402


OUT = ROOT / "output/approval/fig1_panel_labels_left_20260820"
LEFT_SHIFT = 0.035


def main() -> None:
    original_panel_label = fig1.panel_label

    def shifted_panel_label(ax, label, *, x=-0.105):
        if label in {"(a)", "(c)"}:
            x -= LEFT_SHIFT
        return original_panel_label(ax, label, x=x)

    OUT.mkdir(parents=True, exist_ok=True)
    fig1.panel_label = shifted_panel_label
    try:
        outputs = fig1.build_condensed_density_benchmark(
            stem="fig1_multidensity_benchmark",
            output_dir=OUT,
        )
    finally:
        fig1.panel_label = original_panel_label

    print(f"Approval preview written to {ROOT / outputs['pdf']}")
    print(f"Labels (a) and (c) shifted left by {LEFT_SHIFT:.3f} axes width")


if __name__ == "__main__":
    main()
