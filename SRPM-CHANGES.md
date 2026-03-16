# Local SRPM Modification Changelog

This document tracks all manual modifications made to SRPM specifications and sources to enable GNOME 50 on CentOS Stream 10.

## 1. Custom GNOME 50 Compatibility Packages

### `gnome50-el10-compat`
*   **Origin**: New package.
*   **Purpose**: Restores upstream `systemd-user` PAM behavior to fix dynamic GDM greeter user authentication.
*   **Modifications**:
    *   Created `systemd-user.pam` with `account required pam_permit.so`.
    *   Spec file provides override at `/etc/pam.d/systemd-user`.

## 2. Modified Rawhide Backports

### `gi-docgen`
*   **Origin**: Backport from Rawhide.
*   **Modifications**:
    *   Patched spec to remove `BuildSystem: pyproject` (unsupported on EL10).
    *   Fixed `%autosetup` directory name mismatch (`gi_docgen` vs `gi-docgen`).
    *   Switched to local SRPM build in COPR.

### `gnome-user-share`
*   **Origin**: Backport from Rawhide.
*   **Modifications**:
    *   Generated and added a **vendor tarball** (`gnome-user-share-48.1-vendor.tar.xz`) to bypass missing Rust crate dependencies in EL10 repositories.
    *   Patched spec to use the vendor tarball and configure offline cargo build.
    *   Added `BuildRequires: pkgconfig(glib-2.0)` which was missing in the Rawhide spec.

### `gdm`
*   **Origin**: Backport from Rawhide.
*   **Modifications**:
    *   Added `Requires: gnome50-el10-compat` to ensure the PAM workaround is automatically installed during a GNOME 50 upgrade.

### `glib2`
*   **Origin**: Backport from Rawhide.
*   **Modifications**:
    *   Retained EL10-specific schema compilation triggers and `gio` module query triggers.

## 3. Version Overrides / Forced Backports
*The following were built as local SRPMs to resolve dependency conflicts or provide newer versions than what COPR's `distgit` fetcher was pulling.*

*   **`libgexiv2`**: Backported to version 0.16.0 to resolve Nautilus dependencies.
*   **`pango` (GNOME 49)**: Added `BuildRequires: python3-setuptools` to fix `ModuleNotFoundError: No module named distutils` in `g-ir-scanner` during build. Bumped release to 2.
*   **`tinysparql` (GNOME 49)**: Added `BuildRequires: python3-setuptools` to fix `ModuleNotFoundError: No module named distutils` in `g-ir-scanner` during build. Bumped release to 2.
*   **`libgexiv2` (GNOME 49)**: Added `BuildRequires: python3-setuptools` to fix `ModuleNotFoundError: No module named distutils` in `g-ir-scanner` during build. Bumped release to 3.
*   **`libcloudproviders` (GNOME 49)**: Added `BuildRequires: python3-setuptools` to fix `ModuleNotFoundError: No module named distutils` in `g-ir-scanner` during build. Bumped release to 3.
*   **`tinysparql`**: Backported to version 3.11~rc to resolve GNOME 50 dependencies.
*   **`localsearch`**: Backported to version 3.11~rc to resolve GNOME 50 dependencies.
*   **`libical`**: Rebuilt against ICU 77 to fix `evolution-data-server` dependency chain.
*   **`evolution-data-server`**: Rebuilt against ICU 77.
*   **`libebur128`**: Backported from Rawhide (dependency for Pipewire 1.6).
*   **`libzip`**: Backported from Rawhide (dependency for Localsearch).
*   **`glycin`**: Built from local SRPM to resolve `gdk-pixbuf2` obsolescence conflicts in Rawhide spec.
