# HRRRv4 Radar Data Assimilation: Technical Summary

## Scope and provenance

This document summarizes our reconstruction of the HRRRv4 radar-data-assimilation system, with emphasis on MRMS reflectivity assimilation in HRRRDAS, radar-reflectivity latent-heating initialization in deterministic HRRR, WSR-88D VAD winds, direct WSR-88D Level-II radial-velocity assimilation, Level-II radial-velocity superobbing and QC, the GSI radial-velocity observation operator, and the pathway by which radial velocity enters the HRRRDAS EnKF.

The reconstruction is based on the HRRR/HRRRDAS literature, NOAA documentation, the DTC radar-DA evaluation, and an audit of the public NOAA-EMC/HRRR source repository.

For source-code provenance, a useful reference snapshot is the NOAA-EMC/HRRR repository state on **24 May 2022**:

`44728d00f2ea7a09cd79cb5274484ab84e1dfc38`

This is contemporaneous with the 2022 HRRRv4 overview papers. We compared it with the later May 2026 repository state synchronized from `hrrr.v4.1.20`:

`40ee6058c2fc6624cbfbbe8cf1c20c59e6a45827`

Nearly all scientifically important radar-DA code discussed below is unchanged between those snapshots. The important exception is a 2024 robustness fix to the Level-II radar reader, discussed in Section 10.

---

## 1. Overall HRRRv4 radar-DA architecture

HRRRv4 uses several complementary radar-assimilation mechanisms rather than a single unified radar-analysis procedure.

The **HRRR Data-Assimilation System (HRRRDAS)** is a 36-member, 3-km ensemble system cycling hourly. It uses a serial ensemble Kalman filter / ensemble square-root filter (EnKF/EnSRF) and supplies both an ensemble mean and flow-dependent background-error covariances to deterministic HRRR.

The deterministic HRRR analysis uses GSI hybrid ensemble-variational data assimilation. Its first guess is generated through a one-hour preforecast initialized from the HRRRDAS ensemble mean. During that preforecast, MRMS reflectivity is used repeatedly through radar latent-heating initialization.

```text
HRRRDAS EnKF
    |
    | ensemble mean + ensemble covariance
    v
1-h deterministic HRRR preforecast
    |
    | radar-reflectivity latent-heating initialization
    v
deterministic HRRR GSI hybrid analysis
```

| Radar information | HRRRDAS | Deterministic HRRR |
|---|---|---|
| MRMS reflectivity | Direct EnKF assimilation | Primarily radar latent-heating / cloud-hydrometeor initialization |
| WSR-88D VAD winds | Assimilated as conventional horizontal winds | Assimilated as conventional horizontal winds |
| WSR-88D Level-II radial velocity | Direct scalar \(V_r\) assimilation via GSI observer -> EnKF | Direct scalar \(V_r\) assimilation in GSI |

---

## 2. MRMS reflectivity assimilation in HRRRDAS

HRRRDAS directly assimilates three-dimensional MRMS reflectivity with its EnKF.

The 2020 HRRRDAS documentation reports an extremely aggressive reduction in observation volume: approximately

\[
5\times10^8
\]

candidate/raw MRMS reflectivity observations are reduced to approximately

\[
2\times10^5
\]

observations used in an HRRRDAS analysis.

The documentation associates these values with the hourly HRRRDAS analysis workflow, but it does not unambiguously establish whether the \(5\times10^8\) number represents one instantaneous 3-D MRMS mosaic or all candidate observations entering the hourly preprocessing window. The safest wording is:

> Approximately 500 million candidate/raw MRMS reflectivity observations are processed for an hourly HRRRDAS analysis and reduced to approximately 200,000 assimilated observations.

The 2022 HRRR system paper gives horizontal reflectivity thinning of approximately **6 km in precipitating regions** and **12 km in nonprecipitating regions**, together with vertical thinning.

Retaining nonprecipitating observations is important because radar data can suppress spurious model precipitation as well as initiate observed precipitation.

HRRRDAS uses a separate reflectivity EnKF update with relatively tight localization:

\[
L_h \approx 18~\mathrm{km},
\qquad
L_v \approx 0.5~\text{scale height}.
\]

The reflectivity analysis updates

\[
U,\;V,\;T,\;QVAPOR,\;QCLOUD,\;QRAIN,\;QSNOW,\;QGRAUPEL.
\]

This is distinct from the broader conventional-observation EnKF pass.

---

## 3. MRMS reflectivity in deterministic HRRR: radar latent-heating initialization

Direct reflectivity assimilation in HRRRDAS is supplemented by a different mechanism in deterministic HRRR.

During the one-hour deterministic HRRR preforecast, three-dimensional MRMS reflectivity is used at approximately 15-min intervals, nominally at 45, 30, 15, and 0 min before the analysis/forecast start.

The radar-LHI procedure modifies the model latent-heating tendency according to observed reflectivity. Its core logic is approximately:

\[
Z > 28~\mathrm{dBZ}
\Rightarrow
\text{prescribed positive latent heating},
\]

\[
Z \le 0~\mathrm{dBZ}
\Rightarrow
\text{suppress latent heating / modeled precipitation},
\]

while for

\[
0 < Z \le 28~\mathrm{dBZ}
\]

or where radar data are unavailable, the model microphysics heating is retained.

Thus HRRRv4 combines direct EnKF reflectivity assimilation in HRRRDAS with repeated diabatic radar-reflectivity forcing in the deterministic HRRR preforecast.

---

## 4. VAD winds and direct Level-II radial velocity are different observation types

A **VAD wind** is a retrieved horizontal wind vector \((u,v)\) obtained by fitting the azimuthal variation of Doppler radial velocity around a radar. It is a spatially averaged/profile-scale quantity rather than a local gate measurement.

In the NCEP observation-processing system, VAD winds enter PREPBUFR as report type `VADWND` (type 224) and are treated as conventional wind-profile observations.

A **Level-II radial-velocity observation**, by contrast, remains a scalar line-of-sight measurement:

\[
y = V_r.
\]

It has its own radar-beam location, azimuth, elevation, and time.

The HRRR operational analysis scripts explicitly connect the NCEP NEXRAD Level-II radial-wind BUFR file to the GSI file name:

```text
l2rwbufr
```

and the GSI observation table activates it as:

```text
l2rwbufr   rw   null   l2rw   1.0 ...
```

The HRRRDAS GSI-observer script does the same thing.

Therefore, direct Level-II radial velocity was not merely supported by GSI; it was actually supplied to both deterministic HRRR GSI and HRRRDAS's GSI observer.

---

## 5. First-stage Level-II radial-velocity superobbing

The main Level-II superobbing code is:

```text
sorc/hrrr_gsi.fd/src/gsi/read_l2bufr_mod.f90
```

The operational HRRR configuration uses:

\[
\Delta\alpha = 5^\circ,
\quad
\Delta\theta = 0.25^\circ,
\quad
\Delta r = 5~\mathrm{km},
\]

with approximately \(\pm0.5\) h temporal acceptance, maximum elevation angle \(5^\circ\), maximum range 100 km, and at least 50 native radar gates per superob bin.

A useful shorthand for the first-stage superob is therefore:

\[
\boxed{
5^\circ\ \text{azimuth}
\times
0.25^\circ\ \text{elevation}
\times
5~\mathrm{km\ range}
}
\]

rather than a Cartesian-grid superob.

For each retained bin, GSI computes

\[
\overline{V_r}
=
\frac{1}{N}
\sum_i V_{r,i}
\]

and the within-bin spread

\[
\sigma_{V_r}
=
\sqrt{
\overline{V_r^2}
-
\overline{V_r}^{\,2}
}.
\]

A scientifically important detail is that this quantity is **not divided by \(\sqrt{N}\)**. Thus it behaves more like a measure of unresolved velocity variability / representativeness error than a sampling error of the mean.

The intermediate Level-II superobs are written internally as:

```text
radar_supobs_from_level2
```

before further GSI QC.

---

## 6. VAD-based QC of Level-II radial velocity

The first-stage polar superobbing is only the first data-reduction step. The subsequent processing is primarily in:

```text
sorc/hrrr_gsi.fd/src/gsi/read_radar.f90
```

GSI reads PREPBUFR `VADWND` observations and uses them as a strong consistency check on the Level-II radial-velocity superobs.

The relevant QC switch defaults to:

```text
vadwnd_l2rw_qc = .true.
```

The VAD winds are mapped to nominal 1000-ft vertical bins:

\[
\Delta z_{\mathrm{VAD}}
=
304.8~\mathrm{m}.
\]

For each Level-II superob, GSI projects the corresponding VAD horizontal wind into the radar line of sight:

\[
V_{r,\mathrm{VAD}}
=
u_{\mathrm{VAD}}\cos\alpha
+
v_{\mathrm{VAD}}\sin\alpha,
\]

using GSI's internal azimuth convention.

The key consistency criterion is:

\[
\frac{
\left|
V_{r,\mathrm{VAD}}
-
V_{r,\mathrm{obs}}
\right|
}{
\max\left(1,|\mathbf V_{\mathrm{VAD}}|\right)
}
\le 0.30.
\]

The source sets:

```text
vad_leash = 0.3
```

This is a strong filter. For example:

| VAD wind speed | Approx. maximum allowed radial-velocity departure |
|---:|---:|
| 5 m s\(^{-1}\) | 1.5 m s\(^{-1}\) |
| 10 m s\(^{-1}\) | 3 m s\(^{-1}\) |
| 20 m s\(^{-1}\) | 6 m s\(^{-1}\) |
| 30 m s\(^{-1}\) | 9 m s\(^{-1}\) |

For very weak winds the denominator floors at 1 m s\(^{-1}\), so the corresponding tolerance can be only about 0.3 m s\(^{-1}\).

Additional QC rejects observations with physically unreasonable speeds or heights, observations below radar elevation, poor VAD quality marks, and first-stage superobs with excessive within-bin radial-velocity spread. In the source examined, superobs with spread larger than approximately 6 m s\(^{-1}\) are rejected.

The DTC's FY2018 HRRR radial-velocity study independently found this VAD QC to be very restrictive and showed that disabling it could increase the retained radial-velocity volume by roughly an order of magnitude in one tested case.

---

## 7. Additional thinning after first-stage superobbing

The nominal 5-km range superobbing does **not** represent the final radial-velocity sampling density.

`read_radar.f90` applies another radar-centric thinning stage using a radial scale of approximately:

\[
20~\mathrm{km}.
\]

The number of azimuth sectors increases with range such that the corresponding azimuthal arc length is roughly 15-16 km. The vertical index is tied to the nominal 1000-ft VAD bins.

A useful approximate characterization is therefore:

\[
\sim 20~\mathrm{km}
\times
\sim 16~\mathrm{km}
\times
0.305~\mathrm{km},
\]

although the actual implementation is polar, not Cartesian.

Thus the final radial-velocity data density seen by GSI is substantially lower than one would infer from the first-stage 5-km radial bins alone.

---

## 8. GSI radial-velocity observation operator

The nonlinear radar radial-velocity processing is primarily in:

```text
sorc/hrrr_gsi.fd/src/gsi/setuprw.f90
```

The conventional physical Doppler operator is:

\[
H_{V_r}(x)
=
(u\cos\alpha+v\sin\alpha)\cos\theta
+
(w-v_t)\sin\theta,
\]

with equivalent forms depending on azimuth convention.

The GSI source contains this direct formulation and an optional terminal-fall-speed correction.

However, in the HRRR source/configuration examined, the relevant defaults are:

```text
if_vrobs_raw = .false.
if_vterminal = .false.
```

and we did not find an HRRR CONUS namelist override that changes these values.

Therefore, the operational HRRR pathway appears to use GSI's older **beam-envelope** treatment rather than a simple pointwise beam-center operator.

### 8.1 Beam-envelope treatment

Instead of evaluating radial velocity at one precise beam-center height, GSI defines a vertical beam-uncertainty region whose depth grows with radar range.

GSI evaluates modeled radial velocity at the model levels intersecting this envelope and obtains:

\[
V_{\min}=\min_k V_{r,k}^{f},
\qquad
V_{\max}=\max_k V_{r,k}^{f}.
\]

The effective nonlinear observation operator behaves approximately as:

\[
H(x)=
\begin{cases}
V_{\min}, & V_r^{obs}<V_{\min},\\[3pt]
V_r^{obs}, & V_{\min}\le V_r^{obs}\le V_{\max},\\[3pt]
V_{\max}, & V_r^{obs}>V_{\max}.
\end{cases}
\]

Therefore:

\[
V_{\min}
\le
V_r^{obs}
\le
V_{\max}
\Rightarrow
y-H(x)=0.
\]

In other words, if some model level within the assumed radar-beam vertical envelope is consistent with the observed radial velocity, the observation can receive zero innovation even if the beam-center model velocity differs substantially.

The DTC FY2018 evaluation identified this same behavior as a possible loss of useful high-resolution radial-velocity information and tested a more direct local operator.

### 8.2 Tangent-linear / adjoint operator

After the nonlinear `setuprw` step determines the effective vertical location and interpolation weights, GSI stores the information in an `rwNode`.

The inner-loop tangent-linear operator in `intrw.f90` is the conventional line-of-sight projection:

\[
\delta V_r
=
\cos\alpha\cos\theta\,\delta u
+
\sin\alpha\cos\theta\,\delta v
+
\sin\theta\,\delta w.
\]

The model increments are interpolated using the eight surrounding grid points.

Thus the unusual beam-envelope logic occurs primarily in the **nonlinear/outer-loop determination of \(H(x)\)**, while the GSI inner-loop operator is the familiar LOS linearization.

---

## 9. How Level-II radial velocity enters HRRRDAS

HRRRDAS does **not** first convert Level-II radial velocities into retrieved \(u,v\) winds.

Instead, GSI acts as the observation operator for the ensemble.

For the ensemble mean and for each individual member, GSI computes:

\[
H_i(x^{(m)})
\]

for every retained scalar radial-velocity observation.

These values are written to the GSI `diag_conv` diagnostic stream.

The EnKF code:

```text
sorc/hrrr_gsi.fd/src/enkf/readconvobs.f90
```

explicitly recognizes `rw` as an observation type. `mpi_readobs.f90` assembles the ensemble-mean and member-specific observation equivalents.

Conceptually, the EnKF receives:

\[
y_i,
\qquad
H_i(\overline{x}),
\qquad
H_i(x^{(1)}),\ldots,H_i(x^{(N)}).
\]

It then obtains the ensemble covariance:

\[
\operatorname{cov}(x,V_r)
=
\frac{1}{N-1}
\sum_m
(x_m-\bar x)
\left[
H(x_m)-\overline H
\right].
\]

The mean analysis update for one observation has the usual form:

\[
\overline{x}^{\,a}
=
\overline{x}^{\,f}
+
\frac{P_{xh}}
     {P_{hh}+R}
\left(
y-\overline H
\right).
\]

Thus:

\[
\boxed{
\text{HRRRDAS assimilates scalar }V_r,
\text{ not a prior }u,v\text{ retrieval.}
}
\]

This also means that details of the GSI \(V_r\) observation operator propagate directly into the ensemble observation-space statistics used by HRRRDAS.

---

## 10. 2022 source baseline versus later HRRR v4.x source

We compared the 24 May 2022 NOAA-EMC/HRRR repository state with the May 2026 `hrrr.v4.1.20`-synchronized state.

The following scientifically important files showed no changes between those dates:

- `parm/conus/hrrr_gsiparm.anl.sh`
- `parm/hrrrdas/hrrr_gsiparm.anl.sh`
- `read_radar.f90`
- `setuprw.f90`
- `intrw.f90`
- `stprw.f90`
- `m_rwNode.F90`
- `read_obs.F90`
- `setuprhsall.f90`
- `gsisub.F90`
- `obsmod.F90`
- `qcmod.f90`
- `readconvobs.f90`
- `mpi_readobs.f90`
- `enkf.f90`
- `scripts/hrrrdas/exhrrr_analysis.sh`
- `scripts/hrrrdas/exhrrr_enkf.sh`

The principal radar-related change after 2022 was a February 2024 modification to `read_l2bufr_mod.f90`, released with HRRR v4.1.13 after an operational RAP failure involving `l2rwbufr`.

The fix increased the supported maximum number of radar sites from 150 to 250, repaired radar-station indexing, and changed file-opening logic associated with the operational crash.

It did **not** change the scientific superob geometry, VAD-QC criterion, radial-velocity observation operator, or EnKF assimilation methodology.

Therefore, the May 2022 source snapshot is a reasonable reference for the HRRRv4 radar-assimilation implementation discussed in the 2022 HRRR overview literature.

---

## 11. Main technical takeaways

1. **HRRRv4 uses multiple radar-DA mechanisms.** MRMS reflectivity is directly assimilated in HRRRDAS and also used repeatedly through radar latent-heating initialization in the deterministic HRRR preforecast.
2. **VAD winds and direct Level-II radial velocity are fundamentally different observations.** VAD observations are retrieved horizontal winds; Level-II \(V_r\) remains a scalar line-of-sight velocity.
3. **Direct Level-II radial velocity is assimilated in both deterministic HRRR and HRRRDAS.** In HRRRDAS, GSI calculates member-specific \(H(x)\), and the EnKF uses the resulting scalar radial-velocity observation-space ensemble.
4. **The operational Level-II data undergo very strong reduction and QC before assimilation.**
5. **The within-superob velocity spread is retained as an error-like quantity rather than divided by \(\sqrt{N}\).**
6. **The VAD consistency QC is unusually restrictive.**
7. **The operational GSI nonlinear radial-velocity operator appears to use a beam-envelope treatment.**
8. **The GSI inner-loop TL/adjoint operator is the conventional LOS projection of \(u,v,w\) increments.**
9. **HRRRDAS treats direct radial velocity through the same broad EnKF pass as other conventional observations**, whereas reflectivity receives a separate, much tighter-localized update.

A compact representation of the Level-II pathway is:

```text
Level-II gates
    -> 5 deg x 0.25 deg x 5 km superobs
    -> VAD consistency QC
    -> error/spread and geometry QC
    -> additional ~20-km-scale thinning
    -> GSI H(x)
    -> deterministic hybrid GSI or HRRRDAS EnKF
```

---

## 12. Relevance to a new convection-permitting radar-DA system

Several elements of the HRRRv4 design are useful precedents:

- strong data-volume reduction before DA;
- explicit range/elevation restrictions;
- radar-space rather than model-grid-space superobbing;
- use of within-bin \(V_r\) variability as a representativeness-error metric;
- scalar \(V_r\) assimilation rather than converting all Doppler information to \(u,v\);
- use of a separate tight localization scale for reflectivity.

Other elements deserve careful reconsideration for a modern convection-permitting EnKF/DART application:

- the strong VAD rejection criterion;
- the relatively coarse second-stage Level-II thinning;
- broad conventional-observation localization for direct \(V_r\);
- the beam-envelope GSI observation operator; and
- the interaction between the beam-envelope operator and ensemble observation-space spread.

For a WRF-DART implementation, a natural starting point would be a physically direct Doppler forward operator:

\[
H(V_r)=
(u\sin\beta+v\cos\beta)\cos\theta
+
(w-v_t)\sin\theta,
\]

with explicit beam geometry/interpolation, carefully designed representativeness errors, and localization scales chosen specifically for convective-scale radar observations rather than inherited automatically from HRRR's conventional-observation settings.

---

## 13. Remaining uncertainty

One quantity we have **not** found in an authoritative HRRRv4 source is a representative post-QC, post-superob count of Level-II radial-velocity observations assimilated in a typical hourly analysis cycle.

For MRMS reflectivity, the HRRRDAS documentation explicitly gives the approximate reduction:

\[
500~\text{million}
\rightarrow
200{,}000.
\]

No directly comparable, authoritative HRRRv4 count has yet been found for direct Level-II radial velocity.

Operational GSI diagnostics/logs for archived HRRR/HRRRDAS cycles would likely be the cleanest way to determine this quantity.

---

# References

## HRRR / HRRRDAS papers and documentation

1. **Dowell, D. C., 2020:** *HRRR Data-Assimilation System (HRRRDAS) and HRRRE Forecasts: Documentation.* NOAA/ESRL/GSL, 1 March 2020.  
   https://rapidrefresh.noaa.gov/internal/pdfs/2020_Spring_Experiment_HRRRE_Documentation.pdf

2. **Dowell, D. C., C. R. Alexander, E. P. James, S. S. Weygandt, S. G. Benjamin, G. S. Manikin, B. T. Blake, J. M. Brown, J. B. Olson, M. Hu, T. G. Smirnova, T. Ladwig, J. S. Kenyon, R. Ahmadov, D. D. Turner, J. D. Duda, and T. I. Alcott, 2022:** *The High-Resolution Rapid Refresh (HRRR): An Hourly Updating Convection-Allowing Forecast Model. Part I: Motivation and System Description.* **Weather and Forecasting**, 37, 1371-1395.  
   DOI: https://doi.org/10.1175/WAF-D-21-0151.1  
   AMS: https://journals.ametsoc.org/view/journals/wefo/37/8/WAF-D-21-0151.1.xml

3. **Weygandt, S. S., S. G. Benjamin, M. Hu, C. R. Alexander, et al., 2022:** *Radar Reflectivity-Based Model Initialization Using Specified Latent Heating (Radar-LHI) within a Diabatic Digital Filter or Pre-Forecast Integration.* **Weather and Forecasting**, 37.  
   DOI: https://doi.org/10.1175/WAF-D-21-0142.1  
   AMS: https://journals.ametsoc.org/view/journals/wefo/37/8/WAF-D-21-0142.1.xml

4. **Benjamin, S. G., E. P. James, M. Hu, C. R. Alexander, T. T. Ladwig, J. M. Brown, S. S. Weygandt, D. D. Turner, P. Minnis, W. L. Smith Jr., and A. K. Heidinger, 2021:** *Stratiform Cloud-Hydrometeor Assimilation for HRRR and RAP Model Short-Range Weather Prediction.* **Monthly Weather Review**, 149, 2673-2694.  
   DOI: https://doi.org/10.1175/MWR-D-20-0319.1  
   AMS: https://journals.ametsoc.org/view/journals/mwre/149/8/MWR-D-20-0319.1.xml

5. **Developmental Testbed Center, FY2018:** *Radar Radial Velocity Assimilation in HRRR / DPQC Radar Radial Velocity Testing and Evaluation.*  
   https://dtcenter.org/sites/default/files/nodeurlarg1/dtc-dpqc-radar-radial-velocity-assimilation-hrrr-fy2018.pdf

## GSI documentation

6. **Developmental Testbed Center:** *GSI User's Guide, Version 3.7.*  
   https://dtcenter.org/sites/default/files/community-code/gsi/docs/users-guide/html_v3.7/gsi_ch1.html

## NOAA-EMC HRRR source repository

7. **NOAA-EMC/HRRR GitHub repository:**  
   https://github.com/NOAA-EMC/HRRR

8. **24 May 2022 reference commit:**  
   `44728d00f2ea7a09cd79cb5274484ab84e1dfc38`  
   https://github.com/NOAA-EMC/HRRR/commit/44728d00f2ea7a09cd79cb5274484ab84e1dfc38

9. **1 May 2026 v4.1.20-sync commit used for comparison:**  
   `40ee6058c2fc6624cbfbbe8cf1c20c59e6a45827`  
   https://github.com/NOAA-EMC/HRRR/commit/40ee6058c2fc6624cbfbbe8cf1c20c59e6a45827

10. **13 February 2024 Level-II reader fix (HRRR v4.1.13):**  
    `85e21fa324d0f700b2a30d60fa8fadf7f6e5e659`  
    https://github.com/NOAA-EMC/HRRR/commit/85e21fa324d0f700b2a30d60fa8fadf7f6e5e659

## Core source files at the 24 May 2022 reference commit

- Deterministic HRRR analysis driver:  
  https://github.com/NOAA-EMC/HRRR/blob/44728d00f2ea7a09cd79cb5274484ab84e1dfc38/scripts/conus/exhrrr_analysis.sh

- HRRRDAS GSI-observer driver:  
  https://github.com/NOAA-EMC/HRRR/blob/44728d00f2ea7a09cd79cb5274484ab84e1dfc38/scripts/hrrrdas/exhrrr_analysis.sh

- HRRRDAS EnKF driver:  
  https://github.com/NOAA-EMC/HRRR/blob/44728d00f2ea7a09cd79cb5274484ab84e1dfc38/scripts/hrrrdas/exhrrr_enkf.sh

- Deterministic HRRR GSI configuration:  
  https://github.com/NOAA-EMC/HRRR/blob/44728d00f2ea7a09cd79cb5274484ab84e1dfc38/parm/conus/hrrr_gsiparm.anl.sh

- HRRRDAS GSI configuration:  
  https://github.com/NOAA-EMC/HRRR/blob/44728d00f2ea7a09cd79cb5274484ab84e1dfc38/parm/hrrrdas/hrrr_gsiparm.anl.sh

- Level-II BUFR reader / first-stage superobbing:  
  https://github.com/NOAA-EMC/HRRR/blob/44728d00f2ea7a09cd79cb5274484ab84e1dfc38/sorc/hrrr_gsi.fd/src/gsi/read_l2bufr_mod.f90

- VAD QC / radial-wind QC / additional thinning:  
  https://github.com/NOAA-EMC/HRRR/blob/44728d00f2ea7a09cd79cb5274484ab84e1dfc38/sorc/hrrr_gsi.fd/src/gsi/read_radar.f90

- Nonlinear radial-velocity setup / observation operator:  
  https://github.com/NOAA-EMC/HRRR/blob/44728d00f2ea7a09cd79cb5274484ab84e1dfc38/sorc/hrrr_gsi.fd/src/gsi/setuprw.f90

- Radar-wind observation-node definition:  
  https://github.com/NOAA-EMC/HRRR/blob/44728d00f2ea7a09cd79cb5274484ab84e1dfc38/sorc/hrrr_gsi.fd/src/gsi/m_rwNode.F90

- Tangent-linear / adjoint radar-wind operator:  
  https://github.com/NOAA-EMC/HRRR/blob/44728d00f2ea7a09cd79cb5274484ab84e1dfc38/sorc/hrrr_gsi.fd/src/gsi/intrw.f90

- Radar-wind contribution to GSI observation penalty / step calculation:  
  https://github.com/NOAA-EMC/HRRR/blob/44728d00f2ea7a09cd79cb5274484ab84e1dfc38/sorc/hrrr_gsi.fd/src/gsi/stprw.f90

- GSI conventional-diagnostic reader, including `rw`:  
  https://github.com/NOAA-EMC/HRRR/blob/44728d00f2ea7a09cd79cb5274484ab84e1dfc38/sorc/hrrr_gsi.fd/src/enkf/readconvobs.f90

- MPI observation assembly for the EnKF:  
  https://github.com/NOAA-EMC/HRRR/blob/44728d00f2ea7a09cd79cb5274484ab84e1dfc38/sorc/hrrr_gsi.fd/src/enkf/mpi_readobs.f90

- EnKF / serial ensemble square-root filter implementation:  
  https://github.com/NOAA-EMC/HRRR/blob/44728d00f2ea7a09cd79cb5274484ab84e1dfc38/sorc/hrrr_gsi.fd/src/enkf/enkf.f90

---

*Prepared as a technical summary of the HRRRv4 radar-data-assimilation investigation for the LASSO BNF DA planning effort.*
