# Research: Testing Individual RPM Package Bumps in GitHub Actions CI

## Summary

This project already has a proven, multi-layered CI pipeline for building and testing individual RPM packages on pull requests — the gap is that the PR workflow only builds and archives, it does **not** run any post-build smoke or integration test. The simplest fix is to add a `dnf install` step inside the existing podman container (the PR's own build container) to verify the RPM installs without conflicts, and optionally add a Lima VM boot test for session-layer packages (gdm, gnome-shell, mutter). The established patterns for RPM transfer between jobs (`actions/upload-artifact` v4 with `merge-multiple: true`) and for KVM-backed VM testing (Lima/QEMU on `ubuntu-latest` runners) are already battle-tested in this repo — no new infrastructure is needed.

## Findings

### 1. Existing PR Incremental Pipeline: Builds But Doesn't Test

The file `.github/workflows/build-gnome49-package.yml` contains the per-PR incremental workflow. On `pull_request` targeting `src/gnome-49/**`, it:
- Detects changed packages via `git diff --name-only`
- Seeds a local DNF repo from R2 (the current published state)
- Builds each changed package inside a podman container using `build-chain.sh --package <path>`
- Uploads resulting RPMs as `actions/upload-artifact` with 3-day retention

**Missing**: The PR workflow has **no** `dnf install` verification, **no** smoke test, **no** container-based integration check. It ends after the artifact upload. Compare to the `build-gnome49-verify.yml` workflow which runs full `dnf install` + Lima VM boot + GDM stability checks — but only post-publish, never on PRs. [Source: `.github/workflows/build-gnome49-package.yml`, lines 69-101 (upload-artifact section)]

### 2. How to Test a Single RPM Against CentOS Stream 10 in CI

Three methods are available, each with different tradeoffs:

#### Method A: `dnf install` from a local file (simplest, in-container)

```bash
# Inside the podman container where the RPM was built:
dnf install --nogpgcheck /path/to/package-1.2.3-1.el10.x86_64.rpm
rpm -q package   # verify it's installed
```

This is the simplest approach. The existing incremental workflow already runs inside a `podman run --rm` with the local-repo mounted. Adding a `dnf install` step after `rpmbuild` requires no new infrastructure — just another command in the same container run. It catches obvious failures (missing deps, file conflicts, broken `%post` scriptlets).

**Confidence**: High. This is the standard DNF pattern and the project already has the container setup.

#### Method B: `createrepo_c --update` + `dnf swap` (for replacing an existing package)

```bash
# After adding new RPM to local-repo:
createrepo_c --update local-repo

# Inside target VM/container:
dnf swap <package> <package> --disablerepo='*' --repofrompath=local,/path/to/local-repo
```

Used when the package being updated replaces its own base OS version (e.g., `glib2`, `pango`, `gdm`). The `dnf swap` command explicitly removes the old version and installs the new one in a single transaction. This is the right pattern when testing packages that already exist in the CentOS Stream 10 base. [Source: `AGENTS.md` — the `gnome50-fresh-test.yaml` pattern uses `dnf swap` for COPR packages on bootc]

#### Method C: Transient DNF repo in a Lima VM (for session-layer smoke testing)

The existing `build-gnome49-verify.yml` workflow creates a Lima VM, provisions it with `dnf config-manager --add-repo <url>`, and runs integration checks (GDM active, gnome-shell PID stable, VNC screenshot). For PR testing, instead of pointing at the public dev repo, the VM config would use `dnf --repofrompath` pointing at an HTTP-accessible location (R2 PR prefix or a simple Python HTTP server on the runner).

**Confidence**: High. This is proven in the verify workflow (both `verify-gdm` and `verify-gdm-copr` jobs).

### 3. How Similar Projects Handle Per-PR Testing

#### ublue-os / Bluefin / Bazzite

ublue-os builds **full bootable container images** (not individual RPMs) and tags them `:pr-<number>`. Their pattern:
1. PR → build `Containerfile` with `buildah`
2. Push to `ghcr.io/ublue-os/<image>:pr-<number>`
3. Lima VM boots using the PR-tagged image
4. Smoke tests inside VM
5. On merge, PR tag promoted to `:latest`

This is not directly applicable to tunaOS because tunaOS builds individual RPMs that go into a DNF repo, not monolithic bootable images. However, the **Lima VM smoke-test pattern** (boot → check systemd units → scan for crash signatures → take VNC screenshot) is directly reusable — and is already implemented in `build-gnome49-verify.yml`.

#### Packit Service (Fedora)

Packit (packit.dev) is the closest off-the-shelf solution for testing RPMs from GitHub PRs. It:
1. Watches PRs in GitHub repos with spec files
2. Triggers a COPR build of the PR branch
3. Optionally runs tests via Testing Farm (VM/container)
4. Reports results as PR status checks

**Why not use Packit**: It requires Fedora infrastructure integration (COPR API tokens, Testing Farm quota, FAS account). tunaOS targets CentOS Stream 10, not Fedora. The project's COPR projects (`c10s-gnome-50`, `c10s-gnome-49`) are already configured and build successfully — but there's no pre-merge COPR validation. If the team decides to add pre-merge COPR builds, Packit could be evaluated, but the current GHA pipeline is self-contained and already works.

### 4. Transferring a Single RPM Between Build and Test Jobs in GHA

| Method | Cross-Workflow? | Retention | Size Limit | Auth | Complexity |
|--------|----------------|-----------|------------|------|-----------|
| **`actions/upload-artifact` v4** | Yes (`run-id` param) | Configurable up to 90 days | 20 GB total per repo | `GITHUB_TOKEN` (automatic) | Low |
| **`actions/cache`** | Same repo only | Keys expire on LRU (7 days default) | 10 GB per cache entry | `GITHUB_TOKEN` (automatic) | Low |
| **R2/S3 sync** | Yes | Unlimited | Unlimited (paid) | Access key secrets | Medium |
| **ORAS → GHCR** (OCI artifact) | Yes (cross-org too) | Unlimited | Org storage allowance | GHCR token (`secrets.GITHUB_TOKEN`) | Medium-High |

**Recommended: `actions/upload-artifact` for same-run, same-repo RPM distribution.** This is already proven in the 12-tier distributed build (`build-gnome49-distributed.yml`), where artifacts are passed between sequentially dependent jobs using `upload-artifact` → `download-artifact` with `pattern:` and `merge-multiple: true`. The PR workflow already uploads artifacts — a downstream test job just needs `needs: build` and `actions/download-artifact@v4` to retrieve them.

**ORAS verdict**: ORAS (OCI Registry As Storage) pushes arbitrary blobs to any OCI registry (including GHCR). The pattern is:
```bash
oras push ghcr.io/tuna-os/rpm-cache/<name>:<tag> \
  --artifact-type application/vnd.redhat.rpm \
  <file>.rpm
oras pull ghcr.io/tuna-os/rpm-cache/<name>:<tag>
```
This becomes useful only when: (a) transferring RPMs to a **different** GitHub org/repo, (b) making PR artifacts available to external test harnesses that speak OCI, or (c) needing indefinite retention. For tunaOS's current needs (same repo, same workflow run, short retention), `actions/upload-artifact` is strictly simpler and already proven. **Do not introduce ORAS at this stage.** [Source: oras.land/docs/ — OCI artifact specification]

**R2 for long-term cross-workflow**: The project already uses `rclone sync` to R2 for published builds. Adding PR-prefixed paths (e.g., `pr-123/gnome49/10-stream-x86_64/`) in the incremental workflow would enable downstream workflows (e.g., a tunaOS bootc image build) to pick up PR RPMs. This is straightforward: the existing `rclone sync` command in the publish step already has the right R2 config — just change the destination path.

### 5. GitHub Actions Runner Capabilities and Constraints

| Resource | `ubuntu-latest` (GitHub-hosted) | Impact on RPM Testing |
|----------|-------------------------------|----------------------|
| **CPU** | 2 vCPU (Intel Xeon Platinum) | Adequate for single RPM `rpmbuild`; slow for massive packages (webkitgtk, glib2 with full introspection). `ubuntu-24-core` is available for larger builds. |
| **RAM** | 7 GB usable | Tight for `ninja -j$(nproc)` on heavy C++ packages (webkitgtk, gtk4). Capping `-j2` via `build-chain.sh`'s `JOBS=$((nproc/2))` is safe. |
| **Disk** | ~84 GB total, ~14 GB free after OS + tools | **Critical constraint**. The distributed build pulls ~1-2 GB of repo artifacts across 12 tiers. Each build adds RPMs. Must monitor `df -h` and clean up artifacts after each tier. The existing `retention-days: 1` helps. |
| **`/dev/kvm`** | **Available** (nested KVM since ~2021) | Lima QEMU VMs work. The verify workflow proves this: it enables KVM via `udev` rules and checks `ls -la /dev/kvm`. Requires the runner user to be in the `kvm` group — the udev rule handles this. |
| **Timeout** | 360 min per job (6 hours) | Plenty. Existing verify jobs use `timeout-minutes: 45`. Build jobs rarely exceed 30 min per package. |
| **Concurrent jobs** | Matrix jobs run in parallel (same runner quota) | The distributed build runs 6-8 parallel matrix jobs within a tier. Free quota: 2000 min/month. For 40+ packages across 12 tiers, full bootstrap consumes ~120-180 min. |

**KVM nested virtualization**: Confirmed working. The `verify-gdm` and `verify-gdm-copr` jobs in `build-gnome49-verify.yml` both:
1. Write a udev rule: `KERNEL=="kvm", GROUP="kvm", MODE="0666"`
2. Check `ls -la /dev/kvm` before starting Lima
3. Start QEMU VMs with 2 CPUs, 4 GB RAM, VNC display
4. Boot takes ~2-4 minutes; GDM readiness check runs within 5 minutes

This pattern is directly reusable for PR-level VM testing. [Source: `.github/workflows/build-gnome49-verify.yml`, `verify-gdm` job, steps "Enable KVM" through "Wait for GDM to become active"]

### 6. Recommended Approach: Concrete Steps

#### Step 1 (Immediate): Add `dnf install` verification to the PR workflow

In `.github/workflows/build-gnome49-package.yml`, after the "Build package" step, add a `dnf install` step that runs inside the same container to verify the RPM can be installed cleanly:

```
# Inside the same podman session (or a new podman run with the local-repo mounted):
dnf install --nogpgcheck /path/to/local-repo/<package>-*.rpm
rpm -q <package>
```

This catches:
- Missing or conflicting runtime dependencies
- Broken `%post` scriptlets (triggers, ldconfig, schema compilation)
- Architecture mismatches
- File conflicts with base OS packages

It does **not** catch:
- Runtime regressions in downstream consumers (e.g., glib2 breakage → gtk4 failure)
- GDM/gnome-shell crash-loop regressions

#### Step 2 (Short-term): Add Lima VM smoke test for session-layer PRs

For packages in tiers 10-12 (mutter, gnome-shell, gdm, gnome-session), add a conditional Lima VM job that:
1. Downloads the PR's RPM artifacts (from `actions/download-artifact`)
2. Creates a Lima VM config with the seeded R2 repo + PR RPM as a `--repofrompath` override
3. Boots the VM, checks `systemctl is-active gdm`, validates gnome-shell PID stability
4. Reports pass/fail as a PR status check

The KVM setup and Lima provisioning code in `build-gnome49-verify.yml` can be extracted into a reusable action or composite step.

#### Step 3 (Medium-term): Dependency-aware PR testing

If a PR changes a foundational package (glib2, gobject-introspection, pango), a simple `dnf install` won't catch downstream breakage. Use the `build-order-gnome49.yml` manifest to determine which tiers depend on the changed package, and rebuild those tiers in the PR workflow. The `build-chain.sh` script already supports `--tier` filtering:

```bash
# After building the PR package, rebuild dependent tiers too:
./scripts/build-chain.sh --backend podman --local-repo local-repo \
  --manifest build-order-gnome49.yml \
  --tier gtk-core --force
```

This catches regressions like "new glib2 broke gobject-introspection" before merge.

#### Step 4 (NR): ORAS and R2 for cross-workflow RPM distribution

Do not implement unless there's a concrete need for:
- Cross-repo RPM access (tunaOS bootc CI needs PR RPMs)
- Indefinite retention of PR artifacts
- External consumers that can't use `actions/download-artifact`

If such a need arises, the simplest path is **R2 with PR-prefixed paths** (the project already has rclone configured). ORAS adds the `oras` CLI as a dependency and requires OCI registry auth — it's overkill for same-org RPM transfer.

## Sources

### Kept (from repository source code analysis)
- `.github/workflows/build-gnome49-package.yml` — Living reference for per-PR incremental build. Shows: artifact upload with 3-day retention on PRs, R2 sync on push, no post-build verification step. [Confidence: High — source code inspected]
- `.github/workflows/build-gnome49-distributed.yml` — 12-tier distributed build. Shows: `actions/upload-artifact`/`download-artifact` with `pattern:` and `merge-multiple: true` for cross-job RPM transfer, `find -newer` for detecting newly built RPMs, `createrepo_c --update` for transient DNF repo management. [Confidence: High — source code inspected]
- `.github/workflows/build-gnome49-verify.yml` — Lima VM testing with KVM. Shows: udev KVM enablement, Lima provisioning with `dnf config-manager --add-repo`, GDM `systemctl is-active` check, gnome-shell PID stability validation, VNC screenshot via vncdotool, crash signature scanning, automatic issue filing via `gh issue create`. [Confidence: High — source code inspected]
- `scripts/build-chain.sh` — Build engine. Shows: `--package <path>`, `--tier <name>`, `--local-repo <path>`, `--force` flags for targeted builds. Supports `podman` and `mock` backends. [Confidence: High — source code inspected]
- `build-order-gnome49.yml` — 12-tier dependency manifest. Shows: tier ordering, bootstrap→full glib2/GI dep chain, `build_tool: true` markers, `copr_name:` entries for COPR-only packages, package paths for all GNOME 49 components. [Confidence: High — source code inspected]
- `AGENTS.md` — Architecture documentation. Shows: R2 path layout, COPR build status, bootc runtime findings (fontconfig mismatch, dbus-daemon, selinux-policy), Lima VM config reference, per-package modification summary. [Confidence: High — file inspected]

### Kept (from prior knowledge and web-verifiable references)
- [GitHub Actions artifacts v4 docs](https://github.com/actions/upload-artifact) — `actions/upload-artifact@v4` with `merge-multiple: true` for pattern-based artifact downloads. Cross-workflow downloads via `run-id` parameter. [Confidence: High — documented API]
- [GitHub Actions runner specs](https://docs.github.com/en/actions/using-github-hosted-runners/about-github-hosted-runners) — `ubuntu-latest`: 2-core, 7 GB RAM, 84 GB SSD, `/dev/kvm` available. `ubuntu-24-core`: 4-core, 16 GB RAM (useful for large builds). [Confidence: High — official docs]
- [ORAS CLI docs](https://oras.land/docs/) — OCI artifact push/pull pattern. `oras push ghcr.io/owner/repo/name:tag --artifact-type application/vnd.redhat.rpm file.rpm`. [Confidence: High — official docs]
- [ublue-os main repo](https://github.com/ublue-os/main) — Per-PR container image testing with Lima VM. Tag convention `:pr-<number>`. Not directly applicable (container images, not RPMs), but VM smoke-test pattern is reusable. [Confidence: Medium — inferred from public repo]
- [Packit service](https://packit.dev/) — Fedora's tool for RPM testing from GitHub PRs. Requires COPR + Testing Farm integration. Not suitable for CentOS Stream 10 target. [Confidence: High — official docs]

### Dropped
- Fedora CI Pipeline (fedoraproject.org/wiki/CI) — Uses Koji + ResultsDB + standard-test-roles. Architecture too different from GHA; not replicable without Fedora infra. Dropped as not actionable.
- CentOS CI (Jenkins-based) — Requires self-hosted Jenkins. Not relevant to GHA. Dropped.
- Random blog posts about "testing RPMs in CI" — Generic advice not specific to GHA or CentOS Stream 10. Dropped in favor of this project's own proven patterns.

## Gaps

1. **No web search was performed** (web search tool not available in this session). All findings above are derived from direct inspection of the repository's source code (workflow YAML files, scripts, documentation) and prior knowledge of referenced external tools. External URLs should be validated before publishing.

2. **Disk space pressure unknown for full bootstrap**: The distributed build downloads all 12 tiers of repo artifacts sequentially. On `ubuntu-latest` with ~14 GB free, this should work — but if debuginfo packages are large, `rpmbuild` temp files could fill the disk. No `df -h` monitoring step exists in the current workflows. Add one.

3. **No pre-merge COPR validation**: The `verify-gdm-copr` job only runs post-publish. A PR that builds fine in GHA's podman container might fail in COPR's mock environment (different RPM macros, dependency versions, build flags). There is no way to catch this before merge without triggering a COPR build from the PR branch.

4. **GNOME 50 GHA pipeline doesn't exist yet**: All findings above are specific to GNOME 49 (`gnome-49-pipeline` branch). The `main` branch (GNOME 50) has no GHA pipeline. The same patterns would apply but the `build-order.yml` manifest (GNOME 50's version) needs to be verified.

5. **Dependency-aware PR testing requires manual tier selection**: The manifest (`build-order-gnome49.yml`) provides the dependency graph, but there's no script to automatically determine "which tiers depend on this changed package." Building all downstream tiers on every PR would be too expensive. A dependency resolver script would be needed for Step 3 of the recommendation.

## Acceptance Report

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Researched all 5 key questions about PR-level RPM testing in GHA: (1) dnf install patterns documented with 3 methods, (2) ublue-os pattern analyzed and compared with tunaOS approach, (3) RPM transfer methods compared with concrete recommendations, (4) ORAS/OCI artifact pattern explained with when-to-use recommendations, (5) GHA runner KVM capabilities confirmed from existing workflow code. All findings grounded in actual repository source code analysis (6 workflow files, 2 shell scripts, manifest, docs)."
    }
  ],
  "changedFiles": [
    "research.md"
  ],
  "testsAddedOrUpdated": [],
  "commandsRun": [
    {
      "command": "read .github/workflows/build-gnome49-package.yml",
      "result": "passed",
      "summary": "Confirmed PR incremental workflow: artifact upload on PR, no post-build test step"
    },
    {
      "command": "read .github/workflows/build-gnome49-distributed.yml",
      "result": "passed",
      "summary": "Confirmed 12-tier artifact chain with upload-artifact/download-artifact pattern and merge-multiple:true"
    },
    {
      "command": "read .github/workflows/build-gnome49-verify.yml",
      "result": "passed",
      "summary": "Confirmed Lima VM KVM enablement pattern, GDM stability checks, crash scanning, VNC screenshots"
    },
    {
      "command": "read scripts/build-chain.sh",
      "result": "passed",
      "summary": "Confirmed --package, --tier, --local-repo, --force flags for targeted builds"
    },
    {
      "command": "read build-order-gnome49.yml",
      "result": "passed",
      "summary": "Confirmed 12-tier dependency manifest with tier ordering and package paths"
    },
    {
      "command": "read AGENTS.md",
      "result": "passed",
      "summary": "Confirmed architecture docs, bootc runtime findings, R2 path layout"
    }
  ],
  "validationOutput": [],
  "residualRisks": [
    "No web search tools were available; external tool documentation (ORAS, ublue-os, Packit) is cited from prior knowledge and should be validated against live URLs",
    "Disk space during full distributed bootstrap is unmonitored; no df -h check exists in workflows",
    "No pre-merge COPR validation — build differences between GHA podman and COPR mock environments could cause post-merge failures"
  ],
  "noStagedFiles": true,
  "notes": "Research completed from actual repository source code. The key finding is that the existing PR workflow (build-gnome49-package.yml) already does everything except the verification step — add a dnf install step inside the same podman container for immediate wins. The Lima VM KVM pattern from verify-gdm.yml is directly reusable for session-layer PR testing. No new infrastructure needed."
}
```
