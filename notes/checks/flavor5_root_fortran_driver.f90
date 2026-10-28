! Driver for flavor5_root_fortran_check.sh (notes/dart_flavor5_wrong_root.md).
! Calls DART's enh_linear_bayes and bayes_cov_inflate as in 7bbd35a09 (infl_old_mod) and with the
! patched root choice (infl_new_mod), compiled in float32 (our r8 = r4) or float64:
!  1. a sweep (flavor5_root_checks.py section 3's cases, plus extreme ones): where the two differ, and
!     whether the patched root lies on the side of lambda_mean that q = like_bar/like_prime points to
!  2. the inflation note's cases: one bayes_cov_inflate update (before the bounds), mean and sd
program driver
use infl_old_mod, only : r8, PI, GHA2017, change_GA_IG, enh_old => enh_linear_bayes, bci_old => bayes_cov_inflate
use infl_new_mod, only : enh_new => enh_linear_bayes, bci_new => bayes_cov_inflate
implicit none
integer, parameter :: ens_size = 5
real(r8) :: gams(7) = (/ 0.001_r8, 0.05_r8, 0.2_r8, 0.5_r8, 0.8_r8, 0.99_r8, 1.0_r8 /)
real(r8) :: lms(5) = (/ 1.0_r8, 1.5_r8, 2.0_r8, 3.0_r8, 5.0_r8 /)
real(r8) :: lsds(5) = (/ 0.3_r8, 0.6_r8, 1.0_r8, 1.5_r8, 3.0_r8 /)
real(r8) :: rhos(8) = (/ 0.001_r8, 0.02_r8, 0.05_r8, 0.1_r8, 0.2_r8, 0.5_r8, 1.0_r8, 2.0_r8 /)
real(r8) :: sp2s(3) = (/ 0.25_r8, 1.0_r8, 100.0_r8 /)
real(r8) :: ratios(24) = (/ 0.0_r8, 0.05_r8, 0.3_r8, 0.7_r8, 0.95_r8, 0.999_r8, 0.99999_r8, 1.00001_r8, &
   1.001_r8, 1.05_r8, 1.5_r8, 2.0_r8, 3.0_r8, 5.0_r8, 7.0_r8, 9.0_r8, 12.0_r8, 16.0_r8, 25.0_r8, &
   50.0_r8, 100.0_r8, 1.0e3_r8, 1.0e4_r8, 1.0e5_r8 /)
real(r8) :: lm, lsd, g, sp2, so2, d2, beta, old, new, q, fac1, fac2, th2, th, dth, newsd, oldsd
real(r8) :: like_bar, like_prime
integer :: i1, i2, i3, i4, i5, i6, k
integer :: ncase, n_guard, n_reg, n_diff, n_diff_out, n_same_in, n_dir_bad, n_new_keep, n_old_keep, n_nan
integer :: n_shown, n_dir_ulp
real(r8) :: dev_ulp
logical :: in_reg
real(r8) :: note_cases(3, 8)

print '(a,i3)', 'precision digits: ', precision(1.0_r8)
! 1. sweep
ncase = 0; n_guard = 0; n_reg = 0; n_diff = 0; n_diff_out = 0; n_same_in = 0; n_dir_bad = 0
n_new_keep = 0; n_old_keep = 0; n_nan = 0; n_shown = 0; n_dir_ulp = 0; dev_ulp = 0.0_r8
do i1 = 1, size(gams); do i2 = 1, size(lms); do i3 = 1, size(lsds)
do i4 = 1, size(rhos); do i5 = 1, size(sp2s); do i6 = 1, size(ratios)
   g = gams(i1); lm = lms(i2); lsd = lsds(i3); sp2 = sp2s(i5); so2 = rhos(i4) * sp2
   ! flavor-5 theta_bar^2 and q, as in enh_linear_bayes
   fac1 = (1.0_r8 + g * (sqrt(lm) - 1.0_r8))**2
   fac2 = -1.0_r8 / ens_size
   if (fac1 < abs(fac2)) fac2 = 0.0_r8
   th2 = (fac1 + fac2) * sp2 + so2
   th = sqrt(th2)
   d2 = ratios(i6) * th2
   dth = 0.5_r8 * sp2 * g * (1.0_r8 - g + g * sqrt(lm)) / (th * sqrt(lm))
   like_bar = exp(-0.5_r8 * d2 / th2) / (sqrt(2.0_r8 * PI) * th)
   like_prime = like_bar * dth * (d2 / th2 - 1.0_r8) / th
   call change_GA_IG(lm, lsd**2, beta)
   call enh_old(d2, sp2, so2, lm, g, ens_size, beta, old)
   call enh_new(d2, sp2, so2, lm, g, ens_size, beta, new)
   ncase = ncase + 1
   ! enh_linear_bayes's early exits (likelihood or its slope 0 or below TINY) keep lambda_mean
   if (like_bar <= 0.0_r8 .or. like_prime == 0.0_r8 .or. abs(like_bar) <= tiny(0.0_r8) .or. &
       abs(like_prime) <= tiny(0.0_r8)) then
      n_guard = n_guard + 1
      q = huge(q)
      in_reg = .false.
   else
      q = th / (dth * (d2 / th2 - 1.0_r8))
      in_reg = q > 0.0_r8 .and. q < 2.0_r8 * lm**2 / beta
   endif
   if (in_reg) n_reg = n_reg + 1
   if (old /= new) n_diff = n_diff + 1
   if (old /= new .and. .not. in_reg) n_diff_out = n_diff_out + 1
   if (old == new .and. in_reg) n_same_in = n_same_in + 1
   ! a step against q: more than a few ulps (a wrong pick), or within them (the near root's round-off)
   if ((new - lm) * sign(1.0_r8, q) < -4.0_r8 * spacing(lm)) then
      n_dir_bad = n_dir_bad + 1
   else if ((new - lm) * sign(1.0_r8, q) < 0.0_r8) then
      n_dir_ulp = n_dir_ulp + 1
      dev_ulp = max(dev_ulp, abs(new - lm) / spacing(lm))
   endif
   if (new == lm) n_new_keep = n_new_keep + 1
   if (old == lm) n_old_keep = n_old_keep + 1
   if (new /= new) n_nan = n_nan + 1
   if ((old /= new .neqv. in_reg) .or. (new - lm) * sign(1.0_r8, q) < -4.0_r8 * spacing(lm)) then
      if (n_shown < 10) print '(a,7es12.4)', '  case g lm sd rho r q 2c*lm: ', g, lm, lsd, rhos(i4), ratios(i6), q, &
         2.0_r8 * lm**2 / beta
      if (n_shown < 10) print '(a,2f12.6)', '      DART, patched: ', old, new
      n_shown = n_shown + 1
   endif
enddo; enddo; enddo; enddo; enddo; enddo
print '(a,i6,a,i6)', ' sweep: cases ', ncase, ', of which stopped by the early exits ', n_guard
print '(a,i6)', ' in the wrong-root region 0 < q < 2 lam_b^2/beta: ', n_reg
print '(a,i6,a,i6,a,i6)', ' DART and patched differ in ', n_diff, '; outside the region ', n_diff_out, &
   '; same inside it ', n_same_in
print '(a,i6,a,i6)', ' patched step against the sign of q: ', n_dir_bad, '; patched NaN: ', n_nan
print '(a,i6,a,f4.1,a)', ' patched root within ulps on the wrong side of lambda_mean (round-off): ', n_dir_ulp, &
   ' (at most ', dev_ulp, ' ulp)'
print '(a,i6,a,i6)', ' lambda_mean kept (early exits, or step rounded to 0): DART ', n_old_keep, &
   ', patched ', n_new_keep

! 2. the inflation note's cases: sp2 = 1, so2 = 0.2, gamma = 1, N = 5, sd floor 0.3
!    columns: lambda_mean, lambda_sd, d^2/(sigma_y^2 + sigma_o^2) with sigma_y^2 = lambda_mean * sp2
note_cases = reshape((/ 1.0_r8, 0.6_r8, 4.0_r8,   1.0_r8, 0.6_r8, 6.0_r8,   1.0_r8, 0.6_r8, 8.0_r8, &
                        1.0_r8, 0.6_r8, 9.0_r8,   1.0_r8, 0.6_r8, 12.0_r8,  2.0_r8, 1.2_r8, 6.0_r8, &
                        2.0_r8, 1.2_r8, 8.0_r8,   2.0_r8, 1.2_r8, 9.0_r8 /), (/ 3, 8 /))
do k = 1, 8
   lm = note_cases(1, k); lsd = note_cases(2, k)
   d2 = note_cases(3, k) * (lm + 0.2_r8)
   call bci_old(ens_size, GHA2017, 0.0_r8, 1.0_r8, sqrt(d2), 0.2_r8, lm, lsd, 1.0_r8, 0.3_r8, 1.05_r8, old, oldsd)
   call bci_new(ens_size, GHA2017, 0.0_r8, 1.0_r8, sqrt(d2), 0.2_r8, lm, lsd, 1.0_r8, 0.3_r8, 1.05_r8, new, newsd)
   print '(a,f4.1,a,f4.1,a,f5.1,a,2f8.4,a,2f8.4)', ' lam_b ', lm, ' sd ', lsd, ' ratio ', note_cases(3, k), &
      ': DART ', old, oldsd, '  patched ', new, newsd
enddo
end program driver
