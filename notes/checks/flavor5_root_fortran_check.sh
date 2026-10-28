#!/bin/bash
# Runs DART's flavor-5 mode update, as in DART 7bbd35a09 and with patches/dart_7bbd35a09_flavor5_root_choice.patch,
# for notes/dart_flavor5_wrong_root.md. Takes adaptive_inflate_mod.f90 from the DART repository's commit (not
# its working tree, which may carry the patch), applies the patch to a copy, cuts bayes_cov_inflate ..
# change_GA_IG out of both into two stand-alone modules (stubs for error_handler; in a temporary directory, as
# DART's source isn't kept here), compiles them with flavor5_root_fortran_driver.f90 in float32 (our
# r8 = r4) and float64, and runs both. Also says whether DART's working tree carries the patch.
# Run from anywhere: bash notes/checks/flavor5_root_fortran_check.sh
set -eo pipefail
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../.." && pwd)
dart=$repo/../software/DART
rel=assimilation_code/modules/assimilation/adaptive_inflate_mod.f90
patchfile=$repo/patches/dart_7bbd35a09_flavor5_root_choice.patch
source "$repo/scripts/env_wrf.sh" >/dev/null 2>&1
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/old/$(dirname $rel)" "$work/new/$(dirname $rel)"
git -C "$dart" show 7bbd35a09:$rel > "$work/old/$rel"
cp "$work/old/$rel" "$work/new/$rel"
(cd "$work/new" && patch -s -p1 < "$patchfile")
if cmp -s "$dart/$rel" "$work/new/$rel"; then echo "DART working tree: patched"
elif cmp -s "$dart/$rel" "$work/old/$rel"; then echo "DART working tree: not patched"
else echo "DART working tree: neither the commit nor the patched file"; fi
for kind in r4 r8; do
   if [ $kind = r4 ]; then r8='SELECTED_REAL_KIND(6,30)'; else r8='SELECTED_REAL_KIND(12)'; fi
   mkdir "$work/$kind"
   for v in old new; do
      f=$work/$kind/infl_${v}_mod.f90
      cat > "$f" <<EOT
module infl_${v}_mod
! adaptive_inflate_mod.f90, bayes_cov_inflate .. change_GA_IG ($v), copied at build time
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
      sed -n '/^subroutine bayes_cov_inflate/,/^end subroutine change_GA_IG/p' "$work/$v/$rel" >> "$f"
      echo "end module infl_${v}_mod" >> "$f"
   done
   (cd "$work/$kind" && ifort -O2 -fp-model precise infl_old_mod.f90 infl_new_mod.f90 \
      "$here/flavor5_root_fortran_driver.f90" -o drv)
   echo "=== $kind"
   "$work/$kind/drv"
done
