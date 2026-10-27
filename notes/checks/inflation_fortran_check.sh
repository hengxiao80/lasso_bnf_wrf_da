#!/bin/bash
# Runs DART's own inflation routines for notes/dart_adaptive_inflation.md (Sec. 5.3, 5.4, 7).
# Copies adaptive_inflate_mod.f90:763-1262 (bayes_cov_inflate .. change_GA_IG) from ../software/DART
# into a stand-alone module in a temporary directory (DART's source is not kept here), with stubs for
# error_handler, compiles it with inflation_fortran_driver.f90 in float32 (our r8 = r4) and float64,
# and runs both. Run from anywhere: bash notes/checks/inflation_fortran_check.sh
set -eo pipefail
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd)
src=$repo/../software/DART/assimilation_code/modules/assimilation/adaptive_inflate_mod.f90
sed -n 763p "$src" | grep -q '^subroutine bayes_cov_inflate' || { echo "line 763 is no longer bayes_cov_inflate"; exit 1; }
sed -n 1262p "$src" | grep -q '^end subroutine change_GA_IG' || { echo "line 1262 is no longer the end of change_GA_IG"; exit 1; }
source "$repo/scripts/env_wrf.sh" >/dev/null 2>&1
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
for kind in r4 r8; do
   if [ $kind = r4 ]; then r8='SELECTED_REAL_KIND(6,30)'; else r8='SELECTED_REAL_KIND(12)'; fi
   mkdir "$work/$kind"
   f=$work/$kind/infl_test_mod.f90
   cat > "$f" <<EOT
module infl_test_mod
! adaptive_inflate_mod.f90 lines 763-1262, copied verbatim at build time
implicit none
integer, parameter :: r8 = $r8
real(r8), parameter :: PI = 3.14159265358979323846_r8
integer, parameter :: GHA2017 = 1, AND2009 = 2, E_ERR = 2
character(len=512) :: string1
character(len=*), parameter :: source = 'test'
contains
subroutine error_handler(level, routine, text, src)
integer, intent(in) :: level
character(len=*), intent(in) :: routine, text, src
print *, 'ERROR ', trim(routine), ' ', trim(text); stop 1
end subroutine error_handler
EOT
   sed -n 763,1262p "$src" >> "$f"
   echo "end module infl_test_mod" >> "$f"
   (cd "$work/$kind" && ifort -O2 -fp-model precise infl_test_mod.f90 "$here/inflation_fortran_driver.f90" -o drv)
   echo "=== $kind"
   "$work/$kind/drv"
done
