#!/usr/bin/env python3
"""Record the pinned commits, local patches, compiler/library versions and
executable checksums for the project's WRF/WPS/WRFDA/DART builds into
software_lock.json.

This only audits software that has actually been built under SOFTWARE_ROOT;
it does not build, download or modify anything. Rerun it after any rebuild,
patch, or module-version change so software_lock.json stays truthful.

Usage (from the project root, after `uv sync` has created .venv once):
    source scripts/env_wrf.sh   # so module_environment() resolves real versions
    uv run python3 scripts/audit_configuration.py
"""

import datetime
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOFTWARE_ROOT = Path("/gpfs/wolf2/arm/cli120/proj-shared/hengxiao80/software")
PATCHES_DIR = PROJECT_ROOT / "patches"
ENV_SCRIPT = PROJECT_ROOT / "scripts" / "env_wrf.sh"

# Executables expected for each component, as paths relative to that
# component's checkout root. A missing file is recorded as such, not silently
# skipped, per the plan's requirement that "all executable/version records
# are complete."
EXPECTED_EXECUTABLES = {
    "WRF": [
        "main/real.exe",
        "main/wrf.exe",
        "main/ndown.exe",
        "main/tc.exe",
    ],
    "WPS": [
        "geogrid.exe",
        "ungrib.exe",
        "metgrid.exe",
    ],
    "WRFDA": [
        "var/build/da_wrfvar.exe",
    ],
    "DART": [
        "models/wrf/work/filter",
        "models/wrf/work/model_mod_check",
        "models/wrf/work/perfect_model_obs",
        "models/wrf/work/closest_member_tool",
        "models/wrf/work/perturb_single_instance",
        "models/wrf/work/wakeup_filter",
        "models/wrf/work/advance_time",
        "models/wrf/work/create_fixed_network_seq",
        "models/wrf/work/create_obs_sequence",
        "models/wrf/work/fill_inflation_restart",
        "models/wrf/work/obs_diag",
        "models/wrf/work/obs_selection",
        "models/wrf/work/obs_seq_coverage",
        "models/wrf/work/obs_seq_to_netcdf",
        "models/wrf/work/obs_seq_verify",
        "models/wrf/work/obs_sequence_tool",
        "models/wrf/work/obs_common_subset",
        # These are built from source under WRF_DART_utilities/ and WRF_BC/,
        # but quickbuild.sh symlinks every model_serial_programs output flat
        # into work/ by basename (confirmed by inspection), same as WRFDA's
        # own obsproc.exe -> src/obsproc.exe pattern.
        "models/wrf/work/add_pert_where_high_refl",
        "models/wrf/work/advance_cymdh",
        "models/wrf/work/convertdate",
        "models/wrf/work/ensemble_init",
        "models/wrf/work/pert_wrf_bc",
        "models/wrf/work/replace_wrf_fields",
        "models/wrf/work/select",
        "models/wrf/work/update_wrf_bc",
        "models/wrf/work/wrf_dart_obs_preprocess",
        "models/wrf/work/extract",
        "models/wrf/work/grid_refl_obs",
    ],
}

# configure.wrf/configure.wps keys worth recording verbatim for each
# component, when that file exists. Absent keys are simply omitted.
CONFIGURE_KEYS = {
    "WRF": ["SFC", "SCC", "DM_FC", "RWORDSIZE", "DMPARALLEL", "OMP", "WRF_CHEM"],
    "WRFDA": ["SFC", "SCC", "DM_FC", "RWORDSIZE", "DMPARALLEL", "OMP"],
    "WPS": ["SFC", "SCC", "DM_FC", "LDFLAGS"],
}


def run(cmd, cwd=None):
    try:
        out = subprocess.run(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
        )
        return out.stdout.strip()
    except FileNotFoundError:
        return None


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def file_kind(path):
    out = run(["file", "-b", str(path)])
    return out if out else None


def git_info(repo_dir):
    if not (repo_dir / ".git").exists():
        return None
    commit = run(["git", "rev-parse", "HEAD"], cwd=repo_dir)
    remote = run(["git", "remote", "get-url", "origin"], cwd=repo_dir)
    dirty = run(["git", "status", "--porcelain"], cwd=repo_dir)
    submodules = []
    status_out = run(["git", "submodule", "status", "--recursive"], cwd=repo_dir)
    if status_out:
        for line in status_out.splitlines():
            # Leading '+' means checked-out commit differs from what the
            # superproject records (e.g. we edited a submodule file in
            # place); leading '-' means not initialized.
            m = re.match(r"^([ +\-U])([0-9a-f]{40})\s+(\S+)", line)
            if m:
                submodules.append(
                    {
                        "path": m.group(3),
                        "commit": m.group(2),
                        "flag": {
                            " ": "clean",
                            "+": "checked_out_differs_from_recorded",
                            "-": "not_initialized",
                            "U": "merge_conflict",
                        }.get(m.group(1), m.group(1)),
                    }
                )
    return {
        "remote": remote or None,
        "commit": commit or None,
        "working_tree_dirty": bool(dirty),
        "dirty_files": dirty.splitlines() if dirty else [],
        "submodules": submodules,
    }


def configure_settings(component_dir, keys):
    for name in ("configure.wrf", "configure.wps"):
        cfg = component_dir / name
        if cfg.exists():
            text = cfg.read_text(errors="replace")
            found = {}
            for key in keys:
                m = re.search(r"^%s\s*=\s*(.*)$" % re.escape(key), text, re.MULTILINE)
                if m:
                    found[key] = m.group(1).strip()
            return {"source_file": name, "settings": found}
    return None


def audit_executables(component_dir, rel_paths):
    results = []
    for rel in rel_paths:
        full = component_dir / rel
        entry = {"path": rel}
        if full.is_symlink() and not full.exists():
            entry["status"] = "dangling_symlink"
        elif not full.exists():
            entry["status"] = "missing"
        else:
            entry["status"] = "present"
            entry["is_symlink"] = full.is_symlink()
            resolved = full.resolve()
            entry["resolved_path"] = str(resolved)
            entry["size_bytes"] = resolved.stat().st_size
            entry["mtime_utc"] = datetime.datetime.utcfromtimestamp(
                resolved.stat().st_mtime
            ).isoformat() + "Z"
            entry["sha256"] = sha256_of(resolved)
            entry["file_type"] = file_kind(resolved)
        results.append(entry)
    return results


def patch_inventory():
    if not PATCHES_DIR.exists():
        return []
    patches = []
    for p in sorted(PATCHES_DIR.glob("*")):
        if p.is_file() and p.name != "README.md":
            patches.append(
                {
                    "file": p.name,
                    "sha256": sha256_of(p),
                    "size_bytes": p.stat().st_size,
                }
            )
    return patches


def module_environment():
    if not ENV_SCRIPT.exists():
        return None
    lines = [
        l.strip()
        for l in ENV_SCRIPT.read_text().splitlines()
        if l.strip().startswith("module load")
    ]
    modules = [l.replace("module load", "").strip() for l in lines]
    # Resolve each module's actual target with `module show`, which prints
    # the real installed path/version even when the module name itself
    # (e.g. "hdf5") carries no explicit version.
    resolved = {}
    for mod in modules:
        show = subprocess.run(
            ["bash", "-lc", "module show %s" % mod],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )
        first_line = None
        for l in (show.stdout + show.stderr).splitlines():
            if l.strip().endswith(".lua:") or l.strip().endswith(":"):
                if "/" in l:
                    first_line = l.strip().strip("-: ")
                    break
        resolved[mod] = first_line
    return {
        "env_script": str(ENV_SCRIPT.relative_to(PROJECT_ROOT)),
        "modules_loaded": modules,
        "modules_resolved": resolved,
    }


def host_info():
    return {
        "hostname": run(["hostname"]),
        "uname": run(["uname", "-a"]),
        "generated_at_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "generated_by": "audit_configuration.py",
    }


def main():
    record = {"host": host_info(), "modules": module_environment(), "software": {}}

    for component in ("WRF", "WPS", "WRFDA", "DART"):
        comp_dir = SOFTWARE_ROOT / component
        if not comp_dir.exists():
            record["software"][component] = {"status": "not_built"}
            continue
        entry = {
            "path": str(comp_dir),
            "git": git_info(comp_dir),
            "configure": configure_settings(comp_dir, CONFIGURE_KEYS.get(component, [])),
            "executables": audit_executables(
                comp_dir, EXPECTED_EXECUTABLES.get(component, [])
            ),
        }
        record["software"][component] = entry

    record["local_patches"] = patch_inventory()

    missing = []
    for component, entry in record["software"].items():
        for exe in entry.get("executables", []):
            if exe["status"] != "present":
                missing.append("%s/%s (%s)" % (component, exe["path"], exe["status"]))
    record["incomplete_executables"] = missing

    out_path = PROJECT_ROOT / "software_lock.json"
    out_path.write_text(json.dumps(record, indent=2, sort_keys=False) + "\n")

    print("Wrote %s" % out_path)
    if missing:
        print("WARNING: incomplete/missing executables:")
        for m in missing:
            print("  - %s" % m)
        return 1
    print("All expected executables present and hashed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
