#!/bin/bash
# Run DART's obs_diag on the obs_seq.final files of a range of analysis cycles of one run.
#
# Usage: [TEMPLATE=<file>] run_obs_diag.sh <output dir> <first> <last> <assim|all> <diag dir>
#
# <output dir>: a run's output directory (e.g. cases/20250520/da_theta_m0_n50/output_conv_refl_f2), read only:
#   <t>/filter/obs_seq.final for every analysis time t from <first> to <last> (YYYYMMDDHHMM, every 15 min), each
#   cycle's <t>/status must say "complete"; <first>/filter/input.nml supplies the other modules' namelists.
# Selection: assim = DART's default (prior statistics over DART QC 0-3, posterior over QC 0-1, i.e. outliers
#   left out; rank histogram without outliers); all = every observation type in the files listed in trusted_obs
#   (QC 7 added to the prior and the posterior statistics; rank histogram with outliers). The prior statistics of
#   "all" use the selection of notes/fulltest_d1_analysis.md Sec. 3.1 (QC 0 or 7).
# <diag dir>: created; obs_diag runs there and writes obs_diag_output.nc, obs_diag.log, LargeInnov.txt,
#   dart_log.*, plus obs_seq_list.txt, input.nml, time.log and run_obs_diag.txt (this call). It must not exist
#   yet or be empty, and must not be inside the output directory or a run_* or output_* directory.
# TEMPLATE: the &obs_diag_nml template, default <experiment dir>/config/input.nml.obs_diag (bins described
#   there), with @FIRST@, @LAST@, @TRUSTED@, @OUTLIERS@ filled in here.
# obs_diag is serial (MPI singleton); ~4 s and ~110 MB for one 213-MB obs_seq.final (05:30 of D2, login node).
# Check the result with scripts/da/check_obs_diag.py <diag dir>.
set -eu

die() { echo "run_obs_diag.sh: $*" >&2; exit 1; }
[ $# -eq 5 ] || die "usage: run_obs_diag.sh <output dir> <first> <last> <assim|all> <diag dir>"
out_dir=$(cd "$1" && pwd -P) || die "no output directory $1"
first=$2; last=$3; sel=$4; diag=$5
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd -P)
REPO=$(cd "${SCRIPT_DIR}/../.." && pwd -P)
OBS_DIAG=${REPO}/../software/DART/models/wrf/work/obs_diag
TEMPLATE=${TEMPLATE:-$(dirname "${out_dir}")/config/input.nml.obs_diag}
[ -x "${OBS_DIAG}" ] || die "no ${OBS_DIAG}"
[ -f "${TEMPLATE}" ] || die "no template ${TEMPLATE}"
case ${sel} in assim) outliers=.false. ;; all) outliers=.true. ;; *) die "selection must be assim or all" ;; esac
[[ ${first} =~ ^[0-9]{12}$ && ${last} =~ ^[0-9]{12}$ ]] || die "times are YYYYMMDDHHMM"

# The diagnostics directory: new or empty, outside the run's directories.
mkdir -p "${diag}"
diag=$(cd "${diag}" && pwd -P)
case ${diag}/ in "${out_dir}"/*) die "${diag} is inside the output directory" ;; esac
for part in ${diag//\// }; do
   case ${part} in run_*|output_*) die "${diag} is inside a run_* or output_* directory" ;; esac
done
[ -z "$(find "${diag}" -mindepth 1 -maxdepth 1 | head -1)" ] || die "${diag} is not empty"

# The cycles: every 15 min from first to last, each complete.
epoch() { date -u -d "${1:0:8} ${1:8:2}:${1:10:2}" +%s; }
t0=$(epoch "${first}"); t1=$(epoch "${last}")
[ "${t1}" -ge "${t0}" ] || die "last before first"
: > "${diag}/obs_seq_list.txt"
n=0
for (( s = t0; s <= t1; s += 900 )); do
   t=$(date -u -d "@${s}" +%Y%m%d%H%M)
   grep -qx complete "${out_dir}/${t}/status" 2> /dev/null || die "cycle ${t} not complete"
   f=${out_dir}/${t}/filter/obs_seq.final
   [ -s "${f}" ] || die "no ${f}"
   echo "${f}" >> "${diag}/obs_seq_list.txt"
   n=$(( n + 1 ))
done

# trusted_obs: 'null', or every type named in the files' headers (one per line).
if [ "${sel}" = all ]; then
   trusted=$(while read -r f; do
                head -n 300 "${f}" | awk 'NR == 3 {n = $1} NR > 3 && NR <= 3 + n {print $2}'
             done < "${diag}/obs_seq_list.txt" | sort -u | awk '{printf "%s'\''%s'\''", (NR > 1 ? ",\n                           " : ""), $1}')
   [ -n "${trusted}" ] || die "no observation types found in the headers"
else
   trusted="'null'"
fi
nmltime() { date -u -d "${1:0:8} ${1:8:2}:${1:10:2}" +"%Y, %-m, %-d, %-H, %-M, 0"; }
ft=$(nmltime "${first}"); lt=$(nmltime "${last}")

# input.nml: the run's filter namelist plus the filled-in template.
nml0=${out_dir}/${first}/filter/input.nml
grep -qi '^ *&obs_diag_nml' "${nml0}" && die "${nml0} already has an &obs_diag_nml"
cp "${nml0}" "${diag}/input.nml"
{
   echo
   while IFS= read -r line; do
      line=${line//@FIRST@/${ft}}; line=${line//@LAST@/${lt}}
      line=${line//@TRUSTED@/${trusted}}; line=${line//@OUTLIERS@/${outliers}}
      printf '%s\n' "${line}"
   done < "${TEMPLATE}"
} >> "${diag}/input.nml"
grep -q '@[A-Z]*@' "${diag}/input.nml" && die "unfilled field in ${diag}/input.nml"

cat > "${diag}/run_obs_diag.txt" << EOF
run_obs_diag.sh ${out_dir} ${first} ${last} ${sel} ${diag}
date: $(date -u '+%Y-%m-%d %H:%M:%S UTC'), host: $(hostname)
repo commit: $(git -C "${REPO}" rev-parse --short HEAD)$([ -z "$(git -C "${REPO}" status --porcelain -- "$(readlink -f "${TEMPLATE}")" "${SCRIPT_DIR}/$(basename "$0")" 2> /dev/null)" ] || echo " (template or script not committed)")
template: ${TEMPLATE}
filter namelist: ${nml0}
obs_diag: ${OBS_DIAG} ($(stat -c '%y' "${OBS_DIAG}" | cut -c1-19))
cycles: ${n} (${first} to ${last})
EOF

source "${REPO}/scripts/env_wrf.sh" > /dev/null 2>&1
export OMPI_MCA_coll_hcoll_enable=0   # hcoll can hang MPI programs at exit (notes/filter_exit_hang.md)
cd "${diag}"
echo "run_obs_diag.sh: ${sel}, ${n} cycles ${first} to ${last}, in ${diag}"
rc=0
/usr/bin/time -v -o time.log "${OBS_DIAG}" > obs_diag.log 2>&1 || rc=$?
grep -q "obs_diag Finished successfully" obs_diag.log || die "obs_diag failed (exit ${rc}); see ${diag}/obs_diag.log"
echo "run_obs_diag.sh: done, $(awk -F': ' '/Elapsed/ {print $2}' time.log) wall," \
     "$(awk -F': ' '/Maximum resident/ {printf "%.0f MB", $2 / 1024}' time.log) peak"
grep -E "# (observations used|identity|bad UV|bad Level|priorQC 7 postQC 2|bad DART QC prior|bad DART QC post) " obs_diag.log
