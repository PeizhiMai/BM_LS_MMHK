## Generated Outputs

Run:

```bash
python3 scripts/benchmark_compare.py
python3 scripts/extract_spectral_from_notebook.py
```

This produces:

- `half_filling_methods.csv`: AFQMC/MMHK from `benchmark.xlsx` + DMET values from PRX Tables II/III/VI
- `half_filling_deltas.csv`: MMHK deltas against AFQMC and DMET
- `half_filling_comparison.pdf`: half-filling comparison plot with AFQMC+DMET error bars
- `spectral_function_from_notebook.png`: spectral-function image extracted from notebook output
- `spectral_function_metadata.txt`: source metadata (`mu`, printed `nden`)
