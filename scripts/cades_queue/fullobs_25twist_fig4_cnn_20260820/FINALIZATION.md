# Safe local finalization

Finalizer:

`/Users/cosdis/Desktop/projects/HK_orbital_cluster/benchmark/scripts/cades_queue/finalize_fullobs_25twist_fig4_cnn.py`

Read-only eligibility check:

```bash
~/.venvs/myenv/bin/python \
  /Users/cosdis/Desktop/projects/HK_orbital_cluster/benchmark/scripts/cades_queue/finalize_fullobs_25twist_fig4_cnn.py \
  --check-only
```

Finalize after the check reports `ELIGIBLE`:

```bash
~/.venvs/myenv/bin/python \
  /Users/cosdis/Desktop/projects/HK_orbital_cluster/benchmark/scripts/cades_queue/finalize_fullobs_25twist_fig4_cnn.py
```

The fixed destination is:

`/Users/cosdis/Desktop/projects/HK_orbital_cluster/benchmark/data/fullobs/fullobs_25twist_fig4_cnn_20260820`

There is no force or overwrite option. The finalizer requires exactly 300 valid
COMPLETE outputs, zero matching Slurm activity, zero anomalies/warnings,
successful scheduler queries, and matching pinned solver/source/library hashes
before it creates a staging directory. It inventories and hashes all remote
files before transfer and requires both the remote inventory and the downloaded
untouched `metadata/manifest.tsv` to match the campaign-specific manifest hash
`baa6f80fd1173165fa36f201c52b6c6f9ec4b1d198ef9169687c5977ffd381e5`.
It then verifies the download, repeats the remote audit and inventory, applies
the same deep observable validation locally, generates the two analysis CSVs,
writes a snapshot-wide checksum ledger, makes the tree read-only, and installs
it with one atomic rename.

The incomplete-batch refusal test on 2026-08-21 exited with status 2 while the
campaign was still active and created neither the destination nor staging path.
