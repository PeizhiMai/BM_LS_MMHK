# Two-copy repair policy

For each terminal ordinary failure or invalid completed pair, create exactly two concurrent isolated GAXRR copies on `ccsd`, per the user's 2026-08-27 account-routing directive. Use distinct globally unused QBASIS_LANCZOS_SEED values. Never launch a third copy while a round is active. The first strictly valid installer wins and cancels only its active sibling. If both fail, the next monitor pass starts one fresh two-copy round on `ccsd`.
