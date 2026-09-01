# Main Figure 1 finite-reference guide

Main-text Figure 1 uses a deliberately strict, deduplicated literature subset. The
selection rules are:

1. exclude thermodynamic-limit extrapolations;
2. require TABC for CP-AFQMC and exclude BCS-state rows;
3. at fixed `(n,U)`, retain the largest finite CP-AFQMC system (the selected
   systems are all `20x8`);
4. compare the retained CP-AFQMC energy with the unextrapolated `4x4` DMET
   energy and keep the lower value;
5. use the double occupancy from the selected energy's method and system when
   available; otherwise use the closest result at exactly the same `(n,U)`;
6. never borrow double occupancy across `U` or density.

The visual encoding is deliberately independent of these source-selection
rules:

- color always identifies density: red for `n=1`, blue for `n=0.875`, and
  purple for `n=0.8`;
- filled circles connected by lines are MMHK;
- open circles are AFQMC or CP-AFQMC;
- open triangles are DMET.

The files supporting the selection retain their established `figS2` provenance
names from before the figure was promoted:

- all strict finite candidates:
  `results/figS2_filtered_candidate_data.csv`;
- final selected comparison:
  `results/figS2_selected_comparison_data.csv`;
- selected half-filled references:
  `results/figS2_selected_half_filling_references.csv`;
- one-row-per-doped-open-marker inventory:
  `results/figS2_open_marker_inventory.csv`;
- machine-readable filter and pairing audit:
  `results/figS2_source_filter_audit.json`.

## 1. Selected finite TABC CP-AFQMC energies

Panel (a) contains three open blue circles at `n=0.875`. Here blue denotes
density and the open-circle shape denotes CP-AFQMC. At each interaction,
the `20x8` TABC calculation is the largest available finite system:

| U/t | Selected system/state | Energy |
|---:|---|---:|
| 6 | `20x8`, stripe 10 | -0.8701958 |
| 8 | `20x8`, stripe 10 | -0.7703 |
| 12 | `20x8`, stripe 10 | -0.6449745 |

At `U/t=6` and 8 these energies are lower than the available `4x4` DMET
energies. At `U/t=12`, no retained DMET energy is available. No PBC,
open-boundary, pinned, UHF, DMET-stripe, or BCS-state row from the stripe
table is plotted.

Source: <https://github.com/zhengbx/stripe_data>

## 2. Selected unextrapolated 4x4 DMET values

The open triangles come from the LeBlanc et al. ancillary files. Their edge
color identifies density:

- panel (a), `n=0.8`: four selected energies at `U/t=2,4,6,8`;
- panel (a), `n=0.875`: two selected energies at `U/t=2,4`;
- panel (b), `n=0.8`: two double occupancies at `U/t=2,4`, each
  corresponding to its selected DMET energy;
- panel (b), `n=0.875`: one double occupancy at `U/t=8`.

The last point is the only fallback. The selected energy at
`(n,U/t)=(0.875,8)` is the `20x8` CP-AFQMC result, but its source table does
not report double occupancy. The `4x4` DMET double occupancy at exactly the
same `(n,U)` is therefore retained. No double occupancy is plotted for
`(0.875,6)` or `(0.875,12)`.

No `2x2`, `4x2`, or `8x2` embedding and no DMET thermodynamic extrapolation is
shown.

Source: <https://doi.org/10.1103/PhysRevX.5.041041>

## 3. Half-filled references

At each half-filled `U`, panel (a) keeps the lower AFQMC or DMET energy and
panel (b) uses the double occupancy reported by that same method:

| U/t | Selected energy and D method |
|---:|---|
| 2, 4 | DMET |
| 6, 8, 12 | AFQMC |

Panel (c) retains both directly reported AFQMC and DMET magnetizations because
magnetization is not paired to the energy through the selection rule.

## Marker interpretation

- Filled colored circles connected by lines are MMHK.
- Open circles are AFQMC/CP-AFQMC; the blue doped circles are the selected
  largest-system TABC energies.
- Open triangles are selected unextrapolated `4x4` DMET quantities, with edge
  color carrying density rather than method.
- Both direct half-filled magnetic estimates are shown as red open symbols in
  panel (c).
- Every marker is placed at its exact physical `U/t`; method and density are
  distinguished only by marker shape, fill, and color.
