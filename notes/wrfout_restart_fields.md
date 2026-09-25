# Fields in `wrfinput` but not in `wrfout` (restart-from-`wrfout` list)

Written 2026-09-25. These are the 65 variables present in our `theta_m0` `wrfinput_d01` but absent from our
`wrfout` (`cases/20250520/theta_m0/`, compared by variable name). Restarting a member from its own
`wrfout` (decision in `wrf_dart_tutorial_adaptation.md` 2.11) needs them added to the history output.

Each item gives: **name** — **status** — **definition** — **add via `iofields`?**

- **Status** is whether HRRRv4 (HRRRDAS) has the field in its own `wrfout`, i.e. whether HRRR's WRF 3.9
  Registry gives it the history flag `h`. HRRR builds `wrf.exe` with `WRF_SMOKE=1`
  (`sorc/build_hrrr_wrfarw.sh`, `build_hrrrdas_wrfarw.sh`), so its Registry is `Registry.EM_SMOKE` and its
  includes. None of the 65 is in *our* `wrfout`.
- **Definition** is from the variable's attributes in our `wrfinput_d01` (description, dimensions, shape, type,
  units), plus the entry in our WRF Registry (`Registry.EM` and its includes): symbol, I/O flags, file.
  Flag letters: `i` input, `r` restart, `h` history, `d`/`u` nest down/up interpolation, digits = other
  input streams.
- **`iofields`**: WRF's `iofields_filename` can add any Registry state field to a stream. It matches each
  entry, case-insensitively, against the field's Registry file name (`DataName`)
  (`frame/module_domain.F`, `modify_io_masks`). That is the netCDF name listed here. All 65 are state
  fields in our build, none is tied to a physics package (so all are always allocated, and all are
  present in our `wrfinput`). So all can be added with `+:h:0:<name>`. This is from reading the code; the
  restart test (2.11) will confirm that they appear in `wrfout` and that WRF reads them back.

Correction to the earlier count: 2.11 said HRRR adds 26 of these to history. That comparison used the
wrong set of Registry files for HRRR (it mixed in `registry.chem`/`registry.var_chem` and missed that HRRR
builds from `Registry.EM_SMOKE`). The correct count is **25 in HRRR's `wrfout`, 40 not**: `EROD` is
defined for HRRR only in `registry.smoke`, with flags `i12rdu` (no `h`).

Summary: in HRRR's `wrfout`: 25. Not in HRRR's `wrfout`: 40 (the 32 `LAT_*`/`LON_*` corner scalars, which
no WRF code uses and which are 0.0 in our files, plus `AL`, `ALB`, `CPLMASK`, `EROD`, `FRC_URB2D`,
`T_INIT`, `UOCE`, `VOCE`).

## The 65 fields

- **AL** — not in HRRR `wrfout` — inverse perturbation density; dims (Time, bottom_top, south_north, west_east) = 1×149×389×549; float32; units: m3 kg-1; our Registry: symbol `al`, flags `ir` (Registry.EM_COMMON); HRRR flags: `r` (Registry.EM_COMMON) — yes, `+:h:0:AL`
- **ALB** — not in HRRR `wrfout` — inverse base density; dims (Time, bottom_top, south_north, west_east) = 1×149×389×549; float32; units: m3 kg-1; our Registry: symbol `alb`, flags `irdus` (Registry.EM_COMMON); HRRR flags: `rdus` (Registry.EM_COMMON) — yes, `+:h:0:ALB`
- **CPLMASK** — not in HRRR `wrfout` — COUPLING MASK (0:VALUE FROM SST UPDATE; 1:VALUE FROM COUPLED OCEAN), vertical di; dims (Time, num_ext_model_couple_dom_stag, south_north, west_east) = 1×1×389×549; float32; units: none given; our Registry: symbol `cplmask`, flags `i0r` (Registry.EM_COMMON); HRRR flags: `i0r` (Registry.EM_COMMON) — yes, `+:h:0:CPLMASK`
- **DTS** — in HRRR `wrfout` — SMALL TIMESTEP; dims (Time) = 1; float32; units: none given; our Registry: symbol `dts`, flags `ir` (Registry.EM_COMMON); HRRR flags: `irh` (Registry.EM_COMMON) — yes, `+:h:0:DTS`
- **DTSEPS** — in HRRR `wrfout` — TIME WEIGHT CONSTANT FOR SMALL STEPS; dims (Time) = 1; float32; units: none given; our Registry: symbol `dtseps`, flags `ir` (Registry.EM_COMMON); HRRR flags: `irh` (Registry.EM_COMMON) — yes, `+:h:0:DTSEPS`
- **EROD** — not in HRRR `wrfout` — fraction of erodible surface in each grid cell (0-1); dims (Time, dust_erosion_dimension, south_north, west_east) = 1×3×389×549; float32; units: none; our Registry: symbol `erod`, flags `i012rd` (Registry.EM_COMMON); HRRR flags: `i12rdu` (registry.smoke) — yes, `+:h:0:EROD`
- **FCX** — in HRRR `wrfout` — RELAXATION TERM FOR BOUNDARY ZONE; dims (Time, DIM0010) = 1×10; float32; units: none given; our Registry: symbol `fcx`, flags `ir` (Registry.EM_COMMON); HRRR flags: `irh` (Registry.EM_COMMON) — yes, `+:h:0:FCX`
- **FNDALBSI** — in HRRR `wrfout` — ALBSI_LOGICAL; dims (Time) = 1; int32; units: -; our Registry: symbol `IFNDALBSI`, flags `ir` (Registry.EM_COMMON); HRRR flags: `irh` (Registry.EM_COMMON) — yes, `+:h:0:FNDALBSI`
- **FNDICEDEPTH** — in HRRR `wrfout` — ICEDEPTH_LOGICAL; dims (Time) = 1; int32; units: -; our Registry: symbol `IFNDICEDEPTH`, flags `ir` (Registry.EM_COMMON); HRRR flags: `irh` (Registry.EM_COMMON) — yes, `+:h:0:FNDICEDEPTH`
- **FNDSNOWH** — in HRRR `wrfout` — SNOWH_LOGICAL; dims (Time) = 1; int32; units: -; our Registry: symbol `IFNDSNOWH`, flags `i` (Registry.EM_COMMON); HRRR flags: `ih` (Registry.EM_COMMON) — yes, `+:h:0:FNDSNOWH`
- **FNDSNOWSI** — in HRRR `wrfout` — SNOWSI_LOGICAL; dims (Time) = 1; int32; units: -; our Registry: symbol `IFNDSNOWSI`, flags `ir` (Registry.EM_COMMON); HRRR flags: `irh` (Registry.EM_COMMON) — yes, `+:h:0:FNDSNOWSI`
- **FNDSOILW** — in HRRR `wrfout` — SOILW_LOGICAL; dims (Time) = 1; int32; units: -; our Registry: symbol `IFNDSOILW`, flags `i` (Registry.EM_COMMON); HRRR flags: `ih` (Registry.EM_COMMON) — yes, `+:h:0:FNDSOILW`
- **FRC_URB2D** — not in HRRR `wrfout` — URBAN FRACTION; dims (Time, south_north, west_east) = 1×389×549; float32; units: dimensionless; our Registry: symbol `FRC_URB2D`, flags `i012rd=(interp_fcnm)u=(copy_fcnm)` (Registry.EM_COMMON); HRRR flags: `i10rd=(interp_fcnm)u=(copy_fcnm)` (Registry.EM_COMMON) — yes, `+:h:0:FRC_URB2D`
- **GCX** — in HRRR `wrfout` — 2ND RELAXATION TERM FOR BOUNDARY ZONE; dims (Time, DIM0010) = 1×10; float32; units: none given; our Registry: symbol `gcx`, flags `ir` (Registry.EM_COMMON); HRRR flags: `irh` (Registry.EM_COMMON) — yes, `+:h:0:GCX`
- **LAKEFLAG** — in HRRR `wrfout` — Flag for lake  in the global attributes for metgrid data; dims (Time) = 1; int32; units: -; our Registry: symbol `LAKEFLAG`, flags `i0` (registry.lake); HRRR flags: `i0h` (registry.lake) — yes, `+:h:0:LAKEFLAG`
- **LAKE_DEPTH** — in HRRR `wrfout` — lake depth; dims (Time, south_north, west_east) = 1×389×549; float32; units: m; our Registry: symbol `lake_depth`, flags `i012rd=(interp_mask_water_field:lu_index,islake)` (Registry.EM_COMMON); HRRR flags: `i012rhd=(interp_mask_water_field:lu_index,islake)` (Registry.EM_COMMON) — yes, `+:h:0:LAKE_DEPTH`
- **LAKE_DEPTH_FLAG** — in HRRR `wrfout` — Flag for lakedepth  in the global attributes for metgrid data; dims (Time) = 1; int32; units: -; our Registry: symbol `LAKE_DEPTH_FLAG`, flags `i0` (registry.lake); HRRR flags: `i0h` (registry.lake) — yes, `+:h:0:LAKE_DEPTH_FLAG`
- **LANDUSEF** — in HRRR `wrfout` — LANDUSE FRACTION BY CATEGORY; dims (Time, land_cat_stag, south_north, west_east) = 1×21×389×549; float32; units: none given; our Registry: symbol `landusef`, flags `i012rdu` (Registry.EM_COMMON); HRRR flags: `i012rhdu` (Registry.EM_COMMON) — yes, `+:h:0:LANDUSEF`
- **LAT_LL_D** — not in HRRR `wrfout` — latitude lower left, massless point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lat_ll_d`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LAT_LL_D`
- **LAT_LL_T** — not in HRRR `wrfout` — latitude lower left, temp point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lat_ll_t`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LAT_LL_T`
- **LAT_LL_U** — not in HRRR `wrfout` — latitude lower left, u point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lat_ll_u`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LAT_LL_U`
- **LAT_LL_V** — not in HRRR `wrfout` — latitude lower left, v point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lat_ll_v`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LAT_LL_V`
- **LAT_LR_D** — not in HRRR `wrfout` — latitude lower right, massless point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lat_lr_d`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LAT_LR_D`
- **LAT_LR_T** — not in HRRR `wrfout` — latitude lower right, temp point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lat_lr_t`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LAT_LR_T`
- **LAT_LR_U** — not in HRRR `wrfout` — latitude lower right, u point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lat_lr_u`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LAT_LR_U`
- **LAT_LR_V** — not in HRRR `wrfout` — latitude lower right, v point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lat_lr_v`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LAT_LR_V`
- **LAT_UL_D** — not in HRRR `wrfout` — latitude up left, massless point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lat_ul_d`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LAT_UL_D`
- **LAT_UL_T** — not in HRRR `wrfout` — latitude up left, temp point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lat_ul_t`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LAT_UL_T`
- **LAT_UL_U** — not in HRRR `wrfout` — latitude up left, u point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lat_ul_u`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LAT_UL_U`
- **LAT_UL_V** — not in HRRR `wrfout` — latitude up left, v point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lat_ul_v`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LAT_UL_V`
- **LAT_UR_D** — not in HRRR `wrfout` — latitude up right, massless point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lat_ur_d`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LAT_UR_D`
- **LAT_UR_T** — not in HRRR `wrfout` — latitude up right, temp point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lat_ur_t`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LAT_UR_T`
- **LAT_UR_U** — not in HRRR `wrfout` — latitude up right, u point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lat_ur_u`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LAT_UR_U`
- **LAT_UR_V** — not in HRRR `wrfout` — latitude up right, v point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lat_ur_v`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LAT_UR_V`
- **LON_LL_D** — not in HRRR `wrfout` — longitude lower left, massless point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lon_ll_d`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LON_LL_D`
- **LON_LL_T** — not in HRRR `wrfout` — longitude lower left, temp point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lon_ll_t`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LON_LL_T`
- **LON_LL_U** — not in HRRR `wrfout` — longitude lower left, u point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lon_ll_u`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LON_LL_U`
- **LON_LL_V** — not in HRRR `wrfout` — longitude lower left, v point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lon_ll_v`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LON_LL_V`
- **LON_LR_D** — not in HRRR `wrfout` — longitude lower right, massless point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lon_lr_d`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LON_LR_D`
- **LON_LR_T** — not in HRRR `wrfout` — longitude lower right, temp point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lon_lr_t`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LON_LR_T`
- **LON_LR_U** — not in HRRR `wrfout` — longitude lower right, u point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lon_lr_u`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LON_LR_U`
- **LON_LR_V** — not in HRRR `wrfout` — longitude lower right, v point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lon_lr_v`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LON_LR_V`
- **LON_UL_D** — not in HRRR `wrfout` — longitude up left, massless point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lon_ul_d`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LON_UL_D`
- **LON_UL_T** — not in HRRR `wrfout` — longitude up left, temp point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lon_ul_t`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LON_UL_T`
- **LON_UL_U** — not in HRRR `wrfout` — longitude up left, u point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lon_ul_u`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LON_UL_U`
- **LON_UL_V** — not in HRRR `wrfout` — longitude up left, v point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lon_ul_v`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LON_UL_V`
- **LON_UR_D** — not in HRRR `wrfout` — longitude up right, massless point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lon_ur_d`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LON_UR_D`
- **LON_UR_T** — not in HRRR `wrfout` — longitude up right, temp point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lon_ur_t`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LON_UR_T`
- **LON_UR_U** — not in HRRR `wrfout` — longitude up right, u point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lon_ur_u`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LON_UR_U`
- **LON_UR_V** — not in HRRR `wrfout` — longitude up right, v point; dims (Time) = 1; float32; units: degrees; our Registry: symbol `lon_ur_v`, flags `ir` (Registry.EM_COMMON); HRRR flags: `ir` (Registry.EM_COMMON) — yes, `+:h:0:LON_UR_V`
- **QV_BASE** — in HRRR `wrfout` — BASE STATE QV IN IDEALIZED CASES; dims (Time, bottom_top) = 1×149; float32; units: none given; our Registry: symbol `qv_base`, flags `ir` (Registry.EM_COMMON); HRRR flags: `irh` (Registry.EM_COMMON) — yes, `+:h:0:QV_BASE`
- **SOILCBOT** — in HRRR `wrfout` — SOIL CAT FRACTION (BOTTOM); dims (Time, soil_cat_stag, south_north, west_east) = 1×16×389×549; float32; units: none given; our Registry: symbol `soilcbot`, flags `i012rdu` (Registry.EM_COMMON); HRRR flags: `i012rhdu` (Registry.EM_COMMON) — yes, `+:h:0:SOILCBOT`
- **SOILCTOP** — in HRRR `wrfout` — SOIL CAT FRACTION (TOP); dims (Time, soil_cat_stag, south_north, west_east) = 1×16×389×549; float32; units: none given; our Registry: symbol `soilctop`, flags `i012rdu` (Registry.EM_COMMON); HRRR flags: `i012rhdu` (Registry.EM_COMMON) — yes, `+:h:0:SOILCTOP`
- **STEP_NUMBER** — in HRRR `wrfout` — (no description); dims (Time) = 1; int32; units: -; our Registry: symbol `step_number`, flags `ir` (Registry.EM_COMMON); HRRR flags: `irh` (Registry.EM_COMMON) — yes, `+:h:0:STEP_NUMBER`
- **TOPOSLPX** — in HRRR `wrfout` — ELEVATION X SLOPE; dims (Time, south_north, west_east) = 1×389×549; float32; units: none given; our Registry: symbol `toposlpx`, flags `i012rdu` (Registry.EM_COMMON); HRRR flags: `i012rhdu` (Registry.EM_COMMON) — yes, `+:h:0:TOPOSLPX`
- **TOPOSLPY** — in HRRR `wrfout` — ELEVATION Y SLOPE; dims (Time, south_north, west_east) = 1×389×549; float32; units: none given; our Registry: symbol `toposlpy`, flags `i012rdu` (Registry.EM_COMMON); HRRR flags: `i012rhdu` (Registry.EM_COMMON) — yes, `+:h:0:TOPOSLPY`
- **T_BASE** — in HRRR `wrfout` — BASE STATE T IN IDEALIZED CASES; dims (Time, bottom_top) = 1×149; float32; units: K; our Registry: symbol `t_base`, flags `ir` (Registry.EM_COMMON); HRRR flags: `irh` (Registry.EM_COMMON) — yes, `+:h:0:T_BASE`
- **T_INIT** — not in HRRR `wrfout` — initial potential temperature; dims (Time, bottom_top, south_north, west_east) = 1×149×389×549; float32; units: K; our Registry: symbol `t_init`, flags `ird` (Registry.EM_COMMON); HRRR flags: `ird` (Registry.EM_COMMON) — yes, `+:h:0:T_INIT`
- **UOCE** — not in HRRR `wrfout` — SEA SURFACE ZONAL CURRENTS; dims (Time, south_north, west_east) = 1×389×549; float32; units: m s-1; our Registry: symbol `UOCE`, flags `i0124rd=(interp_mask_water_field:lu_index,iswater)` (Registry.EM_COMMON); HRRR flags: `i0124rd=(interp_mask_water_field:lu_index,iswater)` (Registry.EM_COMMON) — yes, `+:h:0:UOCE`
- **U_BASE** — in HRRR `wrfout` — BASE STATE X WIND IN IDEALIZED CASES; dims (Time, bottom_top) = 1×149; float32; units: none given; our Registry: symbol `u_base`, flags `ir` (Registry.EM_COMMON); HRRR flags: `irh` (Registry.EM_COMMON) — yes, `+:h:0:U_BASE`
- **U_FRAME** — in HRRR `wrfout` — FRAME X WIND; dims (Time) = 1; float32; units: m s-1; our Registry: symbol `u_frame`, flags `ir` (Registry.EM_COMMON); HRRR flags: `irh` (Registry.EM_COMMON) — yes, `+:h:0:U_FRAME`
- **VOCE** — not in HRRR `wrfout` — SEA SURFACE MERIDIONAL CURRENTS; dims (Time, south_north, west_east) = 1×389×549; float32; units: m s-1; our Registry: symbol `VOCE`, flags `i0124rd=(interp_mask_water_field:lu_index,iswater)` (Registry.EM_COMMON); HRRR flags: `i0124rd=(interp_mask_water_field:lu_index,iswater)` (Registry.EM_COMMON) — yes, `+:h:0:VOCE`
- **V_BASE** — in HRRR `wrfout` — BASE STATE Y WIND IN IDEALIZED CASES; dims (Time, bottom_top) = 1×149; float32; units: none given; our Registry: symbol `v_base`, flags `ir` (Registry.EM_COMMON); HRRR flags: `irh` (Registry.EM_COMMON) — yes, `+:h:0:V_BASE`
- **V_FRAME** — in HRRR `wrfout` — FRAME Y WIND; dims (Time) = 1; float32; units: m s-1; our Registry: symbol `v_frame`, flags `ir` (Registry.EM_COMMON); HRRR flags: `irh` (Registry.EM_COMMON) — yes, `+:h:0:V_FRAME`
- **Z_BASE** — in HRRR `wrfout` — BASE STATE HEIGHT IN IDEALIZED CASES; dims (Time, bottom_top) = 1×149; float32; units: none given; our Registry: symbol `z_base`, flags `ir` (Registry.EM_COMMON); HRRR flags: `irh` (Registry.EM_COMMON) — yes, `+:h:0:Z_BASE`
