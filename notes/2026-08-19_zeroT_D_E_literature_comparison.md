# Zero-temperature double-occupancy and energy comparisons

## Scope and conventions

The 16-MMHK calculations use the spinful square-lattice Hamiltonian
$H=-t\sum_{\langle ij\rangle\sigma}(c^\dagger_{i\sigma}c_{j\sigma}+\mathrm{H.c.})+U\sum_i n_{i\uparrow}n_{i\downarrow}+V\sum_{\langle ij\rangle}n_i n_j$
at half filling with $t=1$, $t'=0$, $N_\uparrow=N_\downarrow=8$, and $Q=(0,0)$.
Only $E_0$ and the site-averaged double occupancy are measured.

Each interaction set contains the 861 symmetry-wedge points $0\leq k_x\leq k_y\leq40$.
The full mixed-momentum integral uses $k_x\leftrightarrow k_y$ multiplicity and trapezoidal endpoint weights; the unnormalized total weight is 1600.
The $U=V=0$ row is not sampled numerically: its energy is evaluated from the noninteracting band on the same quadrature and $D=(N_\uparrow/N)(N_\downarrow/N)=1/4$ analytically.

## Literature inputs

- Yao et al., PRB 106, 195121 (2022): $D$ was digitized from Fig. 2(d), using the $L=16$ projector-DQMC markers at $V/U=1/4$. A conservative marker-resolution uncertainty of 0.0015 is recorded.
- Zhou et al., PRB 109, 245107 (2024): Table I explicitly reports energy per lattice site for 50 spinless particles on a $10\times10$ lattice. The one-Lanczos-step ($p=1$) energies are primary and fPEPS values are a cross-check.
- Zhou's missing $V=0$ baseline is the exact sum of the 50 lowest one-body levels on the same $10\times10$ open lattice.

## 16-MMHK averages

| U_over_t | V_over_t | n_rows | quadrature_weight | E0_per_site_mean | D_mean | E0_per_site_nested_21_minus_full | D_nested_21_minus_full |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 0 | 0 | 1600 | -1.6207228 | 0.25 | 0.0012458236 | 0 |
| 0 | 0.45 | 861 | 1600 | -0.91568012 | 0.33953981 | 2.0441323e-09 | -9.9983175e-08 |
| 0 | 1 | 861 | 1600 | -0.51982062 | 0.43908309 | 0 | -2.8199665e-14 |
| 0 | 2 | 861 | 1600 | -0.27833956 | 0.48122952 | 5.5511151e-17 | 4.2577053e-14 |
| 2 | 0.5 | 861 | 1600 | -0.26941809 | 0.20996067 | 8.61843e-05 | -0.00082669478 |
| 4 | 1 | 861 | 1600 | 0.99945252 | 0.16738406 | -4.5018114e-06 | 9.489381e-05 |
| 6 | 1.5 | 861 | 1600 | 2.2000482 | 0.11849803 | -2.0388939e-08 | 2.718807e-07 |

## Direct double-occupancy comparison

| U_over_t | V_over_t | mmhk_value | literature_value | literature_uncertainty | absolute_difference | percentage_difference |
| --- | --- | --- | --- | --- | --- | --- |
| 2 | 0.5 | 0.20996067 | 0.2053 | 0.0015 | 0.00466067 | 2.2701754 |
| 4 | 1 | 0.16738406 | 0.1543 | 0.0015 | 0.013084056 | 8.4796218 |
| 6 | 1.5 | 0.11849803 | 0.1095 | 0.0015 | 0.0089980269 | 8.2173762 |

## Spinful/spinless energy comparison

The energy panel uses energy per particle, $E_0/N_e$. For spinful 16-MMHK at half filling, $N_e/N_s=1$, so its energy per particle equals its energy per site. Zhou's spinless calculation has $N_e/N_s=1/2$, so its tabulated per-site energy is divided by $1/2$ to obtain $E_0/N_e$.
This factor is only a normalization conversion; it is not an assumption that the spinful Hamiltonian consists of two independent spinless copies.

| V_over_t | mmhk_energy_per_site | spinless_energy_per_site | mmhk_energy_per_particle | spinless_energy_per_particle | energy_per_particle_difference | p1_minus_fPEPS_per_site | mmhk_V0_subtracted_per_particle | spinless_V0_subtracted_per_particle |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | -1.6207228 | -0.767483 | -1.6207228 | -1.534966 | -0.085756844 |  | 0 | 0 |
| 0.45 | -0.91568012 | -0.6134 | -0.91568012 | -1.2268 | 0.31111988 | -0.0005 | 0.70504272 | 0.308166 |
| 1 | -0.51982062 | -0.462 | -0.51982062 | -0.924 | 0.40417938 | 0 | 1.1009022 | 0.610966 |
| 2 | -0.27833956 | -0.2999 | -0.27833956 | -0.5998 | 0.32146044 | 0 | 1.3423833 | 0.935166 |

## Interpretation limit

The Zhou series is not an accuracy benchmark for 16-MMHK: it is a spinless $10\times10$ open-boundary model at density $1/2$, whereas 16-MMHK is spinful and has total density one.
The present spinful $Vn_i n_j$ interaction expands into same-spin and cross-spin terms, so its two spin sectors are not independent when $V\neq0$. The energy comparison is therefore descriptive rather than a direct accuracy error for 16-MMHK.

## Reproducibility

- Raw snapshot: `/Users/cosdis/Desktop/projects/HK_orbital_cluster/benchmark/data/zeroT_D_E_mmhk/raw_20260819`
- Literature table: `/Users/cosdis/Desktop/projects/HK_orbital_cluster/benchmark/data/literature/zeroT_extended_hubbard_benchmarks/zeroT_D_E_literature.csv`
- Analysis: `scripts/analyze_zeroT_D_E_benchmarks.py`
