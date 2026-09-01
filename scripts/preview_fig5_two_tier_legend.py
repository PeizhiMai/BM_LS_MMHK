#!/usr/bin/env python3
"""Build an approval-only Figure 5 with a larger two-tier legend.

The interaction values occupy the first legend line and the analytic formula
occupies a separate second line.  The previously requested left shift of
panel labels (a) and (c) is retained.  Canonical manuscript figures are not
modified.
"""
from __future__ import annotations

import sys
from pathlib import Path

from matplotlib.axes import Axes


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_compact_finite_tprime_figure as fig5  # noqa: E402
from manuscript_figure_style import (  # noqa: E402
    PANEL_LABEL_X,
    outside_panel_label,
)


OUT = ROOT / "output/approval/fig5_two_tier_legend_20260820"
LEFT_SHIFT = 0.035
LEGEND_FONTSIZE = 10.8
PANEL_D_FORMULA_FONTSIZE = 12.4
PANEL_B_UPWARD_SHIFT = 0.015


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


def build() -> dict[str, str]:
    original_panel_label = fig5.panel_label
    original_output = fig5.OUT
    original_legend = Axes.legend
    two_tier_call_index = 0

    def two_tier_legend(axis, *args, **kwargs):
        nonlocal two_tier_call_index
        handles, labels = axis.get_legend_handles_labels()
        if len(handles) == 4 and kwargs.get("ncol") == 2:
            # The first call is panel (b); move its complete two-line legend
            # upward modestly while retaining a gap below the upper frame.
            is_panel_b = two_tier_call_index == 0
            shift = PANEL_B_UPWARD_SHIFT if is_panel_b else 0.0
            formula_fontsize = (
                LEGEND_FONTSIZE if is_panel_b else PANEL_D_FORMULA_FONTSIZE
            )
            two_tier_call_index += 1
            interaction_legend = original_legend(
                axis,
                handles[:3],
                labels[:3],
                frameon=False,
                ncol=3,
                loc="upper center",
                bbox_to_anchor=(0.50, 0.995 + shift),
                fontsize=LEGEND_FONTSIZE,
                handlelength=1.10,
                columnspacing=0.62,
                labelspacing=0.08,
                borderaxespad=0.08,
            )
            axis.add_artist(interaction_legend)
            return original_legend(
                axis,
                [handles[3]],
                [labels[3]],
                frameon=False,
                ncol=1,
                loc="upper center",
                bbox_to_anchor=(0.50, 0.915 + shift),
                fontsize=formula_fontsize,
                handlelength=1.30,
                labelspacing=0.08,
                borderaxespad=0.02,
            )
        return original_legend(axis, *args, **kwargs)

    OUT.mkdir(parents=True, exist_ok=True)
    fig5.panel_label = shifted_panel_label
    fig5.OUT = OUT
    Axes.legend = two_tier_legend
    try:
        outputs, _ = fig5.build()
        return outputs
    finally:
        Axes.legend = original_legend
        fig5.panel_label = original_panel_label
        fig5.OUT = original_output


def main() -> None:
    outputs = build()
    print(f"Approval preview written to {ROOT / outputs['pdf']}")
    print("Legend layout: three interaction values, then formula on its own line")
    print(f"Legend fontsize: {LEGEND_FONTSIZE:.1f} pt")


if __name__ == "__main__":
    main()
