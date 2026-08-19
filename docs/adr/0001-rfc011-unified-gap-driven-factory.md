# ADR 0001: One gap-driven factory (RFC 011)

- Status: accepted
- Date: 2026-08-18
- RFC: [docs/rfc/rfc011-unified-gap-driven-factory.md](../rfc/rfc011-unified-gap-driven-factory.md)
- Tracking issue: [#418](https://github.com/tuna-os/tunaos-packages/issues/418)
- Sign-off: hanthor (maintainer), 2026-08-18
- Policy: tunaOS RFC lifecycle (tunaOS `docs/RFC-PROCESS.md`, ADR 0004) —
  this is the ADR the merge gate requires; it is also this repository's
  first ADR.

## Context

The factory is five workflow families organized by the crisis that created
each one, each hand-carrying its own build ordering, repo generation,
publish gating, and drift handling. The measured cost is structural
copy-paste drift — the `createrepo_c --update` class (#358) was fixed in
one copy while latent in others (audited in #421) — plus hand-curated build
orders that rot (hummingbird's said 1248 sources; the measured runtime gap
was 673) and a sourcing policy ("system repos first") that no family except
hummingbird's actually executes as a query.

## Decision

**Adopt RFC 011, option C:** one catalog (`manifests/catalog.yaml`) owns
package identity; a generalized, target-parameterized gap engine
(`scripts/measure-target-gap.py`, the proven hummingbird machinery) computes
per-target build orders against live repo indexes with revision-gated drift
PRs; one unified format-agnostic factory (`package-factory.yml` planner +
`package-factory-cell.yml` boundary, landed in #430) replaces the hand-copied
families — amending the originally-proposed per-format orchestrators.
Packaging payloads stay heterogeneous — Tideforge recipes where
they are proven, native EL10 specs where the TIDEFORGE-READINESS verdict
says there is nothing to switch.

**Considered options:**

1. **Status quo plus discipline** — rejected: #358 is the measured proof the
   discipline does not hold across copies.
2. **Rewrite everything into Tideforge recipes** — rejected by the
   TIDEFORGE-READINESS evidence: the EL10 GNOME bootstrap needs scriptlets,
   file triggers, SELinux policy, and bootstrap variants a simple recipe
   format is designed to exclude.
3. **Catalog + gap engine + orchestrator, heterogeneous payloads** — chosen;
   nothing working is rewritten.

## Consequences

- Phases 0–3 land independently, each a safe stopping point; Phase 0
  (catalog + completeness tests) changes no CI behavior.
- Success criteria: #358's class cannot recur; a distro catching up produces
  a PR that removes work automatically; a new (package × target) is a
  catalog entry, not a workflow; the exceptions table cannot silently grow.
- Automated R2 promotion stays out of scope and requires its own RFC with
  the `INCIDENT-repo-wipe-gnome.md` safeguards.
