#!/usr/bin/env python3
"""Build approval-only previews with left-column panel labels shifted left.

This script deliberately writes to ``output/approval`` and does not replace
the canonical manuscript figures.  It uses the current compact Figure 2,
Figure 3, and Figure 5 builders, changing only labels (a) and (c).
"""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_compact_finite_tprime_figure as fig5  # noqa: E402
import build_compact_main_axis_figures as fig23  # noqa: E402
from manuscript_figure_style import (  # noqa: E402
    PANEL_LABEL_X,
    outside_panel_label,
)


OUT = ROOT / "output/approval/fig235_panel_labels_left_20260820"
LEFT_SHIFT = 0.035


def build_figures_2_and_3() -> None:
    """Build Figures 2 and 3 with only (a) and (c) shifted left."""
    original_panel_label = fig23.base._panel_label
    original_output = fig23.base.OUT

    def shifted_panel_label(ax, text, *, x=-0.13, y=0.985):
        if text in {"(a)", "(c)"}:
            x -= LEFT_SHIFT
        return original_panel_label(ax, text, x=x, y=y)

    fig23.base._panel_label = shifted_panel_label
    fig23.base.OUT = OUT
    try:
        u_data, u_values, v_data, epsilon1 = fig23.base._load_sources()
        metrics = fig23.base._axis_metrics(
            u_data, u_values, v_data, epsilon1
        )
        fig23.build_compact_mott(u_data, u_values, epsilon1, metrics)
        fig23.build_compact_cdw(v_data, epsilon1, metrics)
    finally:
        fig23.base._panel_label = original_panel_label
        fig23.base.OUT = original_output


def build_figure_5() -> None:
    """Build Figure 5 with only (a) and (c) shifted left."""
    original_panel_label = fig5.panel_label
    original_output = fig5.OUT

    def shifted_panel_label(
        ax,
        label,
        *,
        color="black",
        framed=True,
        outside_top_tick=False,
    ):
        del framed, outside_top_tick
        x = PANEL_LABEL_X - LEFT_SHIFT if label in {"(a)", "(c)"} else PANEL_LABEL_X
        outside_panel_label(
            ax,
            label,
            color=color,
            fontsize=11.5,
            x=x,
        )

    fig5.panel_label = shifted_panel_label
    fig5.OUT = OUT
    try:
        fig5.build()
    finally:
        fig5.panel_label = original_panel_label
        fig5.OUT = original_output


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    build_figures_2_and_3()
    build_figure_5()
    print(f"Approval previews written to {OUT}")
    print(f"Left-column panel-label shift: {LEFT_SHIFT:.3f} axes width")


if __name__ == "__main__":
    main()
