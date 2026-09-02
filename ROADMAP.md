# tunaos-packages Roadmap

**Last updated**: 2026-08-23 | **Maintainer**: tuna-os (hanthor) / packaging maintainers

---

## Mission

Own the native packaging, patches, build ordering, validation, signing, and
publication work needed to ship curated desktop stacks for TunaOS variants —
independently of third-party repositories. Since #430 the mechanism is a
**single package factory**: one planner, one cell boundary, content-addressed
exact reuse, and SLSA attestations, with publishers that promote the bytes the
gate approved rather than rebuilding them. COPR remains bootstrap/compatibility
only and is being retired (#439).

---

## Current Status (2026-08-23)

- **The unified factory landed** (#430, merged 08-19). One planner and one cell
  boundary replaced the per-family build paths; gated artifacts are
  content-addressed and attested.
- **RFC 011 — one gap-driven factory** (#418) is the model the factory is
  converging on: a single catalog, per-target gap measurement, one orchestrator.
  Phase 1's conversion ledger has landed (#446, `docs/rfc011-conversions.md`);
  the shadow-measure proof for Fedora XFCE is #426.
- **Arch parity closed on both arches for every build-chain family** (#476,
  08-22): xfce el10, xfce fedora, and gnome50/51 aarch64 cells exist. The gnome
  aarch64 cells are **deliberately red** — they surfaced arch-independent
  defects needing a packaging decision, recorded on #480 rather than deleted.
- **All three formats now have a planner-driven publisher** (#476). Arch had
  none at all, so its packages were gated, built, verified and unreachable.
  Publishers now restore the gate's ActionResult instead of rebuilding, which
  closes the symptom half of #484.
- **Hummingbird desktops are not building**: zero packages compiled since
  2026-08-09 (#406); every full run is cancelled at the 360-minute job ceiling
  (#412, #401). A weekly `engine=build-chain` cron now gives the desktops a
  scheduled run at all (#476), but the timeout is unresolved.
- **Desktop parity has no valid tracker.** #133 was closed COMPLETED on 08-11
  with its own unexamined list open; the confirmed defect (`marlin:kde` ships
  338 packages against its base's 480, zero KDE packages, no session file) has
  no successor. Tracked in #507; upstream twin tunaos#1294 is still open.

### The #430 operational transition

#488 audits where the post-merge firefighting drifted from #430's philosophy
and states the order to return to it. This table is the live status of that
transition; #488 carries the reasoning behind each row.

| # | Step | Status | Tracking |
|---|------|--------|----------|
| 1 | Ruleset requires `Package factory gate`; drop the compatibility aliases | 🔴 Not started — aliases still live | #483 |
| 2 | Promotion behind the factory boundary (leased R2 ActionResult/blob publication) | 🟡 Symptom half done in #476; structural boundary open | #484 |
| 3 | Native queue packages → first-class per-package recipe actions | 🟡 In progress — ledger row 1 done, row 2 blocked on engine version-awareness, rows 3–5 unstarted | #418, #426 |
| 4 | Workflow consolidation — fold publishers, parameterize gap-drift, retire dormant builders | 🟡 In progress — `upstream-drift.yml` is now the parameterized matrix; `build.yml`/`build-distributed.yml` remain break-glass until 2026-12-31 (census recorded in RFC 011) | #487 |
| 5 | Report-only CAS reachability / GC | 🔴 Not started | #485 |
| 6 | Sampled reproducibility rebuilds + policy reporting | 🔴 Not started | #486 |

### Priorities

| Priority | Item | Tracking | Status |
|----------|------|----------|--------|
| P0 | Desktop parity: successor tracker for the confirmed `marlin:kde` defect, and per-edition installed package sets so parity is diffable | #507, tunaos#1294 | 🔴 Open — #133 closed COMPLETED with the ask unmet |
| P0 | Hummingbird desktops build at all — 6-hour cell ceiling, zero packages since 08-09 | #406, #412, #401 | 🔴 Broken |
| P0 | Finish the #430 transition in #488's order — start with the ruleset cutover | #488, #483, #484 | 🟡 In progress |
| P1 | aarch64 parity: resolve the two packaging decisions behind the red gnome cells | #480 | 🟡 In progress |
| P1 | Retire COPR, including the personal unpinned COPR that Mock CI still depends on | #439, #391 | 🔴 Open |
| P1 | Served-index correctness on repo.tunaos.org | #456, #458 | 🔴 Open |
| P2 | RFC 011 conversion ledger rows 3–5 | #426 | ⬜ Not started |

---

## Quarterly Goals

### Current Quarter (2026 Q3) — "Expand"

**Theme**: One factory, publishing what it gated.

| Goal | Owner | Tracking | Status |
|------|-------|----------|--------|
| Unified factory with exact reuse + attestations | packaging | #430 | ✅ Done — merged 08-19 |
| Every build-chain family builds on both arches | packaging | #480, #476 | 🟡 Landed with gnome aarch64 cells deliberately red pending two packaging decisions |
| Planner-driven publisher for every format | packaging | #476, #479, #481 | 🟡 All three formats have one and promote gated bytes; the structural boundary is #484 |
| Retire COPR in favour of GitHub/R2 | packaging | #439, #391, COPR-AUDIT.md | 🔴 Open — Mock CI still consumes a personal unpinned COPR |
| Desktop-completeness parity floor for every published edition | packaging | #507, tunaos#1294, [docs/desktop-parity-audit.md](./docs/desktop-parity-audit.md) | 🔴 Open — measurement retired without a replacement |

### Next Quarter (2026 Q4) — "Mature"

| Goal | Tracking | Note |
|------|----------|------|
| Finish #430's transition steps 1, 2, 4, 5, 6 | #488 and children | The order is in #488; step 1 is cheap and stops the old topology re-anchoring |
| Parity as a *release gate*, not a manual check | #507, tunaos#1270 | Per-edition package sets make the variant admission gate mechanisable |
| Sign every published artifact (RPM/DEB + SBOM attestation) | tunaos#1187 | Ties to the tunaOS Q4 supply-chain goal |
| Package signing key rotation + disaster-recovery docs | INCIDENT-repo-wipe-gnome.md | — |

---

## Technical Debt Backlog

| Item | Issue | Priority | Effort |
|------|-------|----------|--------|
| Hummingbird cell exceeds the 6-hour job ceiling | #412, #401 | P0 | L |
| Desktop parity measured by image size, which demonstrably misleads — needs per-edition package sets | #507 | P1 | M |
| Dormant pre-factory builders still in tree (`build-distributed.yml`, ~1.4K lines) | #487 | P1 | M |
| Determinism substrate unverified — `SOURCE_DATE_EPOCH` and cache-key bugs caught by log-reading | #486, #477 | P1 | M |
| Mock CI depends on a personal unpinned COPR | #391 | P1 | S |
| COPR bootstrap infra to retire | #439, COPR-AUDIT.md | P2 | M |

---

## How to Contribute

See [CONTRIBUTING.md](./CONTRIBUTING.md) and [docs/PACKAGE_FACTORY.md](./docs/PACKAGE_FACTORY.md)
for how packages move through the repo. Pick an issue from the priorities above
or comment on a goal you would like to own. The RFC 011 conversion ledger
(#426, `docs/rfc011-conversions.md`) is the most self-contained entry point:
each row is one target family, measurable on its own.

---

## Roadmap Governance

This roadmap is maintained by the strategist agent. Updates are published after
major milestones or quarterly. Propose changes via PR to this file with an issue
reference.

**Currency rule** (#506): a tracker cited in this file that closes must move its
row in the same PR, or the row must name a successor tracker. This repo closes
issues faster than a quarterly cadence can track — the 08-10 revision of this
file reported six closed trackers as open work.

See [SECURITY.md](./SECURITY.md) for vulnerability reporting.

---
*Generated by strategist agent at ACMM L6. Updated 2026-08-23.*
