# RFC 011: One gap-driven factory

**Status:** Draft
**Tracking issue:** [#418](https://github.com/tuna-os/tunaos-packages/issues/418)
**Owner:** hanthor
**Interacts with:** `docs/PACKAGE_FACTORY.md` (promotion contract),
`docs/TIDEFORGE-READINESS.md` (switch-over verdict),
`manifests/package-factory.yaml` (target contract),
tunaOS `PACKAGE-SOURCING.md` (sourcing tiers),
tunaOS `.github/green-criteria.yml` `upstream_references` (image-side parity consumer)

## Problem

TunaOS ships one desktop experience across many bases. The factory that feeds
those images is not organized that way — it is organized by the crisis that
created each piece:

| Factory family | Workflows | Origin |
| --- | --- | --- |
| EL10 GNOME backport | `build-gnome49/50/51-{distributed,package,verify}` (9) | EL10 ships GNOME 47-era |
| XFCE / XFWL4 | `build-xfce-{distributed,package,fedora,arch-validation}` (4) | Wayland XFCE exists nowhere upstream |
| Hummingbird | `build-hummingbird-{distributed,desktops}` + `hummingbird-gap-drift` (3) | A distro whose repos are incomplete |
| Tideforge | `build-tideforge-{supported,arch}`, `publish-tideforge-debs`, `seed-tideforge-source-cache` (4) | The intended generalization |
| One-offs | `build-fprintd-aarch64` etc. | Individual gaps |

Each family hand-carries its own build ordering (`build-order*.yml`, curated
manually), repo generation, publish gating, skip logic, and drift handling.
Three concrete costs, all observed, none hypothetical:

1. **Copy-paste drift.** The `createrepo_c --update` bug (#358) was fixed in
   `build-xfce-package.yml` and is latent in `build-xfce-distributed.yml`,
   `build.yml`, and all three GNOME distributed workflows. One bug, five
   copies, one fix.
2. **Hand-curated build orders rot.** The hummingbird order was 1248 sources
   until a measurement against the live upstream index showed the runtime gap
   is 673. Every other family's order is maintained by memory and diff-reading;
   nothing re-measures when a target's repos move. When EL10.1 or Fedora 45
   picks up a package we build, nothing tells us to *stop* building it.
3. **The sourcing policy is unenforced at build-planning time.**
   tunaOS `PACKAGE-SOURCING.md` says system repos first, Tideforge second.
   Whether a package still needs building is a query against the target's
   repos — but no factory family runs that query except hummingbird's.

Meanwhile the same desktop stacks are needed on multiple targets: EL10 needs
newer GNOME, Wayland XFCE, *and* COSMIC (currently a COPR — the largest
violation in the sourcing audit); Ubuntu lacks COSMIC and quickshell; the DMS
stack has no DEB runtime closure. Today each (stack × target) pair is a
separately hand-built answer.

## What already exists and points the way

This RFC proposes very little new invention. The pieces exist; they have not
been composed:

- **The gap engine.** `scripts/measure-hummingbird-gap.py` takes a catalog
  (`manifests/hummingbird-desktops.yaml`), computes the dependency closure
  against a **live target repo index**, applies a membership rule
  (`runtime` vs `selfhost`), and emits a tiered build order. A revision-gated
  drift workflow re-measures only when the target's repo metadata actually
  changes and opens a review PR with the delta. This is the general mechanism;
  it is currently wired to one target.
- **The catalog shape.** `manifests/hummingbird-desktops.yaml` already
  declares intent separately from execution.
- **The target contract.** `manifests/package-factory.yaml` is the
  authoritative list of targets, formats, and R2 paths.
- **The recipe layer.** Tideforge recipes cover 40 packages with proven
  source and build parity (per `docs/TIDEFORGE-READINESS.md`); native EL10
  specs cover the hard GNOME bootstrap that a generic recipe format cannot
  model (scriptlets, file triggers, SELinux policy, bootstrap variants).
- **The image-side consumer.** tunaOS now measures per-cell package parity
  against Bluefin/Aurora references daily (`green-criteria.yml`
  `upstream_references`); the factory side of that loop is what this RFC
  builds.

## Options considered

**A. Status quo, plus discipline.** Keep the families; fix drift bugs in all
copies when found. Rejected: this is the current state, and #358 shows the
discipline does not hold — the copies drift precisely because nothing
structural keeps them together.

**B. Rewrite everything into Tideforge recipes.** Rejected by evidence:
`docs/TIDEFORGE-READINESS.md` is explicit that the EL10 GNOME queue is
`implementation: native-spec` and "there is nothing to switch". Forcing
scriptlets/SELinux/bootstrap machinery into a simple recipe format would
recreate the complexity inside a format designed to exclude it.

**C. One catalog + per-target gap measurement + one orchestrator; packaging
payloads stay heterogeneous.** Chosen. The catalog owns *identity* (what, at
which version, patched how, for which targets); the gap engine owns *whether
and in what order* each target builds it; the orchestrator owns *how a build
runs mechanically*; the payload (tideforge recipe or native spec) owns *how
the package itself is produced*. Nothing working is rewritten.

## Design

### 1. The catalog (`manifests/catalog.yaml`)

One entry per factory package:

```yaml
packages:
  - name: xfconf
    upstream:
      source: https://…/xfconf-4.20.0.tar.bz2
      sha256: "…"
      version: 4.20.0
    patches: [patches/xfconf/*.patch]        # shared across all targets
    packaging:
      rpm: { tideforge: packages/xfconf }    # or: native: src/xfce-wayland/xfconf
      deb: { tideforge: packages/xfconf }
    targets: [el10, fc44, hummingbird, noble]  # where a gap may exist
    membership: runtime                        # runtime | selfhost, as today
```

Rules, enforced by tests:

- Every package reachable from any workflow matrix or `build-order*.yml`
  appears in the catalog, and vice versa (this kills the "present under
  `packages/` but in no matrix → never built" trap documented in
  `PACKAGE_FACTORY.md`).
- `targets` may only name targets declared in `manifests/package-factory.yaml`.
- A package with no `packaging` entry for a target's format cannot list that
  target.

### 2. The gap engine (`scripts/measure-target-gap.py`)

Generalization of the hummingbird measurer, target-parameterized:

```
measure-target-gap.py --catalog manifests/catalog.yaml --target el10
  → build-order-el10.yml        (tiered, only packages the target's live
                                  repos cannot supply at the required version)
```

- **System-repos-first becomes computed, not remembered:** if the target's
  index satisfies the requirement, the package drops out of that target's
  order automatically. When a distro catches up, we stop building — with a
  review PR showing the drop, not a silent change.
- One **revision-gated drift workflow per target** (the hummingbird pattern:
  compare the live repomd/Packages index revision against the last measured
  one; re-measure only on change; open a PR with adds/drops and provenance).
- Existing curated orders become *generated artifacts with a proof
  obligation*: Phase 1 is complete for a family only when regeneration
  reproduces the curated order, with every difference explained in the PR.

### 3. The orchestrator (one reusable workflow per package format)

`build-rpm-distributed.yml` (reusable, `workflow_call`) parameterized by
`(target, build-order file, mock config)`; likewise `build-deb.yml`,
`build-arch.yml`. The six hand-copied distributed families become thin
callers. Shared once, not five times: tier scheduling, the already-built skip
check (#410's cost problem gets one fix), `createrepo_c --update` handling
(#358's class dies structurally), staged-install gating, publish gates,
R2 paths from `manifests/package-factory.yaml`, and the step-summary
reporting.

### 4. What does NOT change

- **Native EL10 specs stay authoritative** for the GNOME bootstrap, exactly
  per the TIDEFORGE-READINESS verdict. They become catalog-referenced
  payloads; not one spec is rewritten.
- **No automated promotion to R2** returns in this RFC. The post-incident
  stance (`INCIDENT-repo-wipe-gnome.md`) stands; promotion remains a separate
  decision gated on the runtime-gate work (Phase 3 prepares it, a future RFC
  enables it).
- **The sourcing tiers** (tunaOS `PACKAGE-SOURCING.md`) are unchanged — this
  RFC is their enforcement mechanism, not their revision.
- **No cross-format binary reuse.** A .deb is not an .rpm; the shared wins
  are source pins, patches, versions, orchestration, and gates — never
  binaries.

## Plan of attack

Each phase lands independently, is valuable on its own, and is a safe
stopping point. No phase rewrites a working build.

**Phase 0 — catalog, no behavior change.**
Write `manifests/catalog.yaml` covering every package any family builds
today. Add the completeness tests (matrix ⊆ catalog ⊆ matrix). CI change:
none — the catalog is initially a passive index.
*Gate: the completeness test is green; every current package has recorded
upstream source, version, and packaging ref.*

**Phase 1 — gap engine, shadow mode.**
Generalize the measurer; wire per-target drift workflows. For each family,
regenerate its build order from the catalog and diff against the curated one
until reproduction is exact-or-explained. Hummingbird converts first (it
already works this way); then `build-order-xfce-fedora.yml` (smallest), then
`build-order-xfce.yml`, then GNOME 49/50/51, `build-order.yml` last.
*Gate per family: generated order == curated order, modulo diffs explained in
the conversion PR. The curated file is then deleted and the generated one
committed with its provenance header.*

**Phase 2 — orchestrator consolidation.**
Extract the reusable `build-rpm-distributed.yml` from the *best* current copy
(the xfce-package one, which carries the #358 fix). Convert callers
lowest-risk-first: xfce-fedora → xfce → hummingbird → gnome49 → gnome50 →
gnome51 → `build.yml`. Each conversion PR must show an unchanged (or
improved) run on the same inputs before the old workflow file is deleted.
DEB and Arch orchestrators follow the same pattern from the tideforge
workflows.
*Gate per family: one green run of the converted workflow producing the same
artifact set as the last green run of the old one.*

**Phase 3 — runtime gates, then (separately) promotion.**
Implement the 12 declared gate types from `docs/TIDEFORGE-READINESS.md`
against the unified orchestrator — once, for every family, instead of
per-family. COSMIC and DMS closures (currently "payload-only, no install
assertion" — #169) get staged-install coverage as their closures become
factory-complete.
*Gate: the `PACKAGE_FACTORY.md` "not covered" table shrinks monotonically;
each row's removal cites the run that covered it. Automated promotion remains
out of scope and requires its own RFC with the incident safeguards.*

**Cleanup.** When the last family converts, the factory is: one catalog,
one gap engine + N drift detectors, one orchestrator per format,
heterogeneous payloads. The per-family workflow count drops from ~20 to ~6.

## Risks

- **The catalog becomes a second source of truth that drifts.** Mitigation:
  Phase 0's completeness tests make drift a CI failure, and Phase 1 makes the
  build orders *derived*, so the catalog is load-bearing, not decorative.
- **Regeneration never exactly reproduces a curated order.** Acceptable: the
  gate is exact-or-explained. A diff the conversion PR can defend (a package
  the target now ships; a stale pin) is the mechanism working.
- **The reusable workflow becomes a bottleneck for family-specific quirks.**
  Mitigation: quirks live in the mock config and the payload, which stay
  per-family; the orchestrator only owns the mechanics every family already
  shares. If a quirk cannot be expressed that way, that family converts last
  or not at all — partial adoption still retires four copies of every shared
  bug.

## Success criteria

1. #358's drift class cannot recur (one implementation of repo generation).
2. A distro catching up to a factory package produces a review PR that
   *removes* work, automatically.
3. Adding a package for a new target is a catalog entry + payload, not a new
   workflow.
4. The `PACKAGE_FACTORY.md` exceptions table shrinks and cannot silently
   grow (completeness tests).
