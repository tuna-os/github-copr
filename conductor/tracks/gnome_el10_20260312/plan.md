# Implementation Plan: GNOME on EL10

## Phase 1: Preparation and Environment Setup

- [x] **Task: Verify Environment** f33b4f6
  - [ ] Check if `copr-cli` is installed and functional.
  - [ ] Verify access to the source Copr repository: `jreilly1821/c10s-gnome-49`.
- [ ] **Task: Setup Storage Structure**
  - [ ] Create a dedicated subdirectory in `src/` for GNOME 49 sources if necessary.
- [ ] **Task: Conductor - User Manual Verification 'Phase 1: Preparation and Environment Setup' (Protocol in workflow.md)**

## Phase 2: Source Acquisition

- [ ] **Task: Identify All Packages in Copr**
  - [ ] Use `copr-cli` to list all packages in `jreilly1821/c10s-gnome-49`.
  - [ ] Create a local manifest of these packages.
- [ ] **Task: Download Sources**
  - [ ] Script the download of SRPMs or source archives for each package.
  - [ ] Verify the integrity of the downloaded sources.
- [ ] **Task: Extract SPEC Files**
  - [ ] Extract SPEC files from the downloaded SRPMs for local build management.
- [ ] **Task: Conductor - User Manual Verification 'Phase 2: Source Acquisition' (Protocol in workflow.md)**

## Phase 3: Integration and Build Testing

- [ ] **Task: Initial Build Test**
  - [ ] Attempt to build a core GNOME package using the existing `scripts/build-local.sh`.
  - [ ] Troubleshoot any build dependency issues.
- [ ] **Task: Conductor - User Manual Verification 'Phase 3: Integration and Build Testing' (Protocol in workflow.md)**
