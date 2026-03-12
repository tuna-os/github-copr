# Track Specification: GNOME 50 Bootstrap on CentOS 10

## Overview
This track focuses on the full lifecycle of bringing GNOME 50 to CentOS 10. This includes pulling the latest specifications from Fedora Rawhide, identifying and building missing dependencies, and finally validating the result on a fresh VM.

## Objectives
- **Specification Acquisition**: Fetch GNOME 50 SPEC files from Fedora Rawhide via `fedpkg`.
- **Iterative Build & Dependency Resolution**: Perform local mock builds for CentOS 10, identifying and fulfilling missing dependencies by adding them to the repository.
- **SPEC Patching**: Update SPEC files to fix build failures unrelated to dependencies (e.g., path changes, macro fixes).
- **VM Validation**: Deploy and test the resulting packages on a CentOS 10 virtual machine.

## Requirements
- `fedpkg` and `mock` correctly configured for CentOS 10 targets.
- Access to Fedora Dist-Git.
- A virtual machine environment for final installation testing.

## Constraints
- Must maintain a clean build history for each package.
- All new dependencies added must also have their specifications stored in `src/`.
