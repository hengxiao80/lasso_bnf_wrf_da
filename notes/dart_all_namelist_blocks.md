# Complete DART namelist blocks relevant to this project

`notes/dart_input_nml_comparison.md` only shows namelist blocks that actually appear in
`work/input.nml` and/or the two tutorial templates (40 blocks total). This document goes one
level deeper: every namelist block declared in DART **source** (`.f90`) that could plausibly
ever belong in this project's `input.nml`, whether or not it is currently present in any of
those three files, together with whether it has a `.rst` doc page.

## Scope

DART's full source tree declares ~176 uniquely-named namelist blocks, but most belong to
models, location modules, and obs converters this project never touches (CAM, FV3, POP, MPAS,
the `threed_cartesian`/`oned`/`channel`/`annulus` location modules, satellite/ocean obs
converters, etc.). This list is restricted to blocks whose source lives in:

- `assimilation_code/modules/assimilation/` (the shared EAKF/inflation/QC core)
- `assimilation_code/modules/io/`, `assimilation_code/modules/observations/`,
  `assimilation_code/modules/utilities/` (shared I/O, obs-sequence, and utility modules)
- `assimilation_code/location/threed_sphere/` (the location module WRF's `model_mod` uses;
  the other five location modules — `threed_cartesian`, `oned`, `channel`, `annulus`,
  `twod_annulus` — are excluded)
- `assimilation_code/programs/` — restricted to the programs actually built for this project
  (verified against the executables sitting in `../software/DART/models/wrf/work/`, plus
  `preprocess`, which is a build-time tool and doesn't leave a runtime executable there) —
  **plus** `compare_states`, whose namelist block is present in the real `work/input.nml`
  even though nothing built `compare_states` itself in this tree
- `models/wrf/` (model_mod and the WRF_DART_utilities programs)
- `observations/forward_operators/` — restricted to `obs_def_mod.f90` (the preprocess-generated
  file) and the two forward operators it's built from that are actually named in `work/input.nml`'s
  `preprocess_nml` `obs_type_files`/history (`obs_def_gps_mod.f90`, `obs_def_radar_mod.f90`),
  plus `obs_def_tpw_mod.f90` (present in `work/input.nml` even though `tpw` isn't currently one
  of the listed `obs_type_files` — likely a leftover from an earlier config)

Also included, per the user's 2026-09-22 note that the project plans to bring in the
NCEP/prepbufr obs converter later (and possibly all obs types HRRRv4's GSI ingests):
`observations/obs_converters/NCEP/ascii_to_obs/create_real_obs.f90` (`&ncepobs_nml`),
`observations/obs_converters/NCEP/prep_bufr/src/prepbufr.f` (`&prep_bufr_nml`), and
`observations/obs_converters/gps/convert_cosmic_gps_cdf.f90` (`&convert_cosmic_gps_nml`, the
GPS RO converter — HRRRv4 also assimilates GPS-RO bending angle/refractivity, via a different
decoder, but this is DART's equivalent). These three aren't wired into anything this repo has
run yet; `&ncepobs_nml` and `&prep_bufr_nml` are only present here because they ship as stock
defaults in `work/input.nml`, not because this project configured them.

**39 blocks** below. Doc status was checked by testing for a `.rst` file at the same path as the
source `.f90` (DART's usual `<module>_mod.rst` / `programs/<name>/<name>.rst` convention),
verified by file existence rather than by grepping — the same method used for
`dart_input_nml_comparison.md`.

## Core assimilation algorithm (`assimilation_code/modules/assimilation/`)

### `&algorithm_info_nml`
Source: `algorithm_info_mod.f90` · Doc: **none** (source only) · In: `work`, `template`, `template_nest`

- `qceff_table_filename`

### `&assim_tools_nml`
Source: `assim_tools_mod.f90` · Doc: `assim_tools_mod.rst` · In: `work`, `template`, `template_nest`

- `cutoff`
- `sort_obs_inc`
- `spread_restoration`
- `sampling_error_correction`
- `adaptive_localization_threshold`
- `adaptive_cutoff_floor`
- `print_every_nth_obs`
- `rectangular_quadrature`
- `gaussian_likelihood_tails`
- `output_localization_diagnostics`
- `localization_diagnostics_file`
- `special_localization_obs_types`
- `special_localization_cutoffs`
- `distribute_mean`
- `close_obs_caching`
- `adjust_obs_impact`
- `obs_impact_filename`
- `allow_any_impact_values`
- `convert_all_state_verticals_first`
- `convert_all_obs_verticals_first`

### `&cov_cutoff_nml`
Source: `cov_cutoff_mod.f90` · Doc: `cov_cutoff_mod.rst` · In: `work`, `template`, `template_nest`

- `select_localization`

### `&filter_nml`
Source: `filter_mod.f90` · Doc: `filter_mod.rst` · In: `work`, `template`, `template_nest`

- `async`
- `adv_ens_command`
- `ens_size`
- `tasks_per_model_advance`
- `output_members`
- `obs_sequence_in_name`
- `obs_sequence_out_name`
- `init_time_days`
- `init_time_seconds`
- `first_obs_days`
- `first_obs_seconds`
- `last_obs_days`
- `last_obs_seconds`
- `obs_window_days`
- `obs_window_seconds`
- `num_output_state_members`
- `num_output_obs_members`
- `output_interval`
- `num_groups`
- `trace_execution`
- `output_forward_op_errors`
- `output_timestamps`
- `inf_flavor`
- `inf_initial_from_restart`
- `inf_sd_initial_from_restart`
- `inf_sd_max_change`
- `inf_deterministic`
- `inf_damping`
- `inf_initial`
- `inf_sd_initial`
- `inf_lower_bound`
- `inf_upper_bound`
- `inf_sd_lower_bound`
- `silence`
- `distributed_state`
- `single_file_in`
- `single_file_out`
- `perturb_from_single_instance`
- `perturbation_amplitude`
- `perturbation_method`
- `compute_posterior`
- `stages_to_write`
- `input_state_files`
- `output_state_files`
- `output_state_file_list`
- `input_state_file_list`
- `output_mean`
- `output_sd`
- `write_all_stages_at_end`
- `write_obs_every_cycle`
- `allow_missing_clm`

Note: `filter_mod.f90` has an alternate variant, `filter_mod.dopplerfold.f90`, in the same
directory. Not built here (the `quickbuild.log` compile line references the plain
`filter_mod.f90`), so excluded.

### `&kde_nml`
Source: `kde_distribution_mod.f90` · Doc: **none** (source only) · In: none of the three files

- `quadrature_order`

Not currently in `work/input.nml`, `template`, or `template_nest` at all — it's a newer block
(used by the `kde` inflation/probit-transform distribution option) that isn't in the stock
input.nml this project built against.

### `&probit_transform_nml`
Source: `probit_transform_mod.f90` · Doc: **none** (source only) · In: `work`, `template`, `template_nest`

- `fix_bound_violations`
- `use_logit_instead_of_probit`
- `do_inverse_check`

### `&quality_control_nml`
Source: `quality_control_mod.f90` · Doc: `quality_control_mod.rst` · In: `work`, `template`, `template_nest`

- `input_qc_threshold`
- `outlier_threshold`
- `enable_special_outlier_code`

### `&reg_factor_nml`
Source: `reg_factor_mod.f90` · Doc: `reg_factor_mod.rst` · In: `work`, `template`, `template_nest`

- `select_regression`
- `input_reg_file`
- `save_reg_diagnostics`
- `reg_diagnostics_file`

## Location (`assimilation_code/location/threed_sphere/`)

### `&location_nml`
Source: `location_mod.f90` · Doc: `location_mod.rst` · In: `work`, `template`, `template_nest`

- `horiz_dist_only`
- `vert_normalization_pressure`
- `vert_normalization_height`
- `vert_normalization_level`
- `vert_normalization_scale_height`
- `approximate_distance`
- `nlon`
- `nlat`
- `output_box_info`
- `print_box_level`
- `special_vert_normalization_obs_types`
- `special_vert_normalization_pressures`
- `special_vert_normalization_heights`
- `special_vert_normalization_levels`
- `special_vert_normalization_scale_heights`

## I/O and observation-sequence core

### `&state_vector_io_nml`
Source: `assimilation_code/modules/io/state_vector_io_mod.f90` · Doc: **none** (source only) · In: `work`, `template`, `template_nest`

- `buffer_state_io`
- `single_precision_output`

### `&obs_kind_nml`
Source: `assimilation_code/modules/observations/obs_kind_mod.f90` · Doc: `obs_kind_mod.rst` · In: `work`, `template`, `template_nest`

- `assimilate_these_obs_types`
- `evaluate_these_obs_types`
- `use_precomputed_FOs_these_obs_types`

### `&obs_sequence_nml`
Source: `assimilation_code/modules/observations/obs_sequence_mod.f90` · Doc: `obs_sequence_mod.rst` · In: `work`, `template`, `template_nest`

- `write_binary_obs_sequence`
- `read_binary_file_format`

## Utilities (`assimilation_code/modules/utilities/`)

### `&ensemble_manager_nml`
Source: `ensemble_manager_mod.f90` · Doc: `ensemble_manager_mod.rst` · In: `work`, `template`, `template_nest`

- `communication_configuration`
- `layout`
- `tasks_per_node`
- `debug`

### `&mpi_utilities_nml`
Source: `mpi_utilities_mod.f90` · Doc: `mpi_utilities_mod.rst` · In: `work`, `template`, `template_nest`

- `reverse_task_layout`
- `all_tasks_print`
- `verbose`
- `async2_verbose`
- `async4_verbose`
- `shell_name`
- `separate_node_sync`
- `create_local_comm`
- `make_copy_before_sendrecv`
- `make_copy_before_broadcast`

Note: this is the MPI-parallel variant, confirmed from `quickbuild.log` (`mpif90 ... -c
.../mpi_utilities_mod.f90` while building `filter` and the other MPI programs). A serial stub
(`null_mpi_utilities_mod.f90`, no namelist) is what `preprocess` links against instead, and
there's a third, unused variant (`mpif08_utilities_mod.f90`) not referenced anywhere in the
build log — excluded here.

### `&schedule_nml`
Source: `schedule_mod.f90` · Doc: `schedule_mod.rst` · In: `work`, `template`, `template_nest`

- `first_bin_start`
- `first_bin_end`
- `last_bin_end`
- `bin_interval_days`
- `bin_interval_seconds`
- `max_num_bins`
- `calendar`
- `print_table`

### `&utilities_nml`
Source: `utilities_mod.f90` · Doc: `utilities_mod.rst` · In: `work`, `template`, `template_nest`

- `TERMLEVEL`
- `logfilename`
- `module_details`
- `nmlfilename`
- `print_debug`
- `write_nml`

## Programs / standalone tools (`assimilation_code/programs/`)

### `&closest_member_tool_nml`
Doc: `closest_member_tool.rst` · In: `work`, `template`, `template_nest`

- `input_restart_files`
- `input_restart_file_list`
- `output_file_name`
- `ens_size`
- `single_restart_file_in`
- `difference_method`
- `use_only_qtys`

### `&compare_states_nml`
Doc: `compare_states.rst` · In: `work` only

- `debug`
- `fail_on_missing_field`
- `do_all_numeric_fields`
- `fieldnames`
- `fieldlist_file`
- `only_report_differences`

Note: `compare_states` isn't one of the executables actually built in
`models/wrf/work/` (no `compare_states` binary there), but its namelist block ships in the real
`work/input.nml` regardless — it's a stock default block, not something this project configured.

### `&fill_inflation_restart_nml`
Doc: `fill_inflation_restart.rst` · In: `work`, `template`, `template_nest`

- `prior_inf_mean`
- `prior_inf_sd`
- `post_inf_mean`
- `post_inf_sd`
- `verbose`
- `write_prior_inf`
- `write_post_inf`
- `input_state_files`
- `single_file`

### `&model_mod_check_nml`
Doc: `model_mod_check.rst` · In: `work` only

- `x_ind`
- `num_ens`
- `loc_of_interest`
- `quantity_of_interest`
- `interp_test_dlat`
- `interp_test_lonrange`
- `interp_test_dlon`
- `interp_test_latrange`
- `interp_test_dvert`
- `interp_test_vertrange`
- `interp_test_dx`
- `interp_test_xrange`
- `interp_test_dy`
- `interp_test_yrange`
- `interp_test_dz`
- `interp_test_zrange`
- `verbose`
- `test1thru`
- `run_tests`
- `interp_test_vertcoord`
- `single_file`
- `input_state_files`
- `output_state_files`
- `all_metadata_file`

### `&obs_common_subset_nml`
Doc: `obs_common_subset.rst` · In: `work` only

- `num_to_compare_at_once`
- `filename_seq`
- `filename_seq_list`
- `filename_out_suffix`
- `print_only`
- `print_every`
- `dart_qc_threshold`
- `calendar`
- `eval_and_assim_can_match`

### `&obs_diag_nml`
Source: `assimilation_code/programs/obs_diag/threed_sphere/obs_diag.f90` · Doc: `obs_diag.rst` · In: `work`, `template`, `template_nest`

- `obs_sequence_name`
- `obs_sequence_list`
- `first_bin_center`
- `last_bin_center`
- `bin_separation`
- `bin_width`
- `time_to_skip`
- `max_num_bins`
- `plevel`
- `hlevel`
- `mlevel`
- `Nregions`
- `lonlim1`
- `lonlim2`
- `latlim1`
- `latlim2`
- `reg_names`
- `print_mismatched_locs`
- `create_rank_histogram`
- `outliers_in_histogram`
- `plevel_edges`
- `hlevel_edges`
- `mlevel_edges`
- `verbose`
- `trusted_obs`
- `use_zero_error_obs`

Note: there are three other `obs_diag_nml` variants in the source tree
(`programs/obs_diag/oned/`, `programs/obs_diag/threed_cartesian/`,
`programs/obs_diag/streamflow/streamflow_obs_diag.f90`) for other location geometries — this
project's `obs_diag` executable is the `threed_sphere` one, matching WRF's location module.

### `&obs_selection_nml`
Doc: `obs_selection.rst` · In: `work`, `template`, `template_nest`

- `num_input_files`
- `filename_seq`
- `filename_seq_list`
- `filename_out`
- `selections_file`
- `selections_is_obs_seq`
- `print_only`
- `calendar`
- `print_timestamps`
- `partial_write`
- `latlon_tolerance`
- `surface_tolerance`
- `pressure_tolerance`
- `height_tolerance`
- `scaleheight_tolerance`
- `level_tolerance`
- `match_vertical`

### `&obs_seq_coverage_nml`
Doc: `obs_seq_coverage.rst` · In: `work`, `template`, `template_nest`

- `obs_sequences`
- `obs_sequence_list`
- `obs_of_interest`
- `textfile_out`
- `netcdf_out`
- `calendar`
- `first_analysis`
- `last_analysis`
- `forecast_length_days`
- `forecast_length_seconds`
- `verification_interval_seconds`
- `temporal_coverage_percent`
- `lonlim1`
- `lonlim2`
- `latlim1`
- `latlim2`
- `verbose`
- `debug`

### `&obs_seq_to_netcdf_nml`
Doc: `obs_seq_to_netcdf.rst` · In: `work`, `template`, `template_nest`

- `obs_sequence_name`
- `obs_sequence_list`
- `lonlim1`
- `lonlim2`
- `latlim1`
- `latlim2`
- `verbose`
- `append_to_netcdf`
- `debug`

### `&obs_sequence_tool_nml`
Doc: `obs_sequence_tool.rst` · In: `work`, `template`, `template_nest`

- `num_input_files`
- `filename_seq`
- `filename_seq_list`
- `filename_out`
- `first_obs_days`
- `first_obs_seconds`
- `last_obs_days`
- `last_obs_seconds`
- `obs_types`
- `keep_types`
- `min_box`
- `max_box`
- `print_only`
- `min_lat`
- `max_lat`
- `min_lon`
- `max_lon`
- `min_qc`
- `max_qc`
- `qc_metadata`
- `min_copy`
- `max_copy`
- `copy_metadata`
- `copy_type`
- `gregorian_cal`
- `min_gps_height`
- `edit_copy_metadata`
- `new_copy_index`
- `edit_qc_metadata`
- `new_qc_index`
- `synonymous_copy_list`
- `synonymous_qc_list`
- `edit_copies`
- `edit_qcs`
- `new_copy_metadata`
- `new_qc_metadata`
- `new_copy_data`
- `new_qc_data`
- `remove_precomputed_FO_values`

### `&obs_seq_verify_nml`
Doc: `obs_seq_verify.rst` · In: `work`, `template`, `template_nest`

- `obs_sequences`
- `obs_sequence_list`
- `input_template`
- `netcdf_out`
- `obtype_string`
- `calendar`
- `print_every`
- `verbose`
- `debug`

### `&perfect_model_obs_nml`
Doc: `perfect_model_obs.rst` · In: `work`, `template`, `template_nest`

- `read_input_state_from_file`
- `write_output_state_to_file`
- `init_time_days`
- `init_time_seconds`
- `async`
- `first_obs_days`
- `first_obs_seconds`
- `last_obs_days`
- `last_obs_seconds`
- `output_interval`
- `obs_seq_in_file_name`
- `obs_seq_out_file_name`
- `adv_ens_command`
- `tasks_per_model_advance`
- `obs_window_days`
- `obs_window_seconds`
- `silence`
- `trace_execution`
- `output_timestamps`
- `print_every_nth_obs`
- `output_forward_op_errors`
- `input_state_files`
- `output_state_files`
- `single_file_in`
- `single_file_out`

### `&perturb_single_instance_nml`
Doc: `perturb_single_instance.rst` · In: none of the three files

- `ens_size`
- `input_files`
- `output_files`
- `output_file_list`
- `perturbation_amplitude`
- `perturbation_method`
- `single_restart_file_in`

Note: `perturb_single_instance` **is** built in `models/wrf/work/` (the binary is there), but
this block isn't in `work/input.nml`, `template`, or `template_nest` — none of the three files
this project has actually configure it. Something to add if/when perturbing a single restart
into an ensemble is needed for the perturbation-bank step mentioned in the plan.

### `&preprocess_nml`
Doc: `preprocess.rst` · In: `work`, `template`, `template_nest`

- `input_obs_def_mod_file`
- `output_obs_def_mod_file`
- `input_obs_qty_mod_file`
- `output_obs_qty_mod_file`
- `input_obs_kind_mod_file`
- `output_obs_kind_mod_file`
- `obs_type_files`
- `quantity_files`
- `overwrite_output`
- `input_files`

Note: `input_obs_kind_mod_file`/`output_obs_kind_mod_file`/`input_files` are explicitly marked
`! deprecate` in the source — kept for backwards-compatible namelist reads, superseded by
`input_obs_qty_mod_file`/`output_obs_qty_mod_file`/`obs_type_files`.

## WRF model (`models/wrf/`)

### `&model_nml`
Source: `models/wrf/model_mod.f90` · Doc: documented in `models/wrf/readme.rst` (no dedicated
`model_mod.rst`) · In: `work`, `template`, `template_nest`

- `num_moist_vars`
- `num_domains`
- `calendar_type`
- `surf_obs`
- `soil_data`
- `h_diab`
- `default_state_variables`
- `wrf_state_variables`
- `wrf_state_bounds`
- `sfc_elev_max_diff`
- `adv_mod_command`
- `assimilation_period_seconds`
- `allow_obs_below_vol`
- `vert_localization_coord`
- `center_search_half_length`
- `center_spline_grid_scale`
- `circulation_pres_level`
- `circulation_radius`
- `polar`
- `periodic_x`
- `periodic_y`
- `scm`
- `allow_perturbed_ics`

Note: `models/wrf/WRF_DART_utilities/ensemble_init.f90` declares its own, separate copy of
`&model_nml` (same block name, nearly the same variable list, minus `allow_perturbed_ics` but
plus `output_state_vector`) — `ensemble_init` reads WRF's model namelist directly rather than
going through `model_mod`. No separate doc page; `readme.rst`'s coverage applies to both.

### `&replace_wrf_fields_nml`
Source: `models/wrf/WRF_DART_utilities/replace_wrf_fields.f90` · Doc: `replace_wrf_fields.rst` · In: `work`, `template`, `template_nest`

- `debug`
- `fail_on_missing_field`
- `fieldnames`
- `fieldlist_file`

### `&wrf_obs_preproc_nml`
Source: `models/wrf/WRF_DART_utilities/wrf_dart_obs_preprocess.f90` · Doc: `wrf_dart_obs_preprocess.rst` · In: `work`, `template`, `template_nest`

- `file_name_input`
- `file_name_output`
- `include_sig_data`
- `superob_aircraft`
- `superob_sat_winds`
- `sfc_elevation_check`
- `overwrite_ncep_sfc_qc`
- `overwrite_ncep_satwnd_qc`
- `aircraft_pres_int`
- `sat_wind_pres_int`
- `sfc_elevation_tol`
- `obs_pressure_top`
- `obs_height_top`
- `obs_boundary`
- `sonde_extra`
- `metar_extra`
- `acars_extra`
- `land_sfc_extra`
- `marine_sfc_extra`
- `sat_wind_extra`
- `profiler_extra`
- `trop_cyclone_extra`
- `gpsro_extra`
- `tc_sonde_radii`
- `increase_bdy_error`
- `maxobsfac`
- `obsdistbdy`
- `sat_wind_horiz_int`
- `aircraft_horiz_int`
- `overwrite_obs_time`

## NCEP/prepbufr and GPS RO obs converters (`observations/obs_converters/`)

Not currently used by this project — `wrf_dart_obs_preprocess` (see WRF model section above)
is how observations reach `obs_seq` files today, per `cases/20250520/DATA_SOURCES.md`. Included
here because the plan is to bring in the NCEP/prepbufr path later.

### `&ncepobs_nml`
Source: `NCEP/ascii_to_obs/create_real_obs.f90` · Doc: `create_real_obs.rst` · In: `work` only

- `year`
- `month`
- `day`
- `tot_days`
- `max_num`
- `select_obs`
- `ObsBase`
- `ADPUPA`
- `AIRCAR`
- `AIRCFT`
- `SATEMP`
- `SFCSHP`
- `ADPSFC`
- `SATWND`
- `obs_U`
- `obs_V`
- `obs_T`
- `obs_PS`
- `obs_QV`
- `obs_Z`
- `daily_file`
- `lon1`
- `lon2`
- `lat1`
- `lat2`
- `obs_time`
- `include_specific_humidity`
- `include_relative_humidity`
- `include_dewpoint`
- `include_surface_pressure`

`create_real_obs` converts NCEP's intermediate ASCII/PREPQC obs (the output of the `prep_bufr`
decoder below) into a DART `obs_seq` file — the ADPUPA/AIRCFT/SFCSHP/etc. flags select which
NCEP observation categories to include.

### `&prep_bufr_nml`
Source: `NCEP/prep_bufr/src/prepbufr.f` · Doc: `prep_bufr.rst` · In: `work` only

- `obs_window`
- `obs_window_upa`
- `obs_window_air`
- `obs_window_sfc`
- `obs_window_cw`
- `otype_use`
- `qctype_use`
- `land_temp_error`
- `land_wind_error`
- `land_moist_error`

This is a fixed-form Fortran (`.f`, not `.f90`) program under `prep_bufr/src/`, built from a
vendored copy of NCEP's BUFRLIB — it decodes raw BUFR prepbufr files into the intermediate
ASCII format `create_real_obs` reads. `otype_use`/`qctype_use` select observation types (by
NCEP PREPBUFR report type code) and quality-control flags to keep.

### `&convert_cosmic_gps_nml`
Source: `gps/convert_cosmic_gps_cdf.f90` · Doc: documented in `gps/gps.rst` (no dedicated
`convert_cosmic_gps_cdf.rst`) · In: `work`, `template`, `template_nest`

- `obs_levels`
- `local_operator`
- `ray_ds`
- `ray_htop`
- `gpsro_netcdf_file`
- `gpsro_netcdf_filelist`
- `gpsro_out_file`
- `use_original_kuo_error`

Converts COSMIC (and similar) GPS radio-occultation profiles (netCDF) into `obs_seq` — separate
from `&obs_def_gps_nml` below, which only controls the runtime forward operator, not the
conversion step.

## Obs forward operators (`observations/forward_operators/`)

### `&obs_def_gps_nml`
Source: `obs_def_gps_mod.f90` · Doc: `obs_def_gps_mod.rst` · In: `work`, `template`, `template_nest`

- `max_gpsro_obs`

### `&obs_def_radar_mod_nml`
Source: `obs_def_radar_mod.f90` · Doc: `obs_def_radar_mod.rst` · In: `work`, `template`, `template_nest`

- `apply_ref_limit_to_obs`
- `reflectivity_limit_obs`
- `lowest_reflectivity_obs`
- `apply_ref_limit_to_fwd_op`
- `reflectivity_limit_fwd_op`
- `lowest_reflectivity_fwd_op`
- `max_radial_vel_obs`
- `allow_wet_graupel`
- `dielectric_factor`
- `microphysics_type`
- `allow_dbztowt_conv`
- `n0_rain`
- `n0_graupel`
- `n0_snow`
- `rho_rain`
- `rho_graupel`
- `rho_snow`

### `&obs_def_tpw_nml`
Source: `obs_def_tpw_mod.f90` · Doc: **none** (source only) · In: `work` only

- `model_levels`
- `pressure_top`
- `separate_surface_level`
- `num_pressure_intervals`

Note: `obs_def_mod.f90` (the file `preprocess` generates, referenced by
`output_obs_def_mod_file`) `#include`s whichever forward-operator modules are listed in
`obs_type_files`; for this project's `work/input.nml` that pulls in `obs_def_radar_mod.f90` and
`obs_def_gps_mod.f90` (their `namelist` statements literally appear a second time, verbatim,
inside the generated `obs_def_mod.f90`) but **not** `obs_def_tpw_mod.f90` — `tpw` isn't in the
current `obs_type_files` list, which is presumably why `&obs_def_tpw_nml` has no effect even
though the block is still sitting in `work/input.nml`.

## Blocks intentionally left out (already known, or out of this project's scope)

- **`&wrf_dart_to_fields_nml`** — appears in all three input.nml/template files but has no
  source anywhere in the current DART tree (no `.f90` declares it, no `.rst` documents it).
  Fully orphaned; safe to ignore.
- **`&assim_model_nml`** — appears in `template`/`template_nest` only (not `work`). Its only
  source in the entire DART tree is `models/MITgcm_annulus/*.f90` — an unrelated model this
  project never builds. Legacy tutorial leftover, not something this project's build reads.
- Every other model's `&model_nml` (CAM, FV3, POP, MPAS, ROMS, ...), the other five location
  modules' `&location_nml`, and the obs_def forward operators for instruments this project
  doesn't ingest (RTTOV radiances, GRACE, ocean color, TES, tower flux, oxygen ion density) —
  excluded per Scope above.
