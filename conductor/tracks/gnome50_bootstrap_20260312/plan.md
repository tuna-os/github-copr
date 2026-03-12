# Implementation Plan: GNOME 50 Bootstrap on CentOS 10

## Phase 1: Specification and Dependency Mapping [checkpoint: 4477886]

- [x] **Task: Fetch GNOME 50 Specs from Rawhide** 72125f9
  - [ ] Use `fedpkg` to clone the latest specifications for GNOME 50 packages.
  - [ ] Organize specifications in `src/gnome-50/`.
- [x] **Task: Fetch GDM and GNOME Session Specs** 62f447e
  - [ ] Fetch latest `gdm` and `gnome-session` specs from Rawhide.
- [x] **Task: Tooling Assessment (Meson)** 6423360
  - [x] Check if `meson` upgrade is required by the new specs (e.g., `BuildSystem: meson`).
  - [ ] Build and install newer `meson` if needed.
- [x] **Task: Core Component Dependency Analysis** fe60c3a
  - [x] Run `mock --buildsrpm` for `gnome-shell`, `gnome-session`, and `gdm`.
  - [x] Identify minimum set of Rawhide dependencies demanded by these packages.
- [x] **Task: Conductor - User Manual Verification 'Phase 1: Specification and Dependency Mapping' (Protocol in workflow.md)** 4477886

## Phase 2: Iterative Dependency Fulfillment & Container Testing

- [ ] **Task: Build Demanded Dependencies**
  - [ ] Build `glib2`, `gobject-introspection`, and `gjs` if demanded versions exceed EL10.
  - [ ] Update build environment local repository.
- [ ] **Task: Build Core GNOME 50 Priority Packages**
  - [ ] Iteratively build `gnome-shell`, `gnome-session`, and `gdm`.
  - [ ] Patch specs only where strictly necessary for EL10 compatibility.
- [ ] **Task: Iterative Container Installation Test**
  - [ ] Attempt to install `gdm`, `gnome-session`, and `gnome-shell` in a CentOS 10 container.
- [ ] **Task: Conductor - User Manual Verification 'Phase 2: Iterative Dependency Fulfillment & Container Testing' (Protocol in workflow.md)**

## Phase 3: Core GNOME Build & Integration

- [ ] **Task: Final Core GNOME Build**
  - [ ] Successfully build all core components.
- [ ] **Task: Conductor - User Manual Verification 'Phase 3: Core GNOME Build & Integration' (Protocol in workflow.md)**

## Phase 4: VM Validation

- [ ] **Task: Setup CentOS 10 VM**
- [ ] **Task: Install GNOME 50 from Repository**
- [ ] **Task: Conductor - User Manual Verification 'Phase 4: VM Validation' (Protocol in workflow.md)**
