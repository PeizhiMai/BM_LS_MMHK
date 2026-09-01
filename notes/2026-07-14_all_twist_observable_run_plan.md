# Plan: all-twist static-observable calculation

## Scope

- Use `Hubbard_sym_testobs_UV.cc` on the (4\times4) momentum-mixing resolution.
- Work at half filling with (N_\uparrow=N_\downarrow=8), fixed total momentum
  (Q=(0,0)), and (t'=0).
- For every interaction pair, run every integer twist index satisfying
  \[
  0\le k_x\le k_y\le 40.
  \]
  This is the symmetry-reduced triangular grid of (41\times42/2=861)
  twists per interaction pair.
- The prepared fixed-(U) scan is
  \[
  (U,V)=(40,0),(40,4),(40,8),(40,9),(40,10),(40,11),(40,12),(40,16),(40,20),
  \]
  corresponding to (V/U=0,0.1,0.2,0.225,0.25,0.275,0.3,0.4,0.5). It
  contains (9\times861=7749) independent jobs.

## Measured quantities

- (n(\mathbf q)) and momentum-space double occupancy
  \(\langle n_{\mathbf q\uparrow}n_{\mathbf q\downarrow}\rangle\);
- real-space double occupancy;
- (S^{zz}(\pi,\pi)) and (S_c(\pi,\pi));
- nearest-neighbor density correlation and its connected form;
- nearest- and next-nearest-neighbor kinetic energy, plus total kinetic energy;
- nearest-neighbor spin correlation
  (C_1=\langle\mathbf S_i\cdot\mathbf S_j\rangle_{\rm NN}).

## Prepared workflow

1. Keep the complete workflow in the standalone CADES directory
   `/home/9pm/ED_qbasis/qbasis/bin/ML/HF/fullobs`, outside `Gcalpath`.  Use job
   name `OBSUV` and dedicated template, submitted, and log directories.
2. Generate deterministic, duplicate-safe templates in interleaved order:
   all nine interaction pairs at one twist before advancing to the next twist.
   Template names use a twist-only ordinal, so adding interaction pairs cannot
   rename or duplicate previously prepared jobs.
3. Require the final `status COMPLETE` record before treating an output file as
   finished.  Partial files from interruption or walltime are not skipped.
4. Before launch, compile the synchronized source with the standalone
   `fullobs/buildUV.sh`; the `Gcalpath` build no longer includes this source.
5. On explicit approval, launch a small pilot first, inspect memory, runtime,
   energy decomposition, and output completeness, and only then open the queue.
6. The prepared launcher counts all user jobs on each account and uses separate
   total-user caps of 150 on `ccsd` and 150 on `cnms`. Both values are
   configurable.
7. Monitor failed tasks by retained run script and Slurm log; do not silently
   rerun failures.

## Safety and acceptance criteria

- Submission is currently disarmed and requires
  `OBSUV_CONFIRM_SUBMIT=YES` in addition to an explicit launch command.
- No job is submitted as part of script preparation or validation.
- Exactly 861 unique ((k_x,k_y)) commands must be generated per interaction
  pair, with no violation of (k_y\ge k_x).
- Every generated shell script must pass `bash -n`.
- A completed interaction set requires 861 nonempty output files ending in
  `status COMPLETE`.
