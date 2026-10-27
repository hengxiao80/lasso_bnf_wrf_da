# MPI programs hang in `MPI_Finalize` in hcoll's teardown (Cirrus)

**Summary.** Our MPI jobs sometimes never exit after their last output. One rank stays stuck in hcoll's teardown inside `MPI_Finalize`, and every other rank waits for it. Switching hcoll off (`OMPI_MCA_coll_hcoll_enable=0`) stops the hang. Results are unchanged and our DA program runs just as fast, but WRF runs ~30 % slower. We would like to know whether this is a known hcoll/UCX issue with a fix.

## Environment

- Open MPI 4.0.4 (spack, module `openmpi/4.0.4`), UCX 1.14.0, hcoll 4.8.3220, MLNX OFED 5.8. Slurm 25.11.8 with `MpiDefault=pmi2`. Intel Fortran 19.1.3.
- `UCX_TLS=self,sm,ud` and `UCX_UD_MLX5_RX_QUEUE_LEN=16384`. hcoll is at its defaults (`coll_hcoll_enable=1`, priority 90, np 2).
- Programs: DART `filter` (40 nodes × 32 ranks = 1,280 ranks) and WRF (8 nodes × 16 ranks × 8 OpenMP threads).

## Symptom

- The program prints its final message, and all its output files are complete. It then never exits.
- All ranks stay alive at ~100 % CPU with no voluntary context switches and nothing in D state, until we cancel the step (4–27 min).
- `filter` at 1,280 ranks hung in 14 of 23 runs. WRF at 128 ranks hung once in ~290 runs (no snapshot was taken).

## What we found

`ptrace` is blocked, so we took stacks of every rank of hung steps with `perf record --call-graph dwarf`. We did this three times, and all three hangs showed the same pattern:

```
1 rank (the first rank on its node, i.e. the hcoll node leader):
  PMPI_FINALIZE > ompi_mpi_finalize > ompi_comm_finalize
  > ompi_attr_delete_all > hcoll_comm_attr_del_fn
  > hcoll_context_free > hmca_bcol_ucx_p2p_disconnect
  > ucp_worker_progress            (spins, never returns)
all other 1,279 ranks:
  PMPI_FINALIZE > ompi_mpi_finalize > mca_pml_ucx_del_procs
  > opal_common_ucx_mca_pmix_fence > ucp_worker_progress
```

- **hcoll leaves one rank stuck.** On one node leader, hcoll's own UCX endpoints (bcol `ucx_p2p`) never finish closing. Every other rank then waits for that rank in the final fence.
- **It is not one bad node.** The stuck node leader was on a different node each time (cirrus31, cirrus34, cirrus46).
- **UCX's timeouts don't end it.** The default UD timeouts (30 s and 300 s linger) are much shorter than the hangs.
- **Lazy connections may play a part.** `HCOLL_BCOL_UCX_P2P_PRECONNECT_NP` defaults to 1024, so above 1,024 ranks hcoll opens its connections lazily. With 2048 we saw 0 hangs, but in only 3 runs, which is too few to tell.

## Workaround in use

| setting (`filter`, 40 × 32) | runs | hung |
|---|---|---|
| hcoll on (default) | 23 | 14 |
| `OMPI_MCA_coll_hcoll_enable=0` | 35 | 0 |
| `HCOLL_BCOL_UCX_P2P_PRECONNECT_NP=2048` | 3 | 0 |

- **`filter` now runs with hcoll off.** The 35 runs with hcoll off include runs on cirrus58–97. Its results are bit-identical, and its wall time is the same or 1–2 s shorter.
- **WRF keeps hcoll on.** With hcoll off its outputs are byte-identical, but the time stepping is ~30 % slower (76 s → 99 s for a 15-min segment on 8 nodes). Instead, our script cancels a WRF step that is still running 30 s after it reports success.

## Questions

1. Is this hang in hcoll 4.8 (`hmca_bcol_ucx_p2p_disconnect` at finalize, with UCX 1.14 over UD) a known issue, and does a newer hcoll, UCX or HPC-X fix it?
2. Did anything change on the fabric or the nodes around mid-October? All our 40-node runs date from 2026-10-20 on, so we can't tell whether the cause is the 40-node scale or the date. Separately, WRF's netCDF writes have become up to ~25 % slower than in early October, and a colleague sees the same.
3. Do you recommend an hcoll setting, or turning hcoll off, for jobs of this size?

**Details available:** the full perf snapshots, `hcoll_info -a` output and logs of jobs 1054828 (hcoll on, 2 of 4 hung), 1054833 (hcoll off, 0 of 8), 1054839 (on / off / preconnect: 1 / 0 / 0 of 3 each) and 1054907 (WRF, hcoll on vs off).
