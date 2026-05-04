# Figure Plan

## Fig. 1: Half-filled benchmark

Use: `results/half_filling_comparison.pdf`

Message: The method reproduces the interaction dependence of the Hubbard benchmark observables at `t'=0`, `n=1`. In text, emphasize that double occupancy agrees best for `U/t >= 4`, while magnetization is more sensitive.

## Fig. 2: Doping and `t'`

Use: `results/tprime_overlay_comparison.pdf`

Message: Show how finite `t'=-0.25t` changes the doped observables. At `n=0.8`, `U/t=12`, magnetization drops from about `0.149` to `0.134` and double occupancy from about `0.0179` to `0.0135`.

## Fig. 3: Density sweep for `t'=-0.25`

Use: `results/magnetization_tpn25_wide_density.pdf`

Message: This can be either a main-text figure or supplement. It shows that magnetization is strongest closer to half filling and evolves smoothly over the density grid.

## Fig. 4: Luttinger surface

Current placeholder: `results/spectral_function_from_notebook.png`

Needed final panel:

- Brillouin-zone map of `sign(Re G(k,0))`
- Overlay zero contour where `Re G(k,0)=0`
- Include the noninteracting Fermi-surface contour as a thin reference line
- Recommended cases: `t'=0, n=1`; `t'=-0.25, n=0.875`; optionally `t'=-0.25, n=0.8`
- Caption should explicitly distinguish a zero of `G` from a pole/Fermi surface

## Supplementary Tables

Use:

- `results/half_filling_methods.csv`
- `results/half_filling_deltas.csv`
- `results/mmhk_observables_all_cases.csv`
- `results/tpn25_observables.csv`

These can become machine-readable supplementary data or compact appendix tables.
