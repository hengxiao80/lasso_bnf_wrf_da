#!/bin/bash
# Refit a copy of a member's pristine boundary file to the member's current state (pilot step 8;
# later called by advance_member.sh).
#
# Usage: refit_member_bdy.sh <state_file> <pristine_wrfbdy> <work_dir>
#
# <state_file> is the member's DART-facing file (wrfrst_dart.py extract, after filter) or a
# wrfinput; update_wrf_bc reads its Times, U V W PH T QVAPOR MU MUB MAPFAC_* (T must equal THM).
# Writes <work_dir>/wrfbdy_d01: a fresh copy of <pristine_wrfbdy> with the record containing the
# state time starting at that time from the state, and tendencies to the record's original end
# (patched update_wrf_bc, patches/README.md). The pristine file is never modified.
# Needs the scripts/env_wrf.sh modules (netCDF libraries).
set -eu

state=$1 pristine=$2 work=$3
UPDATE_WRF_BC=${UPDATE_WRF_BC:-/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/software/DART/models/wrf/work/update_wrf_bc}

mkdir -p "${work}"
cd "${work}"
rm -f wrfbdy_d01 wrfinput_d01 wrfinput_mean dart_log.out dart_log.nml
cp "${pristine}" wrfbdy_d01
ln -sf "$(readlink -f "${state}")" wrfinput_d01
# DART's initialize_utilities reads &utilities_nml; update_wrf_bc has no namelist of its own.
cat > input.nml << EOF
&utilities_nml
   termlevel = 1,
   logfilename = 'dart_log.out',
   nmlfilename = 'dart_log.nml',
   write_nml = 'file',
/
EOF
"${UPDATE_WRF_BC}" > update_wrf_bc.log 2>&1 || true
if ! grep -q 'update_wrf_bc terminated normally' update_wrf_bc.log; then
   cat update_wrf_bc.log >&2
   echo "refit_member_bdy.sh: update_wrf_bc failed in ${work}" >&2; exit 1
fi
rm -f wrfinput_d01
