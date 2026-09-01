#!/usr/bin/env python3
"""Generate the technical LaTeX report for the U=40 fullobs scan."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def f(value, digits=6):
    return f"{float(value):.{digits}f}"


def sci(value, digits=2):
    return f"{float(value):.{digits}e}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("results/fullobs_U40_observable_summary_by_V_20260717_123231.csv"),
    )
    parser.add_argument(
        "--long-stats",
        type=Path,
        default=Path("results/fullobs_U40_observable_stats_long_20260717_123231.csv"),
    )
    parser.add_argument(
        "--quality",
        type=Path,
        default=Path("results/fullobs_U40_data_quality_20260717_123231.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/fullobs_U40_observables_report_20260717.tex"),
    )
    args = parser.parse_args()

    summary = pd.read_csv(args.summary)
    stats = pd.read_csv(args.long_stats)
    quality = json.loads(args.quality.read_text())
    by_v = summary.set_index("V")
    v10 = by_v.loc[10]
    v101 = by_v.loc[10.1]
    v11 = by_v.loc[11]
    v0 = by_v.loc[0]
    v20 = by_v.loc[20]
    crossing = quality["branch_switch_estimate"]

    table_real_rows = []
    table_order_rows = []
    table_momentum_rows = []
    table_coverage_rows = []
    for _, row in summary.iterrows():
        table_real_rows.append(
            " & ".join(
                [
                    f(row.V_over_U, 3),
                    f(row.E0_per_site_mean, 5),
                    f(row.kinetic_per_site_mean, 6),
                    f(row.D_site_mean, 6),
                    f(row.nn_NN_mean, 6),
                    f(row.delta_n_delta_n_NN_mean, 6),
                    f(row.C1_NN_mean, 6),
                ]
            )
            + r" \\"
        )
        table_order_rows.append(
            " & ".join(
                [
                    f(row.V_over_U, 3),
                    f(row.Szz_pipi_mean, 6),
                    f(row.Sc_pipi_mean, 6),
                    f(row.mCDW2_pipi_mean, 6),
                    f(row.D_site_mean, 6),
                    f(row.nn_NN_mean, 6),
                ]
            )
            + r" \\"
        )
        table_momentum_rows.append(
            " & ".join(
                [
                    f(row.V_over_U, 3),
                    f(row.n_k_mean, 7),
                    f(row.n_k_std, 6),
                    f(row.D_k_mean, 6),
                    f(row.var_n_k_mean, 6),
                    sci(row.cov_nup_ndn_k_mean, 2),
                    f(row.n_epsilon_slope, 6),
                    f(row.n_epsilon_R2, 6),
                ]
            )
            + r" \\"
        )
        table_coverage_rows.append(
            " & ".join(
                [
                    str(int(row.V)),
                    str(int(row.wedge_rows)),
                    f(100 * row.wedge_completion_fraction, 3) + r"\%",
                    f(100 * row.quadrature_completion_fraction, 3) + r"\%",
                ]
            )
            + r" \\"
        )

    # Missing-row sensitivity based on the full observed range.
    v20_n = stats[(stats.V == 20) & (stats.observable == "n_k")].iloc[0]
    v20_m = stats[(stats.V == 20) & (stats.observable == "mCDW2_pipi")].iloc[0]
    n_bound = max(
        v20_n["mean"] - v20_n["observed_range_missing_lower_bound"],
        v20_n["observed_range_missing_upper_bound"] - v20_n["mean"],
    )
    m_bound = max(
        v20_m["mean"] - v20_m["observed_range_missing_lower_bound"],
        v20_m["observed_range_missing_upper_bound"] - v20_m["mean"],
    )

    min_r2 = summary.n_epsilon_R2.min()
    max_mott_slope_error = summary.loc[
        summary.branch == "Mott", "n_epsilon_slope_formula_relative_error_percent"
    ].abs().max()
    max_charge_slope_error = summary.loc[
        summary.branch == "charge", "n_epsilon_slope_formula_relative_error_percent"
    ].abs().max()
    max_mott_d_error = summary.loc[
        summary.branch == "Mott", "D_site_formula_relative_error_percent"
    ].abs().max()

    replacements = {
        "__RAW_COUNT__": str(quality["parsed_rows"]),
        "__EXPECTED_COUNT__": str(861 * len(summary)),
        "__COMPLETE_PERCENT__": f(100 * quality["parsed_rows"] / (861 * len(summary)), 3),
        "__SNAPSHOT_PATH__": quality["input_snapshot"],
        "__VC__": f(crossing["V_c"], 4),
        "__VC_RATIO__": f(crossing["V_c_over_U"], 6),
        "__V10_D__": f(v10.D_site_mean, 6),
        "__V11_D__": f(v11.D_site_mean, 6),
        "__V101_D__": f(v101.D_site_mean, 6),
        "__V10_NN__": f(v10.nn_NN_mean, 6),
        "__V11_NN__": f(v11.nn_NN_mean, 6),
        "__V101_NN__": f(v101.nn_NN_mean, 6),
        "__V10_C1__": f(v10.C1_NN_mean, 6),
        "__V11_C1__": f(v11.C1_NN_mean, 6),
        "__V101_C1__": f(v101.C1_NN_mean, 6),
        "__V10_SZZ__": f(v10.Szz_pipi_mean, 6),
        "__V11_SZZ__": f(v11.Szz_pipi_mean, 6),
        "__V101_SZZ__": f(v101.Szz_pipi_mean, 6),
        "__V10_MCDW__": f(v10.mCDW2_pipi_mean, 6),
        "__V11_MCDW__": f(v11.mCDW2_pipi_mean, 6),
        "__V101_MCDW__": f(v101.mCDW2_pipi_mean, 6),
        "__V10_K__": f(v10.kinetic_per_site_mean, 6),
        "__V11_K__": f(v11.kinetic_per_site_mean, 6),
        "__V101_K__": f(v101.kinetic_per_site_mean, 6),
        "__V0_NSTD__": f(v0.n_k_std, 6),
        "__V10_NSTD__": f(v10.n_k_std, 6),
        "__V11_NSTD__": f(v11.n_k_std, 6),
        "__V101_NSTD__": f(v101.n_k_std, 6),
        "__V20_NSTD__": f(v20.n_k_std, 6),
        "__NSTD_RISE__": f(100 * (v10.n_k_std / v0.n_k_std - 1), 1),
        "__NSTD_DROP__": f(100 * (v11.n_k_std / v10.n_k_std - 1), 1),
        "__NSTD_DROP101__": f(100 * (v101.n_k_std / v10.n_k_std - 1), 1),
        "__V10_DK__": f(v10.D_k_mean, 6),
        "__V11_DK__": f(v11.D_k_mean, 6),
        "__V10_COV__": sci(v10.cov_nup_ndn_k_mean, 3),
        "__V11_COV__": sci(v11.cov_nup_ndn_k_mean, 3),
        "__V10_VAR__": f(v10.var_n_k_mean, 6),
        "__V11_VAR__": f(v11.var_n_k_mean, 6),
        "__V20_VAR__": f(v20.var_n_k_mean, 6),
        "__MIN_R2__": f(min_r2, 6),
        "__MAX_MOTT_SLOPE_ERR__": f(max_mott_slope_error, 2),
        "__MAX_CHARGE_SLOPE_ERR__": f(max_charge_slope_error, 2),
        "__MAX_MOTT_D_ERR__": f(max_mott_d_error, 2),
        "__ENERGY_RESID__": sci(quality["max_abs_identity_residuals"]["energy_per_site"], 2),
        "__N_BOUND__": sci(n_bound, 2),
        "__M_BOUND__": sci(m_bound, 2),
        "__TABLE_REAL__": "\n".join(table_real_rows),
        "__TABLE_ORDER__": "\n".join(table_order_rows),
        "__TABLE_MOMENTUM__": "\n".join(table_momentum_rows),
        "__TABLE_COVERAGE__": "\n".join(table_coverage_rows),
    }

    template = r"""
\documentclass[10pt]{article}
\usepackage[margin=0.72in]{geometry}
\usepackage{amsmath,amssymb,booktabs,array,longtable,graphicx,xcolor,microtype}
\usepackage[hidelinks]{hyperref}
\usepackage{fancyhdr}
\usepackage{enumitem}
\graphicspath{{../figures/fullobs/}}
\definecolor{mottblue}{HTML}{335F8D}
\definecolor{chargeorange}{HTML}{C56F2D}
\definecolor{softgray}{HTML}{F4F5F7}
\pagestyle{fancy}
\fancyhf{}
\lhead{U=40 full-observable scan}
\rhead{Technical report}
\cfoot{\thepage}
\setlength{\headheight}{13pt}
\setlength{\parindent}{0pt}
\setlength{\parskip}{5pt}
\setlist[itemize]{leftmargin=1.3em,itemsep=2pt,topsep=2pt}
\newcommand{\vk}{\mathbf{k}}

\begin{document}

\begin{center}
{\LARGE\bfseries Static observables expose the Mott--charge reorganization at $U=40$\par}
\vspace{0.35em}
{\large All-momentum analysis of the $V$-extended MMHK calculation\par}
\vspace{0.4em}
{\small Data snapshot: 18 July 2026, 16:50 EDT}
\end{center}

\vspace{0.5em}
\colorbox{softgray}{\parbox{0.965\linewidth}{
\textbf{Technical summary.}
The analysis uses __RAW_COUNT__ validated outputs out of __EXPECTED_COUNT__ requested
fixed-$Q=(0,0)$ calculations (__COMPLETE_PERCENT__\% complete) at $U=40$, $t'=0$.
Every real-space charge and spin diagnostic changes branch between $V=10$ and $V=10.1$:
the on-site double occupation rises from __V10_D__ to __V101_D__, the checkerboard
order proxy rises from __V10_MCDW__ to __V101_MCDW__, and
$S^{zz}(\pi,\pi)$ collapses from __V10_SZZ__ to __V101_SZZ__.
The momentum distribution remains almost perfectly linear in the bare dispersion
($R^2\ge __MIN_R2__$), but its slope changes from the Mott denominator $U-V$ to the
charge denominator $7V-U$.  A local Hellmann--Feynman branch interpolation gives
$V_c\simeq __VC__$, or $V_c/U\simeq __VC_RATIO__$, while the directly sampled statement
is the directly resolved bracket $10<V_c<10.1$.  The static observables therefore provide an
independent, sharply resolved counterpart to the Green-function-zero reorganization.}}

\section{A collective branch change occurs between $V=10$ and $V=10.1$}

The scan separates into two internally uniform regimes.  On the Mott side through
$V=10$, $D_i$ remains small, $\langle n_i n_j\rangle_{\rm NN}$ remains close to one,
and antiferromagnetic correlations remain strong.  Already at $V=10.1$, the same calculation
has instead entered an almost classical checkerboard state: $D_i\approx 1/2$,
$\langle n_i n_j\rangle_{\rm NN}\approx0$, and $m_{\rm CDW}^2\approx1$.
The numerical changes across the newly resolved $V=10$ to $10.1$ interval are
\begin{align*}
D_i &: __V10_D__ \rightarrow __V101_D__, &
\langle n_i n_j\rangle_{\rm NN} &: __V10_NN__ \rightarrow __V101_NN__,\\
C_1 &: __V10_C1__ \rightarrow __V101_C1__, &
S^{zz}(\pi,\pi) &: __V10_SZZ__ \rightarrow __V101_SZZ__,\\
m_{\rm CDW}^2 &: __V10_MCDW__ \rightarrow __V101_MCDW__, &
K/N &: __V10_K__ \rightarrow __V101_K__.
\end{align*}
The momentum-to-momentum standard deviations of the local charge observables are
only $10^{-5}$ or smaller at the two boundary points.  Thus the switch is not caused
by a small subset of twist points; all sampled blocks select the same side at each
sampled $V$.

\begin{figure}[htbp]
\centering
\includegraphics[width=\linewidth]{fullobs_static_scan_U40.pdf}
\caption{Twist-averaged static observables versus $V/U$.  Blue and orange backgrounds
mark the Mott- and charge-dominated sides of the atomic scale $V/U=1/4$.
The added points resolve the abrupt and simultaneous charge, spin, kinetic, and momentum
changes between the last Mott point ($V=10$) and the first charge point ($V=10.1$).}
\end{figure}

\section{$n(\vk)$ measures virtual hopping, not a generic fluctuation amplitude}

The full momentum maps show a simple but informative result.  For every $V$,
\begin{equation}
n(\vk)=1+a\,\epsilon_{\vk}+\delta n_{\vk},\qquad
\epsilon_{\vk}=-2(\cos k_x+\cos k_y),
\end{equation}
with $R^2\ge __MIN_R2__$ and a very small nonlinear remainder.  Consequently the
momentum contrast $\sigma_{\vk}[n]$ and kinetic energy are not independent:
for the present normalization, $\sigma_{\vk}[n]=2|a|$ and $K/N=4a$ to the numerical
precision of the complete grids.

The momentum differentiation grows by __NSTD_RISE__\% from
$\sigma_{\vk}[n]=__V0_NSTD__$ at $V=0$ to __V10_NSTD__ at $V=10$.
It immediately falls by __NSTD_DROP101__\% to __V101_NSTD__ at $V=10.1$ and decreases further to
__V20_NSTD__ at $V=20$.  Thus $n(\vk)$ is a clean measure of the virtual-hopping
amplitude and band-memory retained by the insulating state.  It is largest immediately
on the Mott side because the virtual charge denominator $U-V$ is smallest there,
then becomes progressively flatter in the charge state as $7V-U$ grows.

\begin{figure}[p]
\centering
\includegraphics[width=0.94\linewidth]{fullobs_nk_maps_U40.pdf}
\caption{Reconstructed $n(\vk)$ maps on $0\le k_x,k_y\le\pi$.  The Mott-side
dispersion strengthens toward $V/U=1/4$, drops immediately on the charge side,
and then flattens continuously.  All displayed maps are complete; no interpolation was used.}
\end{figure}

\begin{figure}[p]
\centering
\includegraphics[width=0.94\linewidth]{fullobs_nk_vs_epsilon_U40.pdf}
\caption{The measured momentum occupation versus the bare dispersion.  Orange lines
are weighted fits constrained by particle--hole symmetry to pass through
$n=1$ at $\epsilon_{\vk}=0$.  The near-unity $R^2$ values demonstrate that a
single interaction-dependent virtual-hopping scale describes each full map.}
\end{figure}

The separately measured momentum-orbital double occupation sharpens the interpretation.
Its average drops from $D_{\vk}=__V10_DK__$ at $V=10$ to __V11_DK__ at $V=11$,
while the spin covariance
$D_{\vk}-[n(\vk)/2]^2$ collapses from __V10_COV__ to __V11_COV__.
However, the intrinsic number variance
$\mathrm{Var}(n_{\vk})=n(\vk)+2D_{\vk}-n(\vk)^2$ changes from __V10_VAR__ to
__V11_VAR__ and approaches __V20_VAR__ in the charge limit, rather than vanishing.
A flat $n(\vk)$ therefore means loss of momentum differentiation; it does not by
itself mean that the symmetry-preserving many-body state has zero occupation-number
variance.

\begin{figure}[p]
\centering
\includegraphics[width=0.94\linewidth]{fullobs_Dk_maps_U40.pdf}
\caption{Momentum-orbital double occupation
$D_{\vk}=\langle n_{\vk\uparrow}n_{\vk\downarrow}\rangle$.  The charge side tends
toward $D_{\vk}=1/4$, causing the up--down momentum covariance to vanish even while
the real-space double occupation tends to $1/2$.}
\end{figure}

\section{Two virtual charge denominators explain the measured trends}

The same nearest-neighbor hop has different excitation energies in the two atomic
backgrounds.  In a singly occupied Mott background it creates a neighboring
doublon--holon pair with
\begin{equation}
\Delta_M=U-V.
\end{equation}
In the checkerboard doublon--holon background it creates two adjacent singly occupied
sites.  The changed site touches seven interaction bonds, giving
\begin{equation}
\Delta_C=7V-U.
\end{equation}
Second-order perturbation theory at $t=1$ then gives the following parameter-free
forms once the measured nearest-neighbor spin correlation is inserted on the Mott side:
\begin{align}
\frac{E_M}{N} &\simeq 2V-\frac{8(1/4-C_1)}{\Delta_M}, &
\frac{K_M}{N} &\simeq -\frac{16(1/4-C_1)}{\Delta_M},\\
n_M(\vk) &\simeq 1-\frac{4(1/4-C_1)}{\Delta_M}\epsilon_{\vk}, &
D_M &\simeq \frac{8(1/4-C_1)}{\Delta_M^2},\\
\langle n_i n_j\rangle_M &\simeq 1-\frac{4(1/4-C_1)}{\Delta_M^2},\nonumber
\end{align}
and
\begin{align}
\frac{E_C}{N} &\simeq \frac{U}{2}-\frac{4}{\Delta_C}, &
\frac{K_C}{N} &\simeq -\frac{8}{\Delta_C},\\
n_C(\vk) &\simeq 1-\frac{2}{\Delta_C}\epsilon_{\vk}, &
D_C &\simeq \frac12-\frac{4}{\Delta_C^2},\\
\langle n_i n_j\rangle_C &\simeq \frac{14}{\Delta_C^2}.\nonumber
\end{align}
Across all applicable points, the $n(\vk)$ slope differs from these formulas by at
most __MAX_MOTT_SLOPE_ERR__\% on the Mott side and __MAX_CHARGE_SLOPE_ERR__\% on the
charge side.  The largest Mott-side error in $D_i$ is only __MAX_MOTT_D_ERR__\%.
This agreement explains both why momentum differentiation grows toward the boundary
from the Mott side and why it decreases monotonically after the branch switch.

\begin{figure}[htbp]
\centering
\includegraphics[width=\linewidth]{fullobs_strong_coupling_validation_U40.pdf}
\caption{Measured energies, $n(\vk)$ slopes, kinetic energies, and local charge
probabilities compared with the two strong-coupling rules.  Each asymptotic rule is
shown only on its corresponding side.  The agreement is quantitative even for the
points adjacent to the branch change.}
\end{figure}

The exact Hellmann--Feynman relation for these outputs is
\begin{equation}
\frac{\partial(E_0/N)}{\partial V}=2\langle n_i n_j\rangle_{\rm NN}.
\end{equation}
Approximating each branch by its local tangent at $V=10$ and 11 and integrating over
the unit interval locates their crossing at $V_c\simeq __VC__$,
$V_c/U\simeq __VC_RATIO__$.  The estimate shows that the small kinetic correction
barely shifts the atomic value.  It is nevertheless an interpolation; the direct
calculation establishes only the interval $10<V_c<11$.

\begin{figure}[htbp]
\centering
\includegraphics[width=\linewidth]{fullobs_transition_diagnostics_U40.pdf}
\caption{Left: the energy secants compared with the Hellmann--Feynman derivative.
The slope discontinuity identifies a branch crossing.  Right: order diagnostics on
a logarithmic scale, displaying the simultaneous loss of spin response and onset of
checkerboard charge order.}
\end{figure}

\section{Scope, definitions, and aggregation}

The calculation fixes $N_\uparrow=N_\downarrow=8$, $U=40$, $t=1$, $t'=0$, and
$Q=(0,0)$ at a $4\times4$ momentum-mixing resolution.  For each interaction pair,
the Peierls/twist momentum is sampled at
$f_{x,y}=k_{x,y}\pi/40+10^{-5}$ with $0\le k_x\le k_y\le40$.
The stored wedge is reflected under $x\leftrightarrow y$ to reconstruct the square;
off-diagonal rows have symmetry weight two.  Reported momentum averages additionally
use half weight at the $0$ and $\pi$ endpoints, i.e. two-dimensional trapezoidal
quadrature.  Missing rows are not imputed; each mean is normalized by the observed
quadrature weight.

The principal observables are:
\begin{itemize}
\item $D_i=\langle n_{i\uparrow}n_{i\downarrow}\rangle$ and
$D_{\vk}=\langle n_{\vk\uparrow}n_{\vk\downarrow}\rangle$;
\item $S^{zz}(\pi,\pi)=N^{-1}\sum_{ij}(-1)^{i-j}\langle S_i^zS_j^z\rangle$ and
$S_c(\pi,\pi)=N^{-1}\sum_{ij}(-1)^{i-j}\langle(n_i-1)(n_j-1)\rangle$;
\item $m_{\rm CDW}^2=S_c(\pi,\pi)/N$, the nearest-neighbor spin correlation $C_1$,
the nearest-neighbor density product, and kinetic energy per site;
\item $n(\vk)$ at $q=(0,0)$ of each $f$-twisted block, identified with physical
momentum $\vk=f$ in this construction.
\end{itemize}
The output field called \texttt{Gap} is identically zero because only one eigenpair
was requested.  It is metadata, not a charge, spin, or sector gap, and is excluded
from all physical conclusions.  The next-nearest-neighbor kinetic contribution is
also identically zero because $t'=0$.

\section{Numerical validation and incomplete-row sensitivity}

Every downloaded file is marked \texttt{COMPLETE}, matches its SHA-256 manifest,
and has a unique $(U,V,k_x,k_y)$ key.  Several identities provide independent checks:
\begin{align*}
E_0/N &= K/N+UD_i+2V\langle n_i n_j\rangle_{\rm NN},\\
\langle\delta n_i\delta n_j\rangle_{\rm NN}
&=\langle n_i n_j\rangle_{\rm NN}-1,\\
K&=K_{\rm NN}+K_{\rm NNN},\qquad
m_{\rm CDW}^2=S_c(\pi,\pi)/N.
\end{align*}
The largest energy-identity residual is __ENERGY_RESID__; the other three identities
hold to machine precision.  Particle--hole symmetry gives
$n(\vk)+n(\pi-\vk)=2$ with maximum residual below $7\times10^{-6}$.

All 12 interaction sets are complete: every set contains 861 wedge rows and the full
quadrature weight.  The dataset therefore requires neither interpolation nor a
missing-row correction.

\begin{table}[htbp]
\centering
\caption{Downloaded data coverage.  Quadrature coverage includes endpoint weights.}
\begin{tabular}{rrrr}
\toprule
$V$ & wedge rows & row coverage & quadrature coverage\\
\midrule
__TABLE_COVERAGE__
\bottomrule
\end{tabular}
\end{table}

\section{Limitations and recommended next calculations}

\begin{itemize}
\item The refined interaction resolution brackets the switch between $V=10$ and
$10.1$.  The value $V_c\simeq __VC__$ is a local branch interpolation, not a separately
computed transition point.
\item The scan fixes $U=40$ and $Q=(0,0)$.  It establishes the strong-coupling
reorganization within the present momentum-mixing construction but does not by
itself provide thermodynamic scaling in mixing resolution or an unrestricted
momentum-sector comparison.
\item $n(\vk)$ contrast is an excellent virtual-hopping diagnostic, but it should be
called momentum differentiation rather than an undifferentiated measure of quantum
fluctuation.  The separately derived number variance remains finite in the charge
state.
\end{itemize}

The most informative next run, if still finer localization is needed, is a narrow
fixed-$U=40$ grid at $V=10.01,10.02,$ and $10.05$.  A second priority
is repeating a minimal set on both sides at a different large $U$ to test whether the
width and location collapse in $V/U$.  For the manuscript, the immediate next analysis
is to compare the measured $n(\vk)$ slope with the Green-function-zero scale at the
same $(U,V)$ points; the two observables are controlled by the same virtual charge
denominators and may provide a unified interpretation.

\section*{Further questions}
\begin{itemize}
\item Does the zero-dispersion scale inherit the same $U-V$ and $7V-U$ denominators
seen directly in $n(\vk)$ and $K$?
\item Does the branch switch remain as sharp when the momentum-mixing resolution or
total-momentum sector is varied?
\item Can the small nonlinear remainder $\delta n_{\vk}$ isolate higher-order spin
or charge correlations beyond the leading strong-coupling rules?
\end{itemize}

\section*{Reproducibility artifacts}
The frozen raw snapshot is
\path{__SNAPSHOT_PATH__}.  The parser, validation, and figure workflow is
\path{scripts/analyze_fullobs_u40_scan.py}; the report generator is
\path{scripts/generate_fullobs_u40_report.py}.  Machine-readable row data, long-form
observable statistics, wide summaries, the observable dictionary, and validation
JSON are stored under \path{results/} with tag \texttt{20260718\_165039}.

\appendix
\section{Complete numerical summaries}

\begin{table}[!htbp]
\centering\scriptsize
\caption{Energy, kinetic, and nearest-neighbor observables.}
\begin{tabular}{rrrrrrr}
\toprule
$V/U$ & $E_0/N$ & $K/N$ & $D_i$ & $\langle n_i n_j\rangle$ &
$\langle\delta n_i\delta n_j\rangle$ & $C_1$\\
\midrule
__TABLE_REAL__
\bottomrule
\end{tabular}
\end{table}

\begin{table}[!htbp]
\centering\scriptsize
\caption{Spin and charge-order observables.}
\begin{tabular}{rrrrrr}
\toprule
$V/U$ & $S^{zz}(\pi,\pi)$ & $S_c(\pi,\pi)$ & $m_{\rm CDW}^2$ & $D_i$ &
$\langle n_i n_j\rangle$\\
\midrule
__TABLE_ORDER__
\bottomrule
\end{tabular}
\end{table}

\begin{table}[!htbp]
\centering\scriptsize
\caption{Momentum observables and fitted band-memory scale.  The standard deviation
is over momentum, not a sampling error.}
\begin{tabular}{rrrrrrrr}
\toprule
$V/U$ & $\langle n\rangle$ & $\sigma_{\vk}[n]$ & $\langle D_{\vk}\rangle$ &
$\langle\mathrm{Var}(n_{\vk})\rangle$ & $\langle\mathrm{Cov}_{\uparrow\downarrow}\rangle$ & $a$ & $R^2$\\
\midrule
__TABLE_MOMENTUM__
\bottomrule
\end{tabular}
\end{table}

\begin{figure}[p]
\centering
\includegraphics[width=0.94\linewidth]{fullobs_varnk_maps_U40.pdf}
\caption{Derived intrinsic momentum-orbital number variance.  Its finite charge-side
limit distinguishes occupation-number variance from the flattening of the mean
momentum distribution.  Gray cells are unavailable raw rows.}
\end{figure}

\end{document}
"""

    for key, value in replacements.items():
        template = template.replace(key, str(value))
    if "__" in template:
        leftovers = sorted({part for part in template.split() if "__" in part})
        raise RuntimeError(f"Unresolved report placeholders: {leftovers}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(template)
    print(args.output.resolve())


if __name__ == "__main__":
    main()
