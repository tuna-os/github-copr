# TunaOS Packages

`tunaos-packages` is the GitHub-hosted package factory for TunaOS. It replaces
runtime COPR/PPA dependencies with source-controlled, tested packages published
to TunaOS repositories. GitHub Actions builds and tests; Cloudflare R2 serves
the resulting rpm-md/APT/Pacman repositories. ORAS is reserved for immutable
source, SBOM, and provenance bundles—not live package-manager endpoints.

## Status

| Target | Format | Status |
| --- | --- | --- |
| EL10 | RPM / rpm-md | Active production pipeline |
| Ubuntu Resolute | DEB / APT | Native packaging foundation |
| Debian Trixie | DEB / APT | Native packaging foundation |
| openSUSE Tumbleweed | RPM / rpm-md | Build scaffold |
| Arch | pkg.tar.zst / Pacman | Build scaffold |

The target contract and repository paths live in
[`manifests/package-factory.yaml`](manifests/package-factory.yaml).

## How it works

```text
upstream source + pinned checksum
        ↓
native spec/control/PKGBUILD (or experimental Tideforge recipe)
        ↓
GitHub Actions target build → staged repository install → desktop smoke test
        ↓
sign + publish only after every gate passes
```

TunaOS consumes only its staged or promoted repositories. An upstream COPR,
PPA, or image filesystem is never a runtime package source.

## Package classes

- `src/gnome-50/` and `src/deps/` contain the established native EL10 RPM
  pipeline. GNOME 50's bootstrap cycle and `gnome50-el10-compat` remain native
  RPM work because they use patches, scriptlets, file triggers, SELinux policy,
  and EL10-specific dependency workarounds.
- `src/xfce-wayland/` is the native XFCE/XFWL4 build chain.
- `packages/<name>/package.yaml` is the experimental Tideforge single-recipe
  path. It currently validates source pins and renders native RPM/DEB metadata;
  it is not a promotion path until build/install/runtime parity is proven.

## Desktop queues

Dependency trees describe source order. Target queues describe native packaging
and release gates for each distro:

- [`GNOME`](manifests/dependency-trees/gnome.yaml) / [target queues](manifests/target-queues/gnome.yaml)
- [`Niri + DMS`](manifests/dependency-trees/niri.yaml) / [target queues](manifests/target-queues/niri.yaml)
- [`XFCE + XFWL4`](manifests/dependency-trees/xfce.yaml) / [target queues](manifests/target-queues/xfce.yaml)
- [`COSMIC`](manifests/dependency-trees/cosmic.yaml)
- [`Aurora KDE`](manifests/dependency-trees/kde.yaml)

Queues are intentionally target-native. For example, latest GNOME on Debian
gets Debian packages; it does not inherit EL10's SELinux/PAM compatibility
package or RPM triggers.

## Add a package

1. Add it to the appropriate dependency tree and target queue.
2. Prefer an existing distro package. Otherwise import source with an upstream
   revision/tag, license review, and SHA-256.
3. For a straightforward project, copy `packages/_template/package.yaml`.
   Keep genuinely different dependency names in target overrides.
4. For EL10 backports requiring patches, RPM scriptlets, triggers, SELinux, or
   bootstrap ordering, add/maintain a native spec under `src/` instead.
5. Add build, staged-install, and session/runtime gates before promotion.

Useful local checks:

```bash
python3 scripts/validate-package-factory.py manifests/package-factory.yaml
python3 scripts/tideforge.py validate packages/niri/package.yaml
python3 scripts/verify-tideforge-source.py packages/niri/package.yaml
python3 -m pytest tests/ -q
```

## Stable source updates

`Bump Stable Package Sources` runs weekly. It tracks the latest non-prerelease
GitHub release, updates a recipe's version/source/checksum atomically, and
opens a PR. It never publishes directly: normal build, staged-install, and
desktop gates still control release.

## Promotion policy

An artifact can reach a stable TunaOS repository only after it:

1. verifies its source checksum;
2. builds in the declared native target;
3. installs from a staged repository;
4. passes relevant desktop/session checks; and
5. is signed and promoted by CI.

See [`docs/PACKAGE_FACTORY.md`](docs/PACKAGE_FACTORY.md) for the detailed
contract and [`docs/UPSTREAM_PARITY.md`](docs/UPSTREAM_PARITY.md) for the
Bluefin, Aurora, and Zirconium parity inventory.
