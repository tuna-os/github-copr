# AGENTS.md - GNOME 50 Bootstrap on CentOS 10 (EL10)

## Overview
The goal is to bootstrap GNOME 50 on CentOS Stream 10. Since EL10 is currently in development and GNOME 50 is cutting-edge (Fedora 42/43 territory), many dependencies are missing or outdated in the official repos.

## Build Environment
- **Host OS:** Linux
- **Chroot Engine:** `mock`
- **Configuration:** `mock/centos-stream-10-local.cfg`
- **Local Repository:** `mock/repo/`
  - All successfully built RPMs are added here.
  - This repo is prioritized in the mock config to break circular dependencies.

## End Goal
A functional GNOME 50 environment on EL10, verified by building:
1. `mutter` (The compositor)
2. `gnome-shell` (The shell)
3. `gnome-session` (The session manager)
4. `gdm` (The display manager)

## Current Status (2026-03-12)
**Status:** Stuck on `gtk4` (4.17.5) build.
**Roadblock:** Path mismatch for `gio-querymodules`.
- **Error:** `meson.build:979:8: ERROR: Dependency 'gio-2.0' tool variable 'gio_querymodules' contains erroneous value: '/usr/bin/gio-querymodules'`
- **Cause:** EL10 installs this binary as `/usr/bin/gio-querymodules-64`. Upstream `gio-2.0.pc` and Meson expect the standard name.
- **Attempted Fixes:**
  - Patched `glib2.spec` to `sed` the `.pc` file during `%install`.
  - Manually created symlinks in the chroot.
  - Set `GIO_QUERYMODULES` environment variable in manual Meson calls.

## Package-Specific Workarounds (The "Dirty" Log)
To get the bootstrap moving, we have cut corners. These MUST be revisited after the initial bootstrap:

### 1. `glib2`
- **Workarounds:**
  - Removed `BuildSystem: meson` (unsupported by EL10 rpmbuild).
  - Manually expanded `%meson` macros.
  - Disabled `frexp` float check (known EL10 compilation quirk).
  - Forcefully renamed `gio-querymodules` to `-64` and tried to patch `.pc` file.

### 2. `glycin`
- **Workarounds:**
  - Switched to a strictly offline Rust build using a manual `vendor.tar.xz`.
  - Removed `tests` from `Cargo.toml` to reduce dependency bloat.
  - Stripped `Obsoletes: gdk-pixbuf2 < 2.43.5-1` to avoid repository-wide transaction conflicts with system libs.

### 3. `mozjs140` / `gjs`
- **Workarounds:**
  - Built a standalone `libicu77` (bootstrap version) to satisfy `mozjs140` without breaking the system `libicu74`.

### 4. `fontconfig` & `pango`
- **Workarounds:**
  - Stripped `docbook-utils` and man pages to bypass complex documentation toolchain issues.
  - Used very broad wildcards in `%files` to capture generated files quickly.
  - Explicitly disabled subproject bundling (especially `fontconfig` inside `pango`).

### 5. `pipewire` (1.6.1)
- **Workarounds:**
  - Bumped version from 1.4.x to 1.6.1 using CentOS Stream 10 spec as a base.
  - Disabled `ldac`, `spandsp`, and `bluez5-codec-ldac` to avoid missing optional dependencies.

## Command Playbook

### Update Local Repository
Whenever a package builds successfully:
```bash
cp /tmp/results/*.rpm mock/repo/
createrepo_c mock/repo/
```

### Run a Mock Build
```bash
mock -r $(pwd)/mock/centos-stream-10-local.cfg --rebuild path/to/srpm
```

### Install missing deps into chroot (Force)
```bash
mock -r $(pwd)/mock/centos-stream-10-local.cfg --dnf-cmd install -y <package>-devel
```

### Enter Chroot for Debugging
```bash
mock -r $(pwd)/mock/centos-stream-10-local.cfg --shell
```

## Immediate Next Steps
1. Resolve the `gio-querymodules` mismatch in `gtk4`.
2. Re-verify `mutter` build requirements now that `glycin-devel` is properly in the loop.
3. Begin building `gnome-shell` and its JavaScript dependencies.
