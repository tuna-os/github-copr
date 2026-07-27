# Incident: published GNOME 49/50 EL10 repos wiped to 0 packages

Status: root cause confirmed, fixes in progress. Repo restore NOT yet done.

## Current production state (verified 2026-07-27 by HTTP probe)

| URL | Result |
| --- | --- |
| `repo.tunaos.org/gnome50/10-stream-x86_64/repodata/repomd.xml` | 404 |
| `repo.tunaos.org/gnome50/10-x86_64/repodata/repomd.xml` | 404 |
| `repo.tunaos.org/gnome49/10-stream-x86_64/repodata/repomd.xml` | 200, but `primary.xml` says `packages="0"` |
| `dev.repo.tunaos.org/gnome{49,50}/...` | 404 (host serves nothing at all) |

**GNOME 49 is confirmed empty**: its `repomd.xml` survived and its `primary.xml` reports
`packages="0"`. That is an authoritative statement from the repo's own metadata.

**GNOME 50 is unconfirmed.** Spot-probed `gnome-shell-50.0-3.el10.x86_64.rpm`,
`mutter-50.0-4.el10.x86_64.rpm`, `glib2-2.88.0-4.el10.x86_64.rpm` and
`gnome50-el10-compat-1.2.7-1.el10.noarch.rpm` at the repo root and under `Packages/`
and `x86_64/`: all 404. **This is weak evidence** — those NEVRAs were read out of a
`verify-gdm-copr` log, i.e. they came from `copr:jreilly1821/c10s-gnome-50`, not from
R2, and may never have existed in `bluefin/gnome50/` under those exact names. Absence of
`repodata/repomd.xml` proves the metadata is gone, not that the RPMs are.

An authoritative answer needs a bucket listing, which requires R2 credentials. Two ways:

* Run the read-only `R2 Inventory (read-only)` workflow (`.github/workflows/r2-inventory.yml`,
  added for this): `gh workflow run r2-inventory.yml`. It uses the existing repo secrets,
  only ever calls `rclone lsf`/`lsd`, and prints per-prefix RPM counts to the run summary.
* Or locally, with credentials configured: `rclone lsf r2:bluefin/gnome50/10-stream-x86_64/ | head`

**Do not decide between "full rebuild" and "createrepo_c re-index" until that listing
exists.** If RPMs survived, re-indexing is far cheaper than a full chain rebuild.

## Root cause — same bug as the 2026-07-19 XFCE incident (fixed in f877c83, PR #99)

`f877c83` fixed this exact class of bug in `build-xfce-package.yml` only. The GNOME 49,
GNOME 50, and distributed workflows were never given the same treatment, so the bug
was still live in them.

Two independent defects, both still present:

### 1. Change detection matches directories with no RPM spec

`build-gnome50-package.yml:45-48` (and the gnome-49 equivalent):

```bash
git diff --name-only "${BASE}" "${HEAD}" | grep '^src/gnome-50/' | sed 's|/[^/]*$||' | sort -u
```

Any changed file counts as a "package" by stripping its last path component, with no
check that a `.spec` actually lives there. `f877c83` added exactly that `.spec` guard to
the XFCE workflow; GNOME never got it.

### 2. No guard stops an empty `local-repo` from reaching `rclone sync`

`build-gnome50-package.yml:144` / `build-gnome49-package.yml:149`:

```bash
rclone sync local-repo/ "r2:${R2_BUCKET}/${R2_REPO_PATH}/"
```

`rclone sync` makes the destination match the source **exactly**. If `local-repo`
holds only freshly-generated repodata, this deletes every published RPM. The seed step
above it (`rclone sync ... local-repo/ ... || true`) swallows its own failure, so a
failed seed silently produces the empty `local-repo` that then wipes production.

### Confirmed trigger for GNOME 49

Run `28668672883` — `main` push, commit "Merge pull request #66 …", 2026-07-03,
duration 2m22s. Matrix cell: **`build (src/gnome-49/avahi/tests)`** — a `tests/`
directory, not a package. Timeline inside the job:

```
15:06:40  rclone sync r2:bluefin/gnome49/10-stream-x86_64/ local-repo/ --exclude repodata/** || true
15:06:42  createrepo_c --update local-repo
15:06:42  rclone sync local-repo/ r2:bluefin/gnome49/10-stream-x86_64/
```

Two seconds end to end — nothing was pulled, nothing was built, and the empty result
was synced over production. The surviving `repomd.xml` carries
`<revision>1783091202</revision>` = **2026-07-03 15:06:42 UTC**, matching this run to
the second.

GNOME 50 has no surviving `repomd.xml` at all, so it cannot be dated the same way, but
it has the identical unguarded workflow.

## Secondary defect: the promote pipeline is destructive and its gate is fake

`promote-to-prod.yml` / `promote-gnome49-to-prod.yml`:

```bash
rclone sync "r2:tunaosdev/gnome50/10-stream-x86_64/" "r2:bluefin/gnome50/10-stream-x86_64/"
```

* **Nothing in this repository ever writes to the `tunaosdev` bucket.** Every build
  workflow sets `R2_BUCKET: bluefin` and publishes straight to production. `dev.repo.tunaos.org`
  404s, consistent with an empty dev bucket.
* Syncing an empty source over production deletes it. This ran ~15 times on 2026-07-26.
* The gate that fires it is broken. `build-gnome50-verify.yml:5` waits on a workflow named
  `"GNOME 50 Distributed Build and Publish"`, **which does not exist** — the only distributed
  workflows are `build-gnome49-distributed.yml`, `build-xfce-distributed.yml`, and
  `build-distributed.yml` ("Distributed Build and Publish RPMs"). So the only live trigger is
  `pull_request`, on which both real verify jobs are gated off by
  `if: workflow_run.conclusion == 'success' || workflow_dispatch`:

  ```
  verify-repo      | skipped
  verify-gdm       | skipped
  verify-gdm-copr  | success   <- tests COPR, not the repo
  ```

  A COPR-only job reports the workflow green, that green fires promote, promote wipes
  production, and promote's own 404 check then catches the damage it just caused. That is
  the entire wall of red on `main`.

GNOME 49 escaped this second mechanism only because its verify never reached `success`,
leaving its (identically destructive) promote job skipped. It had already been wiped by
defect #1 three weeks earlier.

## Decisions taken

* Drop the fake dev→prod promotion entirely. Builds already publish directly to `bluefin`;
  that is the de-facto design. Delete both promote workflows.
* Port the `f877c83` anti-wipe pattern (spec-check in change detection, `rclone copy` seed,
  build-start marker, hard refuse-to-publish-empty guard) to every workflow that syncs to R2.
* Restore of repo contents is a separate, explicit action against production and is not
  bundled with the CI fix.

## Fixes applied

| File | Change |
| --- | --- |
| `build-gnome49-package.yml`, `build-gnome50-package.yml` | `.spec` check in change detection; seed via `rclone copy` with the `\|\| true` removed; `build-start-marker`; sign scoped to this run's output; hard refuse-to-publish-empty guard before the sync |
| `build-distributed.yml` | refuse-to-publish-empty guard before its two `rclone sync` calls |
| `promote-to-prod.yml`, `promote-gnome49-to-prod.yml` | deleted — they synced from a bucket nothing writes to |
| `build-gnome50-verify.yml` | `workflow_run` retargeted from the nonexistent `"GNOME 50 Distributed Build and Publish"` to `"GNOME 50 Package Build (Incremental)"` |
| `build-gnome49-verify.yml`, `build-gnome50-verify.yml` | `dev.repo.tunaos.org` → `repo.tunaos.org` (the dev host serves nothing) |
| `r2-inventory.yml` | new, read-only, manual-dispatch bucket listing |

Verified locally: the change-detection filter given
`src/gnome-49/avahi/tests`, `src/gnome-49/avahi`, `src/gnome-49/nonexistent`
returns `["src/gnome-49/avahi"]` — it rejects the exact directory that caused the wipe.
`actionlint` reports nothing new on the changed files; `pytest tests/` is 62 passed.
