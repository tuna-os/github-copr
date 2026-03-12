# Track Specification: GNOME on EL10

## Overview
This track involves setting up the build pipeline for GNOME 49 (or latest) on Enterprise Linux 10 (EL10). The strategy is to pull the latest `.spec` files from Fedora Rawhide using `fedpkg` and build the packages using upstream GNOME tarballs.

## Objectives
- Integrate `fedpkg` to fetch the latest RPM specifications from Fedora Rawhide.
- Configure the build system to use upstream GNOME source tarballs.
- Target Enterprise Linux 10 (EL10) for all builds.
- Store specifications in `src/gnome-49/`.

## Requirements
- `fedpkg` and `mock` installed and configured.
- Access to Fedora Dist-Git.
- Infrastructure to fetch and verify upstream GNOME tarballs.

## Constraints
- Must align Rawhide specifications with EL10 dependencies.
- Ensure GPG signing for all generated RPMs.
