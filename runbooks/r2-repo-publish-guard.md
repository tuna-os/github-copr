# Runbook: R2 repo publish workflow wipes production packages

## When to use this

A publish or build workflow that runs `rclone sync <local> r2:<bucket>/<path>/`
against a production repo path shows one of:

* `repomd.xml` / `Release` at `repo.tunaos.org/<path>/` now advertises 0
  packages, or 404s where it used to 200.
* A published repo's package count drops sharply between two runs of the
  same workflow, with no corresponding package removal in this repository.
* The `R2 Inventory` workflow (`.github/workflows/r2-inventory.yml`, manual
  dispatch, read-only) reports 0 objects under a prefix that should be
  populated.

## Why this happens

`rclone sync SRC DST` makes `DST` match `SRC` exactly, deleting anything in
`DST` that isn't in `SRC`. Every publish path in this repo works by:

1. syncing the current production repo *down* into a local working tree,
2. adding/updating packages and regenerating repo metadata locally,
3. syncing the local tree back *up* over production.

If step 1 silently fails or is skipped (network blip, credential issue, a
change-detection filter that matches zero packages, a swallowed `|| true`),
step 3 syncs a near-empty local tree over the real thing and deletes it.
This exact chain caused two production incidents — see
`INCIDENT-repo-wipe-gnome.md` (2026-07-27) and the referenced 2026-07-19 XFCE
incident (fixed in `f877c83`, PR #99).

## Immediate triage

1. Confirm the blast radius with the read-only `R2 Inventory` workflow
   (`.github/workflows/r2-inventory.yml`) — it only lists objects, it never
   writes, so it's always safe to run against production.
2. Check whether the affected prefix is actually consumed by an image build
   (search `manifests/` and the desktop build scripts). A prefix with no
   image-build consumer is a data-loss bug but not a build outage — prioritize
   accordingly, per the precedent in `INCIDENT-repo-wipe-gnome.md`.
3. Identify the run that caused the drop from the workflow's run history —
   compare `repomd.xml`'s `<revision>` timestamp (or the Deb `Release`
   file's `Date:`) against run start times.
4. There is no soft-delete on the R2 side for these buckets. Recovery means a
   full rebuild of the affected chain, not a restore.

## Preventing this in a given workflow

Every workflow that ends in `rclone sync <local> r2:...` (never `rclone
copy`, which is additive) must have both of these gates before that call:

1. **Sync-down must fail loud.** The step that seeds the local tree from R2
   must check its own exit code and `exit 1` on failure, not swallow it with
   `|| true`. A failed seed and an empty-because-nothing-changed seed must
   not be indistinguishable.
2. **Refuse to publish empty.** Immediately before the final `rclone sync`
   up, count the packages in the local tree (RPMs excluding `.src.rpm`, or
   `.deb`s) and `exit 1` with an `::error::` annotation if the count is 0.

Grep for the current set of workflows that sync to R2 and confirm each one
has both gates:

```
grep -rl 'rclone sync' .github/workflows/
```

`build-distributed.yml`, `publish-tideforge-rpms.yml`,
`publish-tideforge-debs.yml`, `publish-tideforge-arch.yml`, and
`publish-build-chain-rpms.yml` carry both gates today — use their "Refuse to
publish an empty result" / sync-down `rc` check steps as the template for any
new or modified publish workflow.

## Related

* `INCIDENT-repo-wipe-gnome.md` — full root-cause writeup for the GNOME 49/50
  wipe this runbook generalizes from.
* `.github/workflows/r2-inventory.yml` — read-only bucket listing, safe to
  run any time.
