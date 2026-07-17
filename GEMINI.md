# GEMINI.md - GNOME 50 Bootstrap Engineering Standards

This file defines foundational mandates and engineering standards for the GNOME 50 on CentOS Stream 10 (EL10) project.

## 1. Package Source & Build Priorities
Always prefer sources in the following order to maintain long-term maintainability:
1.  **Fedora Rawhide Dist-Git** (`just copr-build <name>`): Use for all UNMODIFIED packages.
2.  **GitHub SCM** (`just copr-scm-build <path>`): Use for all MODIFIED packages (patches, EL10-specific fixes). This ensures spec changes are versioned in this repo.
3.  **Local SRPM** (`just copr-srpm-build <path>`): Use only for emergency overrides or one-off tests.

## 2. Dependency Management & "Repo Poisoning"
We must protect the integrity of the main user repository. Avoid adding packages that trigger mass-rebuilds of base system components.

### ICU 77 Isolation
- **Problem**: GNOME 50 (mozjs140, tinysparql) requires ICU 77, but EL10 base is ICU 74.
- **Mandate**: **Do NOT build ICU 77 in the main COPR repo as a standalone package.**
- **Standard**: 
    - Use **bundled ICU 77** (static linking or private shared libs) for packages that require it (e.g., `mozjs140`, `tinysparql`).
    - This allows builds to succeed while preventing end-users from accidentally upgrading their system ICU or causing repository poisoning.
    - All build-time tools (like Autoconf 2.72) should also be built against the system ICU or bundled if necessary.

## 3. Workflow Standards
- **Validation**: Every change must be validated via `podman run --rm -it ghcr.io/ublue-os/bluefin:lts` or a local CS10 container.
- **Documentation**: Manual spec changes must be recorded in `SRPM-CHANGES.md`.
- **SCM Sync**: Ensure local `src/` changes are committed to GitHub before triggering `copr-scm-build`.

## 4. Key Workarounds (Mandatory)
- **PAM**: `gnome50-el10-compat` (or `gnome49-el10-compat`) must be present to fix GDM dynamic user login on EL10.
- **SELinux**: Use Rawhide's `selinux-policy` backport to support GDM 50 userdb architecture.
- **Rust**: For Rust packages lacking EL10 crate dependencies (e.g., `gnome-user-share`), use **vendored tarballs** and offline builds.
- **GDM varlink (GNOME 49)**: EL10 libsystemd 257 rejects `sd_varlink_server_listen_address()` calls with mode bits outside 0777. GDM compiled with newer systemd headers passes `0x400001b6` (0666 | 0x40000000), which is rejected with EINVAL. The patch `src/gnome-49/gdm/0001-el10-force-varlink-mode-0666.patch` uses `#undef SD_VARLINK_SERVER_MODE_MKDIR_0755` + `#define SD_VARLINK_SERVER_MODE_MKDIR_0755 0` to force a safe mode regardless of compile-time headers.

## 5. Self-Hosted Pipeline Rules (GitHub Actions + R2)

### CRITICAL: What NOT to touch
- **NEVER** modify `build-order.yml` (GNOME 50 manifest) or any existing GNOME 50 workflow files (`build-distributed.yml`, `build.yml`).
- **NEVER** modify the existing R2 paths `repo/10-x86_64/` or `repo/10-stream-x86_64/` — these are for GNOME 50 and untouched by the GNOME 49 pipeline.
- **NEVER** change `workers/repo-proxy.ts` unless explicitly asked. The GNOME 49 URL path `/gnome49/...` is served directly from R2 without any Worker transformation (the transform only applies to `/repo/...` paths).
- **NEVER** change COPR build commands (`just copr-build`, `just copr-scm-build`, `just copr-srpm-build`) — COPR and GitHub Actions pipelines are **parallel, not replacements** for each other.
- **NEVER** mix GNOME 49 packages into the GNOME 50 manifest or R2 paths, or vice versa.

### GNOME 49 Self-Hosted Pipeline
- **Manifest**: `.copr/build-order-gnome49.yml` (11 tiers, separate from GNOME 50's `build-order.yml`)
- **Bootstrap workflow**: `.github/workflows/build-gnome49-distributed.yml` — GENERATED from manifest; regenerate with:
  ```bash
  python3 scripts/generate-distributed-workflow.py \
    .copr/build-order-gnome49.yml \
    .github/workflows/build-gnome49-distributed.yml \
    --name "GNOME 49 Distributed Build and Publish" \
    --r2-path "gnome49/10-stream-x86_64"
  ```
- **Incremental workflow**: `.github/workflows/build-gnome49-package.yml` — manually maintained, triggered by Renovate PRs or path-filtered pushes
- **R2 upload path**: `r2:bluefin/gnome49/10-stream-x86_64/`
- **Public URL**: `https://repo.tunaos.org/gnome49/10-stream-x86_64/`
- **Install script**: `contrib/install-gnome49.sh` (uses `gpgcheck=1`, hardcoded baseurl — no `$releasever` expansion)

### Renovate
- Config in `renovate.json` tracks `src/gnome-49/**/*.spec` Version: fields against Fedora F43 dist-git.
- Renovate PRs auto-trigger `build-gnome49-package.yml` via `pull_request` path filters.
- **Do NOT** automerge Renovate PRs for major components (gdm, mutter, gnome-shell) — they require manual verification that EL10 patches still apply.

### Branch Strategy
- All GNOME 49 GHA pipeline work lives in `gnome-49-pipeline` branch.
- Changes that touch ONLY new files (no modifications to existing GNOME 50 files) can be merged to `main`.
- Before any merge: confirm `git diff main -- build-order.yml build-distributed.yml build.yml` is empty.
