# TunaOS Package Factory

This repository is the source-controlled package factory for TunaOS. It builds
and signs packages in GitHub Actions, tests them against declared distro
targets, and publishes only validated repositories to Cloudflare R2.

## Supported targets

| Target | Format | Repository | Status |
|---|---|---|---|
| EL10 | RPM | rpm-md | supported |
| Ubuntu | DEB | APT | supported foundation |
| Debian Sid | DEB | APT | supported foundation |
| openSUSE Tumbleweed | RPM | rpm-md | scaffold |
| Arch | pkg.tar.zst | pacman | scaffold |

The authoritative target and R2-path contract is
[`manifests/package-factory.yaml`](../manifests/package-factory.yaml).

## Upstream source policy

Bluefin, Aurora, Fedora dist-git, and other upstream projects are inputs for
source and packaging metadata only. Before importing a package, record its
upstream commit/tag, license, patches, and target compatibility. TunaOS rebuilds
the package itself; it never enables an upstream COPR, PPA, or binary repository
in a produced image.

The current Bluefin, Aurora, and Zirconium parity inventory and delivery order
are maintained in [`UPSTREAM_PARITY.md`](UPSTREAM_PARITY.md).

## Promotion contract

Every candidate must build in the target buildroot, pass package tests, install
from the staged repository, and complete a desktop/runtime smoke test where the
package affects a session. Only then may CI sign and promote it to the stable R2
path. ORAS is suitable for immutable source/SBOM/provenance bundles, not as the
live DNF/APT/Pacman endpoint.

## Package layout

New work should use this shape:

```text
packages/<name>/
  source.yaml             # upstream URL, revision, license, checksum
  rpm/<target>/*.spec     # RPM packaging and patches
  debian/                 # Debian packaging
  arch/PKGBUILD           # Arch scaffold when supported
  opensuse/*.spec          # openSUSE scaffold when supported
```

Existing `src/` packages are migrated incrementally; they remain build inputs
until their package directories are moved without changing the published NVR.

## Target-native overlays

Source graphs can be shared, but package metadata and compatibility work cannot.
For example, the GNOME queue in `manifests/target-queues/gnome.yaml` keeps the
EL10 bootstrap/spec and SELinux compatibility overlay native to RPM while
Debian Trixie and Ubuntu render and test DEB packages independently.

## Tideforge: experimental single-recipe workflow

Tideforge is developed in parallel with the established native RPM/DEB
pipelines. Those native pipelines remain the production distribution path until
Tideforge renders equivalent artifacts and passes the same build, install, and
runtime gates.

Use `packages/_template/package.yaml` as the only author-maintained recipe.
`scripts/tideforge.py` validates the recipe, shows its per-target build plan,
and renders native RPM or Debian packaging:

```bash
python3 scripts/tideforge.py validate packages/my-package/package.yaml
python3 scripts/tideforge.py plan packages/my-package/package.yaml --target el10
python3 scripts/tideforge.py render packages/my-package/package.yaml --target ubuntu --output out/ubuntu
```

The tool emits target-native files because the package managers require them,
but maintainers edit one recipe. A target override is limited to the dependency
or build difference that cannot be made portable.
