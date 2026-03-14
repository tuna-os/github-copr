# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repo builds and hosts RPM packages for **GNOME 50 on CentOS Stream 10 (EL10)**, using GitHub Actions for CI, Podman/Mock for isolated builds, Cloudflare R2 for storage, and GPG for package signing. It replicates Fedora Copr functionality in a self-hosted setup.

The hosted repo is served at `repo.tunaos.org` (R2 bucket: `bluefin`).

## Key Commands

Local builds require `mock`, `createrepo_c`, `rclone`, and a `.env` file with secrets (see `.env.example`).

```bash
just setup                    # Check dependencies and initialize .env
just check-secrets            # Verify .env has all required secrets
just verify-gpg               # Confirm GPG signing key is available

just build <target>           # Build RPM via mock (e.g. centos-stream-10-x86_64)
just build-and-sign <target>  # Build + GPG sign
just publish <target>         # Build → sign → update metadata → sync to R2

just sign-r2                  # Pull all RPMs from R2, re-sign, push back
just publish-static           # Upload public.gpg and install.sh to R2 root
just clean                    # Remove output/, repodata/, build/

just run-vm iso centos-stream-10   # Launch KVM VM via podman (Web VNC on :8006)
just test-remote root@<ip>         # Deploy and test repo on a remote machine
just rsync-test root@<ip>          # Sync local-repo/ to remote and test upgrade
```

The main build script (used by CI):
```bash
./scripts/build-chain.sh --help    # Tiered build orchestration
```

## Architecture

### Build Pipeline
```
GitHub Actions → build-chain.sh (reads build-order.yml)
  → Tiers executed sequentially; packages within a tier run in parallel
  → Podman container (CentOS Stream 10 image) → rpmbuild
  → GPG sign (rpmsign) → createrepo_c → rclone sync → Cloudflare R2
```

CI seeds the local repo from R2 at the start, adds new builds, re-signs, and pushes back—incremental updates only.

### Key Files

| File | Purpose |
|------|---------|
| `build-order.yml` | Single source of truth: defines ~80 packages across 13+ dependency tiers |
| `scripts/build-chain.sh` | Main build engine; parses build-order.yml; supports podman/mock/native backends |
| `justfile` | Local convenience wrappers (requires `just`) |
| `.github/workflows/build.yml` | Primary CI/CD pipeline |
| `.github/workflows/build-distributed.yml` | Auto-generated per-tier parallel workflow |
| `scripts/generate-distributed-workflow.py` | Regenerates build-distributed.yml from build-order.yml |
| `workers/repo-proxy.ts` | Cloudflare Worker for custom domain routing |
| `contrib/install.sh` | User-facing install script (detects distro/version) |

### Package Sources

- `src/gnome-50/` — GNOME 50 packages (glib2, gtk4, mutter, gnome-shell, gdm, etc.)
- `src/deps/` — Build dependencies not in EL10 repos (meson, mozjs140, pipewire, cairo, etc.)

Each package directory contains a `.spec` file and sources. Some packages have bootstrap variants (e.g., `glib2-bootstrap.spec`, `gobject-introspection-bootstrap.spec`) to break circular dependencies—these build first without certain features, then the full build follows.

### Build Targets

Supported targets: `fedora-43-x86_64`, `almalinux-10-x86_64`, `almalinux-10-x86_64_v2`, `centos-stream-10-x86_64`, and aarch64 variants. The primary target is `centos-stream-10-x86_64`.

### Storage Layout (Cloudflare R2)

```
bluefin/
├── public.gpg           # GPG public key
├── install.sh           # Auto-install script
├── sources/             # Lookaside cache for upstream tarballs
└── repo/
    └── <target>/        # e.g. 10-stream-x86_64/
        ├── *.rpm
        └── repodata/
```

### Required Secrets

`.env` file (local) and GitHub Secrets (CI):
- `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `CLOUDFLARE_ACCOUNT_ID` — R2 access
- `GPG_PRIVATE_KEY`, `GPG_PASSPHRASE` — RPM signing

## Current Status (see AGENTS.md)

As of 2026-03-13, **GNOME 50 is running on the test VM** (libvirt at `192.168.122.135`). GDM greeter and a full user session are functional. The remaining issues are benign VM-specific warnings (software rendering fallback).

### VM: EL10 Runtime Fixes Applied

These workarounds were needed to run GNOME 50 on EL10 and are already applied on the test VM. They need to be packaged properly (e.g., as RPM `%post` scriptlets or a separate compat package):

1. **SELinux policy** (`/etc/selinux/targeted/`): EL10's stock `xdm_t` policy doesn't allow GDM to create its userdb Varlink socket. Two modules installed via `semodule -X 300`:
   - `gdm-gnome50.pp`: Allows `xdm_t` to create/unlink sockets in `systemd_userdbd_runtime_t` dirs, write `passwd_file_t`, create `etc_t` files.
   - `gdm-userdb-connect.pp`: Allows multiple domains (`systemd_userdbd_t`, `chkpwd_t`, etc.) to connect to `xdm_t` unix sockets.

2. **PAM override** (`/etc/pam.d/systemd-user`): `pam_unix.so` calls `unix_chkpwd` which can't resolve GDM's dynamically-allocated greeter users (e.g. `gdm-greeter-N`). The account phase returns `PAM_AUTHINFO_UNAVAIL`. Fix: override with `account required pam_permit.so` for the systemd-user PAM service.

3. **GLib schemas** (`glib-compile-schemas /usr/share/glib-2.0/schemas/`): Must be run after installing GNOME 50 packages; EL10's `%post` scriptlets may not run this automatically in mock-installed RPMs.

4. **GDM Wayland** (`/etc/gdm/custom.conf`): Set `WaylandEnable=true` (no Xorg on EL10 by default).

### GDM 50 Architecture Notes (for packaging)

GDM 50 no longer uses a static `gdm` user for greeters. It dynamically allocates `gdm-greeter`, `gdm-greeter-2`, etc. via systemd's Varlink userdb API, serving them at `/run/systemd/userdb/org.gnome.DisplayManager`. The `systemd --user` instance for these dynamic users must start successfully for gnome-session to launch; this requires the PAM fix above.

**Known spec workarounds already applied** (must be revisited post-bootstrap):
- `glib2`: Removed `BuildSystem: meson`, manually expanded macros, patched `.pc` file
- `glycin`: Offline Rust vendor build, removed tests, stripped conflicting `Obsoletes`
- `mozjs140`/`gjs`: Built with `--with-system-icu` — links against **whatever libicu-devel is in the COPR build environment at build time**. Do NOT add `libicu-77` as a system-replacement package in COPR; it upgrades away libicu-74 and breaks gtk3/pango/everything else compiled against it. If mozjs140 was mistakenly built against libicu-77, delete the icu build from COPR and rebuild mozjs140, gjs, and any other affected packages.
- `libical`/`evolution-data-server`: Intentionally **not** in COPR — they required libicu-77 which caused system-wide conflicts. Drop them unless a future resolution (e.g. parallel libicu packaging) is found.
- `fontconfig`/`pango`: Stripped doc toolchain, broad file globs
- `pipewire`: Bumped to 1.6.1, disabled optional ldac/spandsp

When adding new packages or modifying existing specs, check AGENTS.md for known EL10 quirks before attempting standard Fedora spec approaches.

## COPR Debugging Workflow

Test installs from COPR using a throwaway container — do not use `--skip-broken` initially, read the actual errors:
```bash
podman run --rm quay.io/centos/centos:stream10 bash -c "
  dnf -y install dnf-plugins-core &&
  dnf copr enable -y jreilly1821/c10s-gnome-50-fresh &&
  dnf -y install <packages>
"
```

`just copr-srpm-build <dir>` — pass the **directory**, not the spec path (justfile globs for `*.spec` internally).

`copr-cli delete-build <id>` — deletes build and its RPMs; COPR metadata takes ~30s to regenerate after deletion.
