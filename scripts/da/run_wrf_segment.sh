#!/bin/bash
# Run one WRF segment in its own directory (pilot steps 7-8; later called by advance_member.sh).
#
# Usage: run_wrf_segment.sh <experiment.sh> <run_dir> <start YYYY-MM-DD_HH:MM:SS> <seconds>
#                           <wrfinput> <wrfbdy> <nproc_x> <nproc_y>
#
# Environment (optional): RESTART=.true. starts from a WRF restart file: <wrfinput> is then a
# wrfrst file, linked as wrfrst_d01_<start>; default .false. (cold start from wrfinput_d01).
# RESTART_INTERVAL (minutes) for restart output; default 7200 (none within a segment).
# SRUN_OPTS: extra srun options, e.g. "-N 8 -c 8 --exact" to run beside other members' steps
# in one allocation (cycling, pilot step 12); default none (the step uses the whole allocation).
#
# Links the WRF run-time tables and wrf.exe into run_dir, links <wrfinput> as wrfinput_d01 and
# <wrfbdy> as wrfbdy_d01 (WRF only reads them), writes namelist.input from
# ${CONFIG_DIR}/namelist.input.wrf and copies ${CONFIG_DIR}/iofields_cycle.txt, then runs
# nproc_x * nproc_y MPI ranks with srun (OpenMP threads from the calling job's environment,
# including the wrf.exe UCX settings). Fails unless rsl.out.0000 ends in SUCCESS COMPLETE WRF.
#
# Exit guard (2026-10-21): in run 3, wrf.exe printed SUCCESS, had written everything, and then didn't exit
# (27 min, cancelled by hand); most likely hcoll's teardown in MPI_FINALIZE, as for filter
# (notes/filter_exit_hang.md). Once SUCCESS is in rsl.out.0000, the step gets WRF_EXIT_GRACE s (default 30;
# a normal exit takes ~1 s) to exit; if it hasn't, and no rsl, wrfout or wrfrst file here has changed for
# 30 s, a snapshot of its processes is taken on its nodes (hang_snapshot.py into hang_snapshot/, summary in
# hang_snapshot_summary.txt; WRF_HANG_SNAPSHOT=0 skips it), then the step is cancelled (srun killed 60 s
# later if still there) and the segment counts as complete. Each firing is logged ("wrf exit guard: ...")
# and leaves wrf_exit_guard.txt. The step is named wrf.exe_<member>_<pid>, so the guard finds its own step
# among the members' concurrent ones.
set -eu

exp_sh=$1 run_dir=$2 start=$3 seconds=$4 wrfinput=$5 wrfbdy=$6 npx=$7 npy=$8
source "${exp_sh}"
source "$(dirname "$(readlink -f "$0")")/cycle_lib.sh"     # log, recently_changed

end=$(date -u -d "${start:0:10} ${start:11:8} UTC + ${seconds} seconds" +%Y-%m-%d_%H:%M:%S)
mkdir -p "${run_dir}"
cd "${run_dir}"
rm -f rsl.out.* rsl.error.* wrfinput_d01 wrfbdy_d01 "wrfrst_d01_${start//:/_}" wrf_exit_guard.txt \
   hang_snapshot.log hang_snapshot_summary.txt
rm -rf hang_snapshot
restart=${RESTART:-.false.}
rst_int=${RESTART_INTERVAL:-7200}

# Run-time tables and executables (not the namelist): `find`, since ls is aliased with -F.
find "${WRF_RUN_DIR}" -maxdepth 1 \( -type f -o -type l \) ! -name 'namelist.input*' \
   -exec ln -sf {} . \;
if [ "${restart}" = ".true." ]; then
   ln -sf "$(readlink -f "${wrfinput}")" "wrfrst_d01_${start//:/_}"
else
   ln -sf "$(readlink -f "${wrfinput}")" wrfinput_d01
fi
ln -sf "$(readlink -f "${wrfbdy}")" wrfbdy_d01
cp "${CONFIG_DIR}/iofields_cycle.txt" .

sed -e "s/@SY@/${start:0:4}/; s/@SM@/${start:5:2}/; s/@SD@/${start:8:2}/" \
    -e "s/@SH@/${start:11:2}/; s/@SN@/${start:14:2}/" \
    -e "s/@EY@/${end:0:4}/; s/@EM@/${end:5:2}/; s/@ED@/${end:8:2}/" \
    -e "s/@EH@/${end:11:2}/; s/@EN@/${end:14:2}/" \
    -e "s/@NPX@/${npx}/; s/@NPY@/${npy}/" \
    -e "s/@RESTART@/${restart}/; s/@RSTINT@/${rst_int}/" \
    "${CONFIG_DIR}/namelist.input.wrf" > namelist.input
if grep -q '@[A-Z]*@' namelist.input; then
   echo "run_wrf_segment.sh: unfilled placeholder in namelist.input" >&2; exit 1
fi

echo "$(date) wrf.exe ${start} -> ${end} in ${run_dir} ($((npx * npy)) ranks, restart=${restart})"
t0=$(date +%s)
tag=$(basename "${run_dir}")
[ "${tag}" != wrf ] || tag=$(basename "$(dirname "${run_dir}")")
step_name=wrf.exe_${tag}_$$
srun ${SRUN_OPTS:-} -J "${step_name}" -n $((npx * npy)) --cpu_bind=cores ./wrf.exe &
pid=$!
grace=${WRF_EXIT_GRACE:-30} t_ok= t_cancel=
while kill -0 "${pid}" 2> /dev/null; do
   if [ -z "${t_ok}" ]; then
      ! tail -n 5 rsl.out.0000 2> /dev/null | grep -q 'SUCCESS COMPLETE WRF' || t_ok=${SECONDS}
   elif [ -z "${t_cancel}" ] && [ $((SECONDS - t_ok)) -ge "${grace}" ] \
        && [ -z "$(recently_changed 30 rsl.* wrfout_d01_* wrfrst_d01_*)" ]; then
      step= nodes=
      read -r step nodes <<< "$(squeue -h -s -j "${SLURM_JOB_ID}" -o '%i %j %N' \
         | awk -v n="${step_name}" '$2 == n {print $1, $3; exit}')" || true
      log "wrf exit guard: wrf.exe still running $((SECONDS - t_ok)) s after SUCCESS in ${run_dir};" \
         "step ${step:-(not found)} on ${nodes:-?}"
      if [ "${WRF_HANG_SNAPSHOT:-1}" != 0 ] && [ -n "${nodes}" ]; then
         timeout 300 srun --overlap -w "${nodes}" -N "$(scontrol show hostnames "${nodes}" | wc -l)" \
            --ntasks-per-node=1 -c 1 "${PROJECT_DIR}/.venv/bin/python" \
            "${PROJECT_DIR}/scripts/da/hang_snapshot.py" hang_snapshot wrf.exe --secs 2 --freq 29 \
            > hang_snapshot.log 2>&1 || true
         "${PROJECT_DIR}/.venv/bin/python" "${PROJECT_DIR}/scripts/da/hang_summary.py" hang_snapshot \
            > hang_snapshot_summary.txt 2>&1 || true
      fi
      echo "$(date -u +%Y-%m-%dT%H:%M:%S) step ${step:-?} cancelled $((SECONDS - t_ok)) s after SUCCESS" \
         > wrf_exit_guard.txt
      if [ -n "${step}" ]; then
         scancel "${step}"
      else
         kill -INT "${pid}" 2> /dev/null || true; sleep 0.5; kill -INT "${pid}" 2> /dev/null || true
      fi
      t_cancel=${SECONDS}
   elif [ -n "${t_cancel}" ] && [ $((SECONDS - t_cancel)) -ge 60 ]; then
      kill -KILL "${pid}" 2> /dev/null || true
   fi
   sleep 2
done
wait "${pid}" || true
echo "$(date) wrf.exe finished, $(( $(date +%s) - t0 )) s$([ ! -f wrf_exit_guard.txt ] || echo ' (exit guard fired)')"
if ! tail -n 5 rsl.out.0000 | grep -q 'SUCCESS COMPLETE WRF'; then
   echo "run_wrf_segment.sh: wrf.exe did not complete in ${run_dir}" >&2; exit 1
fi
