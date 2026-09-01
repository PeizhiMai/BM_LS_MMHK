# U-only and V-only axis-refinement Green-function scan

Eleven t-prime-zero axis-refinement sets for live Fig. 3d and Fig. 4d.

- 120 unique Gamma-X-M-Gamma points per set
- 32 tasks, 100 GB, 8 h
- original ordinary allocation: 990 ccsd, 330 cnms (90/30 per set); all ordinary jobs submitted at once
- user-directed 2026-08-27 rebalance: every then-pending cnms job moved in place to ccsd; running cnms jobs were not touched
- all future two-copy repairs are routed to ccsd with fresh seeds
- valid pairs require matching metadata and 999 `a` plus 999 `b` coefficients in both Gh/Gp files
