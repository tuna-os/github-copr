# GNOME 50 Bootstrap on CS10 - Status Report

## Current Status: Implementation Phase (Successes & Blockers)

### 1. Core Infrastructure Successes
*   **COPR Project Established**: `jreilly1821/c10s-gnome-50-fresh` is the active testing ground.
*   **Compatibility Package**: `gnome50-el10-compat` successfully built and integrated. It provides the critical `systemd-user` PAM fix for GDM 50 greeter users.
*   **GDM Integration**: `gdm` has been rebuilt with a hard requirement on `gnome50-el10-compat`.
*   **Successes (Built from Rawhide/Modified)**:
    *   `mutter`, `gnome-shell`, `gnome-session`, `gdm`, `nautilus`, `gtk4`, `glib2`, `selinux-policy`.
    *   **New Backports**: `libgexiv2`, `tinysparql`, `localsearch`, `libical`, `evolution-data-server`, `libebur128`, `libzip`, `lzo`.
    *   **Custom Fixes**: `gi-docgen` (spec patched), `gnome-user-share` (vendored Rust deps).

### 2. Immediate Blockers (Work in Progress)
*   **`glycin` Version Conflict**: COPR's `distgit` builder pulled a version (2.0.8-3) that incorrectly obsoletes `gdk-pixbuf2`, breaking Bluefin/CS10 system integrity. Our local fix (2.0.8-100) is building but hasn't yet overridden the bad version.
*   **Validation**: Full `dnf upgrade` on `bluefin:lts` is 95% there but currently stuck on the `glycin` conflict.

### 3. Documentation
*   **`SRPM-CHANGES.md`**: Tracks all manual spec/source modifications (PAM fixes, Rust vendoring, dependency injections).
*   **`COPR-REPORT.md`**: Categorizes all 40+ packages by origin (Custom vs Modified vs Unmodified Rawhide).
*   **GitHub Issue #1**: Documented the `systemd-user` PAM regression for upstream/community visibility.

## Work Items / TODOs

- [ ] **Force `glycin` Override**: Delete the `distgit` package from COPR if necessary once Build 10224151 finishes, and ensure 2.0.8-100 is the only version served.
- [ ] **Final Container Validation**: Perform a clean `dnf upgrade` on `ghcr.io/ublue-os/bluefin:lts` and verify that `gnome-shell` 50 and `gdm` 50 install alongside the compat package.
- [ ] **VM Testing**: Move from container testing to a full CentOS Stream 10 VM to verify the GDM login flow and SELinux policy enforcement.
- [ ] **Pagure Forking**: Once stable, the local modified specs need to be properly forked into the project's Pagure/Dist-git infrastructure.

## Modified Packages Summary
| Package | Primary Change |
| :--- | :--- |
| `gnome50-el10-compat` | New: PAM `systemd-user` workaround |
| `gdm` | Added `Requires: gnome50-el10-compat` |
| `gnome-user-share` | Vendored Rust crates + added missing `glib2` BR |
| `gi-docgen` | Removed `BuildSystem: pyproject` for EL10 compatibility |
| `glib2` | Retained EL10 schema compilation triggers |
| `glycin` | Modified to prevent `gdk-pixbuf2` obsolescence |
