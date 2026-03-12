# Implementation Plan: GNOME on EL10

## Phase 1: Preparation and Environment Setup [checkpoint: a65ef4c]

- [x] **Task: Verify Environment** f33b4f6
  - [x] Check if `copr-cli` is installed and functional.
  - [x] Verify access to the source Copr repository: `jreilly1821/c10s-gnome-49`.
- [x] **Task: Setup Storage Structure** a50d066
  - [x] Create a dedicated subdirectory in `src/` for GNOME 49 sources if necessary.
- [x] **Task: Conductor - User Manual Verification 'Phase 1: Preparation and Environment Setup' (Protocol in workflow.md)** a65ef4c

## Phase 2: Dist-Git Integration and Specification Fetching

- [x] **Task: Verify `fedpkg` and Dist-Git Access** 1122da5
  - [ ] Install `fedpkg` if missing.
  - [ ] Test cloning a package from Fedora Dist-Git.
- [x] **Task: Script Specification Pulling from Rawhide** e878169
  - [ ] Use `fedpkg` to fetch the latest SPEC files for GNOME packages from Rawhide.
  - [ ] Store SPEC files in `src/gnome-49/`.
- [x] **Task: Identify Upstream Source Tarballs** 5ab8729
  - [ ] Parse SPEC files to find upstream source URLs.
  - [ ] Create a manifest for downloading GNOME tarballs.
- [ ] **Task: Conductor - User Manual Verification 'Phase 2: Dist-Git Integration and Specification Fetching' (Protocol in workflow.md)**

## Phase 3: Build Pipeline and EL10 Integration

- [ ] **Task: Mock Configuration for EL10**
  - [ ] Configure `mock` for EL10 targets (e.g., `centos-stream-10-x86_64`).
- [ ] **Task: Fetch and Build from Upstream Tarballs**
  - [ ] Create a script to download upstream tarballs into the build environment.
  - [ ] Perform a test build for a core GNOME package using Rawhide SPEC + Upstream Tarball.
- [ ] **Task: Conductor - User Manual Verification 'Phase 3: Build Pipeline and EL10 Integration' (Protocol in workflow.md)**
