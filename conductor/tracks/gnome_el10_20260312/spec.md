# Track Specification: GNOME on EL10

## Overview
This track involves pulling down RPM SPEC files and source packages from an existing Copr repository (`jreilly1821/c10s-gnome-49`) to host them in our system and provide GNOME 49 for Enterprise Linux 10 (EL10).

## Objectives
- Integrate `copr-cli` or similar tools to fetch package sources from the specified Copr repository.
- Store the fetched sources in our repository structure (`src/`).
- Enable local building and hosting of these packages.

## Requirements
- `copr-cli` installed and configured.
- Access to the target Copr repository.
- Storage capacity in the `src/` directory for multiple package sources.

## Constraints
- Must maintain the integrity of the original source packages.
- Need to handle a large number of packages potentially.
