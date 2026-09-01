# Spinless 16-MMHK benchmark against 8x8-PBC t-V data

**Date:** 2026-08-20

## Calculation

The common Hamiltonian is

\[H=-t\sum_{\langle ij\rangle}(c_i^\dagger c_j+\mathrm{h.c.})+V\sum_{\langle ij\rangle}n_i n_j,\qquad t=1,\]

at half filling. For each of V/t = 1, 2, and 4, the spinless 16-MMHK calculation used all 861 symmetry-reduced points of the 41x41 mixed-momentum grid. At every point it diagonalized the complete N=8 Hilbert space (dimension 12,870), thereby minimizing over all 16 total-momentum sectors rather than assuming Q=(0,0). Every output is marked COMPLETE and used a 10,000-step Lanczos ceiling.

The integral uses kx<->ky symmetry and trapezoidal endpoint weights. Its reconstructed full-grid weight is 1600. The 21x21 nested-grid check has weight 400.

## Energies

| V/t | 16-MMHK E0/Ns | lowest reported 8x8-PBC E0/Ns | method | signed difference | absolute percentage | 21x21 minus 41x41 |
|---:|---:|---:|:---|---:|---:|---:|
| 1 | -0.467675038987 | -0.460655105751 | CT-QMC | -0.007019933236 | 1.5239% | -3.150e-06 |
| 2 | -0.292044365877 | -0.292399967429 | CT-QMC | +0.000355601552 | 0.1216% | -1.949e-06 |
| 4 | -0.160237430049 | -0.160134400663 | DMRG | -0.000103029387 | 0.0643% | -3.796e-08 |

The reference selector is simply the lower of the two reported finite-size energies at each V: CT-QMC for V=1,2 and DMRG for V=4. This is a transparent benchmark convention, not a claim that those values are exact thermodynamic-limit energies. The V=4 CT-QMC entry has a substantially larger reported variance and lies above the DMRG value.

## Validation and interpretation

- All 2,583 production targets are complete, with 861 unique mixed-momentum rows per interaction.
- Direct V=0 tests reproduce the eight-lowest-level free-fermion energy to better than 1.1e-14 at four generic mixed momenta.
- The analytic thermodynamic V=0 value is -8/pi^2 = -0.810569469139; the 41-point trapezoidal mixed-momentum integral is -0.810361423380, differing by +2.080e-04. No V=0 production jobs were needed.
- Two independent Lanczos seeds at V=1 give identical E0 within displayed precision.
- The nested-grid differences are only O(1e-6) per site or smaller, so mixed-momentum integration error is negligible relative to the benchmark differences.
- 16-MMHK is a thermodynamic momentum-mixing construction, whereas the references are an 8x8 periodic finite lattice. The signed differences are therefore descriptive and are not variational error bounds.
- Agreement improves strongly from V=1 toward the charge-ordered regime. This is physically plausible because the strong-V state is governed increasingly by local checkerboard constraints, while the weaker-coupling regime retains longer-range itinerant correlations that are harder for finite momentum-mixing resolution.

Solver validation: `/Users/cosdis/Desktop/projects/HK_orbital_cluster/benchmark/results/spinless_tV_pbc_solver_validation.json`

## Reference provenance

The archived values are from the VarBench 8x8-periodic, N=32 spinless t-V tables. The CT-QMC rows link to Wang, Liu, and Troyer, Phys. Rev. B 93, 155117 (2016); the DMRG rows record maximum bond dimension 4096. The reported energy variance is retained as provenance and is not treated as a statistical error bar.
