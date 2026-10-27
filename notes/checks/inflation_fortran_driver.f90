! Driver for inflation_fortran_check.sh (notes/dart_adaptive_inflation.md Sec. 5.3, 5.4, 7).
! Calls DART's bayes_cov_inflate and change_GA_IG, compiled stand-alone in float32 (our r8 = r4)
! and float64, for the wrong-root cases and the sd update at small sd.
program driver
use infl_test_mod
implicit none
real(r8) :: lm, lsd, newm, newsd, sp2, so2, d2, beta
integer :: q, i, k
integer :: qs(5) = (/ 4, 6, 8, 9, 12 /)
real(r8) :: sds(5) = (/ 0.6_r8, 0.3_r8, 0.25_r8, 0.2_r8, 0.15_r8 /)
print '(a,i3)', 'precision digits: ', precision(1.0_r8)
! 1. root selection, steep likelihood: sp2 = 1, so2 = 0.2, lambda_b = 1, sd = 0.6, gamma = 1, N = 5
do k = 1, 5
   q = qs(k)
   sp2 = 1.0_r8; so2 = 0.2_r8; d2 = q * (sp2 + so2)
   call bayes_cov_inflate(5, GHA2017, 0.0_r8, sp2, sqrt(d2), so2, 1.0_r8, 0.6_r8, 1.0_r8, 0.3_r8, 1.05_r8, newm, newsd)
   print '(a,i3,a,f8.4,a,f8.4)', ' fl5  d2/(var+R) =', q, ': lambda ', newm, '  sd ', newsd
   call bayes_cov_inflate(5, AND2009, 0.0_r8, sp2, sqrt(d2), so2, 1.0_r8, 0.6_r8, 1.0_r8, 0.3_r8, 1.05_r8, newm, newsd)
   print '(a,i3,a,f8.4,a,f8.4)', ' fl2  d2/(var+R) =', q, ': lambda ', newm, '  sd ', newsd
end do
! 2. sd update at small sd (overflow of beta**alpha / gamma(alpha)?): METAR-like, lambda_b = 1, floor 0.05
do i = 1, 5
   lsd = sds(i)
   call change_GA_IG(1.0_r8, lsd**2, beta)
   call bayes_cov_inflate(5, GHA2017, 0.0_r8, 0.25_r8, 2.0_r8, 1.5876_r8, 1.0_r8, lsd, 1.0_r8, 0.05_r8, 1.05_r8, newm, newsd)
   print '(a,f5.2,a,f9.3,a,es10.3,a,f8.4,a,f8.4)', ' fl5 sd_in=', lsd, ' beta=', beta, ' beta**alpha=', beta**(beta-1.0_r8), &
        ' -> lambda ', newm, ' sd ', newsd
end do
end program driver
