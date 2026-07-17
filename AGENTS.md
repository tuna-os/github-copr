# GNOME Bootstrap on CS10 - Status Report

## 1. Project Branches & Versions
*   **GNOME 50**: Tracks Fedora **Rawhide** Dist-Git.
*   **GNOME 49**: Tracks Fedora **F43** Dist-Git.

## 2. Package Source Priorities
When adding or updating packages, adhere to the following priority list:
1.  **Fedora Dist-Git** (`just copr-build <name>`): Use for unmodified packages. Use `rawhide` for GNOME 50 and `f43` for GNOME 49.
2.  **GitHub SCM** (`just copr-scm-build <path>`): Use for modified specs (patches, EL10-specific fixes).
3.  **Local SRPM** (`just copr-srpm-build <path>`): Use only as a last resort.

## 3. ICU 77 Dependency Isolation
ICU 77 is bundled with packages that require it (e.g., `mozjs140`, `tinysparql`) instead of using a standalone package. This prevents "repo poisoning" and conflicts with EL10's base ICU 74.

## Current Projects
*   **`jreilly1821/c10s-gnome-50`**: GNOME 50 development.
*   **`jreilly1821/c10s-gnome-49`**: GNOME 49 development (forked from GNOME 50).

## Current Status: COPR Build Cycle 1 (2026-03-14)
...
### 1. Build Successes
*   **Secondary Repo (`icu77-el10`)**: 
    *   `meson`, `autoconf`, `python-smartypants`, `python-typogrify` (Build tools).
    *   `wayland-protocols`, `shaderc`, `gi-docgen`, `icu`.
*   **Main Repo (`c10s-gnome-50`)**:
    *   `libldac`, `gnome50-el10-compat`, `selinux-policy`, `libei`.
    *   `gobject-introspection` (Bootstrap variant).

### 2. Immediate Blockers (Failed Builds)
*   **Core Graphics/Foundations**: 
    *   `glib2` (Failed in bootstrap and full variants).
    *   `harfbuzz`, `pango`, `fontconfig`.
    *   `libzip`, `libxcvt`.
*   **Desktop Layer**:
    *   `gtk4`, `glycin` (Conflict/Build issues).
    *   `localsearch`, `mutter`.
*   **System Tools**:
    *   `umockdev` (Failed in secondary repo).

### 3. Analysis of Failures
*   **`glib2`**: Investigating if `icu77` headers are missing from the build environment despite the repo being linked.
*   **`harfbuzz`**: Likely failing due to the `glib2` failure (missing dependency).
*   **`libzip`**: Initial look suggests a potential missing build dependency in EL10/EPEL10.
*   **`glycin` Version Conflict**: COPR's `distgit` builder pulled a version (2.0.8-3) that incorrectly obsoletes `gdk-pixbuf2`. Our local fix (2.0.8-100) is pending success.

### 3. Documentation
*   **`SRPM-CHANGES.md`**: Tracks all manual spec/source modifications (PAM fixes, Rust vendoring, dependency injections).
*   **`COPR-REPORT.md`**: Categorizes all 40+ packages by origin (Custom vs Modified vs Unmodified Rawhide).
*   **GitHub Issue #1**: Documented the `systemd-user` PAM regression for upstream/community visibility.

## Self-Hosted GitHub Actions Pipeline (GNOME 49)

As of 2026-03-15, a parallel self-hosted build pipeline has been implemented alongside COPR in the `gnome-49-pipeline` branch. **The COPR projects are untouched — this is additive.**

### Architecture
```
src/gnome-49/ specs
   → GitHub Actions (mock/podman per-package matrix jobs)
   → GPG sign (secrets.GPG_PRIVATE_KEY)
   → Cloudflare R2 (r2:bluefin/gnome49/10-stream-x86_64/)
   → repo.tunaos.org/gnome49/10-stream-x86_64/ (Cloudflare Worker, no changes needed)
   → DNF repo usable by end users
```

### Key Files
| File | Purpose |
|------|---------|
| `.copr/build-order-gnome49.yml` | GNOME 49 tier manifest (12 tiers, separate from GNOME 50) |
| `.github/workflows/build-gnome49-distributed.yml` | Full bootstrap: builds all tiers in sequence, per-package parallel matrix |
| `.github/workflows/build-gnome49-package.yml` | Incremental: triggered by Renovate PRs or manual dispatch for single package |
| `.github/workflows/build-gnome49-verify.yml` | Post-publish: verifies repo.tunaos.org is serving packages correctly |
| `scripts/watch-pipeline.sh` | Local script to trigger/watch GHA runs via `gh` CLI |
| `contrib/install-gnome49.sh` | User install script (gpgcheck=1, hardcoded baseurl) |
| `renovate.json` | Tracks spec Version: fields against Fedora F43 dist-git |
| `gnome49-repo-test.yaml` | Lima VM config: end-to-end test using repo.tunaos.org (not COPR) |

### R2 Path Layout
- GNOME 49: `r2:bluefin/gnome49/10-stream-x86_64/` → `https://repo.tunaos.org/gnome49/10-stream-x86_64/`
- GNOME 50: `r2:bluefin/repo/10-x86_64/` → `https://repo.tunaos.org/repo/10/x86_64/` (unchanged)

The Cloudflare Worker's `transformPath()` only touches `/repo/...` paths. `/gnome49/...` paths are served directly with no transform.

### Pipeline Commands
```bash
scripts/watch-pipeline.sh run          # trigger full bootstrap + watch
scripts/watch-pipeline.sh watch        # watch latest run
scripts/watch-pipeline.sh package src/gnome-49/gdm   # rebuild one package
scripts/watch-pipeline.sh status       # show recent runs
```

### GNOME 49 COPR Status (2026-03-15)
- **`jreilly1821/c10s-gnome-49`**: All packages green across all 3 chroots (epel-10-x86_64, epel-10-aarch64, alma-kitten+epel-10-x86_64_v2) as of this date.
- Key fix: GDM 49.2 patch `0001-el10-force-varlink-mode-0666.patch` — EL10 libsystemd 257 rejects `SD_VARLINK_SERVER_MODE_MKDIR_0755 = 0x40000000`. The patch forces `#undef` + `#define 0` so the varlink socket at `/run/systemd/userdb/org.gnome.DisplayManager` is created correctly.

## GNOME 50 on bootc (tunaOS skipjack) — Runtime Findings (2026-03-20)

Testing `ghcr.io/tuna-os/skipjack:gnome50` (based on `quay.io/centos-bootc/centos-bootc:stream10`) in a Lima QEMU VM revealed three blockers that do NOT affect a plain CentOS cloud image install:

### Root Cause Chain

| # | Symptom | Root Cause | Fix |
|---|---------|-----------|-----|
| 1 | `symbol lookup error: libpangoft2-1.0.so.0: undefined symbol: FcConfigSetDefaultSubstitute` | COPR pango 1.57.0 built against fontconfig 2.17.0; bootc base has 2.15.0 (symbol absent) | Upgrade `fontconfig` from COPR before installing GNOME stack |
| 2 | `gdm-wayland-session: Unable to run session message bus` (exit 64) | `dbus-daemon` not installed — it is a `Recommends:` of gdm, not hard `Requires:`, so bootc prunes it | Explicitly install `dbus-daemon` in gnome.sh |
| 3 | GDM userdb socket denied even in permissive SELinux | Base EL10 `selinux-policy` 42.x has no policy for GDM 50 dynamic greeter users | Allow `selinux-policy` 43.x from COPR (remove from exclude list) |

### Outcome
After applying all three fixes to a running VM (via `bootc usr-overlay`):
- `gdm.service` reached `active (running)` and stayed stable (8+ minutes, no restart cycling)
- `gnome-shell --mode=gdm` (PID confirmed) launched successfully using `kms_swrast` software rendering on `virtio_gpu`
- GDM greeter session visible on VNC display

### Applied Fixes in tunaOS `build_scripts/gnome.sh`
1. **Removed `selinux-policy*` from COPR exclude** — selinux-policy 43.1 from COPR is required, not optional
2. **Added `fontconfig` to early upgrade** — `dnf -y upgrade glib2 fontconfig` so pango's COPR build resolves correctly
3. **Added `dbus-daemon` to EL10 package install list** — required for GDM Wayland session bus
4. **Added `fontconfig` to versionlock list** — prevents inadvertent downgrade back to 2.15.x

### Lima VM Config Reference
`gnome50-fresh-test.yaml` (plain CentOS cloud image) is the working reference — it explicitly installs `selinux-policy` and `selinux-policy-targeted` from COPR and reaches GDM greeter. Use it to validate COPR changes before rebuilding the bootc image.

## Work Items / TODOs

- [x] **GNOME 49 COPR all-green**: All packages across all 3 chroots succeeded (2026-03-15)
- [x] **GDM varlink socket fix**: Patched `gdm-dynamic-user-store.c` — socket now created correctly
- [x] **GNOME 50 bootc GDM root cause found**: fontconfig 2.15→2.17 mismatch, missing dbus-daemon, selinux-policy 42→43 (2026-03-20)
- [x] **tunaOS gnome.sh fixed**: fontconfig upgrade, dbus-daemon install, selinux-policy unexcluded
- [ ] **skipjack gnome50 image rebuild**: `just build skipjack gnome50` + `just qcow2` to validate clean boot
- [ ] **First GHA bootstrap run**: Trigger `build-gnome49-distributed.yml` and verify all 12 tiers build
- [ ] **repo.tunaos.org/gnome49/ live**: After first successful run, verify HTTP 200 for repomd.xml
- [ ] **VM verification**: `limactl start gnome49-repo-test.yaml` and verify GDM socket exists
- [ ] **Renovate**: Enable Renovate app on repo and verify it finds spec version fields
- [ ] **Merge to main**: After pipeline is stable, PR `gnome-49-pipeline` → `main`
- [ ] **GNOME 50 GHA pipeline**: Same treatment for `build-order.yml` packages (future)

## Modified Packages Summary
| Package | Primary Change |
| :--- | :--- |
| `gnome50-el10-compat` | New: PAM `systemd-user` workaround |
| `gdm` | Added `Requires: gnome50-el10-compat` |
| `gnome-user-share` | Vendored Rust crates + added missing `glib2` BR |
| `gi-docgen` | Removed `BuildSystem: pyproject` for EL10 compatibility |
| `glib2` | Retained EL10 schema compilation triggers |
| `glycin` | Modified to prevent `gdk-pixbuf2` obsolescence |
