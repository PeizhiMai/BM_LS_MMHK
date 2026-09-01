"""Shared visual rules for manuscript figures."""
from __future__ import annotations

from matplotlib.axes import Axes


PANEL_LABEL_X = -0.105
PANEL_LABEL_Y = 0.985
ZERO_DISPERSION_AXIS_LABEL = r"$\omega_{\mathrm{GZ}}(\mathbf{k})/t$"
ZERO_DISPERSION_DIFFERENCE_AXIS_LABEL = r"$\Delta\omega_{\mathrm{GZ}}(\mathbf{k})/t$"
ZERO_DISPERSION_SCALE_AXIS_LABEL = r"GZ coefficient $s_{\mathrm{NN}}$"


def outside_panel_label(
    ax: Axes,
    label: str,
    *,
    color: str = "black",
    fontsize: float = 12.0,
    x: float = PANEL_LABEL_X,
    y: float = PANEL_LABEL_Y,
) -> None:
    """Place an unframed panel label outside the upper-left axes corner."""
    ax.text(
        x,
        y,
        label,
        transform=ax.transAxes,
        ha="right",
        va="top",
        color=color,
        fontsize=fontsize,
        fontweight="bold",
        clip_on=False,
        zorder=30,
    )
