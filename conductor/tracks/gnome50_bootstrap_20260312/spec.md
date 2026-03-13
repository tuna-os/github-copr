# Track Specification: GNOME 50 Bootstrap on CentOS 10

## Overview
This track focuses on the full lifecycle of bringing GNOME 50 to CentOS 10. This includes pulling the latest specifications from Fedora Rawhide, identifying and building missing dependencies, and finally validating the result on a fresh VM.

## Objectives
- **Specification Acquisition**: Fetch GNOME 50 SPEC files for core packages (`gnome-shell`, `gnome-session`, `gdm`) from Fedora Rawhide. Use CentOS 10 native packages for all other dependencies unless an upgrade is strictly demanded.
- **Priority Components**: `gnome-shell`, `gnome-session`, `gdm`.
- **Iterative Build & Dependency Resolution**: Perform local mock builds for CentOS 10. If a build demands a newer version of a dependency not in EL10, fetch and build that dependency from Fedora.
- **Tooling Upgrades**: Build and provide a newer version of `meson` if required by the new specifications.
- **SPEC Patching**: Update SPEC files to fix build failures unrelated to dependencies (e.g., path changes, macro fixes).
- **VM Validation**: Deploy and test the resulting packages on a CentOS 10 virtual machine.

## Requirements
- `fedpkg` and `mock` correctly configured for CentOS 10 targets.
- Access to Fedora Dist-Git.
- A virtual machine environment for final installation testing.

## Constraints
- Must maintain a clean build history for each package.
- All new dependencies added must also have their specifications stored in `src/`.
