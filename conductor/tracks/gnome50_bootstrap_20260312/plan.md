# Implementation Plan: GNOME 50 Bootstrap on CentOS 10

## Phase 1: Specification and Dependency Mapping

- [x] **Task: Fetch GNOME 50 Specs from Rawhide** 72125f9
  - [ ] Use `fedpkg` to clone the latest specifications for GNOME 50 packages.
  - [ ] Organize specifications in `src/gnome-50/`.
- [x] **Task: Initial Mock Builds & Dependency Analysis** ae48379
  - [ ] Run `mock --buildsrpm` for core GNOME 50 packages (e.g., `xdg-desktop-portal`).
  - [ ] Parse `mock` logs to identify missing dependencies.
- [ ] **Task: Conductor - User Manual Verification 'Phase 1: Specification and Dependency Mapping' (Protocol in workflow.md)**

## Phase 2: Iterative Dependency Fulfillment & Container Testing

- [ ] **Task: Build Missing Dependencies**
  - [ ] Fetch specs for missing dependencies from Fedora.
  - [ ] Build and add these dependencies to the repository.
  - [ ] Update build environment to include newly built packages.
- [ ] **Task: Update & Patch SPEC Files**
  - [ ] If builds fail for reasons other than missing dependencies, apply necessary patches to SPEC files.
- [ ] **Task: Iterative Container Installation Test**
  - [ ] Create a Docker/Podman container based on CentOS 10.
  - [ ] Attempt to install the newly built GNOME 50 packages in the container to verify dependency resolution.
  - [ ] Resolve any installation-time dependency conflicts.
- [ ] **Task: Conductor - User Manual Verification 'Phase 2: Iterative Dependency Fulfillment & Container Testing' (Protocol in workflow.md)**

## Phase 3: Core GNOME Build & Integration

- [ ] **Task: Build Core GNOME 50 Packages**
  - [ ] Successfully build all core components (Mutter, Shell, Control Center, etc.).
  - [ ] Verify metadata generation and repository indexing.
- [ ] **Task: Conductor - User Manual Verification 'Phase 3: Core GNOME Build & Integration' (Protocol in workflow.md)**

## Phase 4: VM Validation

- [ ] **Task: Setup CentOS 10 VM**
  - [ ] Install a fresh CentOS 10 instance on a VM.
- [ ] **Task: Install GNOME 50 from Repository**
  - [ ] Configure the VM to use our repository proxy.
  - [ ] Install and launch GNOME 50.
  - [ ] Verify core functionality (UI, networking, basic apps).
- [ ] **Task: Conductor - User Manual Verification 'Phase 4: VM Validation' (Protocol in workflow.md)**
