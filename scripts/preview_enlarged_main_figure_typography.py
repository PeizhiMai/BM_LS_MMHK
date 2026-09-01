#!/usr/bin/env python3
"""Build approval-only, enlarged-typography versions of main Figs. 2, 3, 4, and 6.

The live Overleaf project is intentionally not modified.  This driver writes
standalone PDF/PNG previews into ``output/approval`` while reusing the same
data and plotting functions as the canonical manuscript figures.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

import build_compact_finite_tprime_figure as finite_tprime
import build_compact_main_axis_figures as interaction_axes
import build_prl_split_axis_figures as split_base
import build_scale_and_transition_figure as scale_boundary
from plot_combined_density_benchmark import build_condensed_density_benchmark


ROOT = Path(__file__).resolve().parents[1]
OUT = (
    ROOT
    / "output"
    / "approval"
    / "main_figure_typography_revision9_20260827"
    / "figures"
)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    benchmark = build_condensed_density_benchmark(
        stem="fig1_multidensity_benchmark",
        output_dir=OUT,
    )

    u_data, u_values, v_data, epsilon1 = split_base._load_sources()
    metrics = pd.read_csv(split_base.METRICS_OUT)
    old_axis_out = split_base.OUT
    try:
        split_base.OUT = OUT
        mott = interaction_axes.build_compact_mott(
            u_data,
            u_values,
            epsilon1,
            metrics,
        )
        cdw = interaction_axes.build_compact_cdw(
            v_data,
            epsilon1,
            metrics,
        )
    finally:
        split_base.OUT = old_axis_out

    old_tprime_out = finite_tprime.OUT
    try:
        finite_tprime.OUT = OUT
        tprime, _ = finite_tprime.build()
    finally:
        finite_tprime.OUT = old_tprime_out

    scale_pdf = OUT / "fig4_scale_and_transition_boundary.pdf"
    scale_png = OUT / "fig4_scale_and_transition_boundary.png"
    scale_boundary.build_figure(
        out_pdf=scale_pdf,
        out_png=scale_png,
        mixed_momentum_terms=True,
        vertical=True,
        axis_text_scale=1.4,
        write_derived_tables=False,
    )
    scale = {
        "pdf": str(scale_pdf.relative_to(ROOT)),
        "png": str(scale_png.relative_to(ROOT)),
    }

    print("Approval-only enlarged-typography previews:")
    for name, record in (
        ("Fig. 2 benchmark", benchmark),
        ("Fig. 3 Mott", mott),
        ("Fig. 4 CDW", cdw),
        ("Fig. 5 scale and boundary", scale),
        ("Fig. 6 finite tprime", tprime),
    ):
        print(f"  {name}: {record['pdf']}")


if __name__ == "__main__":
    main()
