# Tooling adapted from sandogasa

[slopfest/sandogasa](https://github.com/slopfest/sandogasa) is a Rust
workspace of Fedora/CentOS/Debian packaging tools (Apache-2.0 OR MIT).
Several of its tools solve, in mature form, problems this factory had
been hitting reactively — each of the adaptations below is pinned to a
factory incident that predates it. The ideas and algorithms were
reimplemented in this repository's Python, not linked as binaries: the
algorithms are small, the factory already parses its own repo metadata,
and a Rust toolchain dependency for CI-side checks would cost more than
it saves.

Licensing: sandogasa is dual-licensed Apache-2.0 OR MIT, which permits
reimplementation and adaptation here; the per-file docstrings record the
origin. Test vectors for the version comparator are carried over
verbatim.

## What was adapted, and from where

| Factory piece | Adapted from | The incident it pins |
| --- | --- | --- |
| `scripts/rpm_vercmp.py` — librpm's rpmvercmp with `~`/`^`, EVR compare, constraint check | `sandogasa-rpmvercmp` crate (vectors carried over) | `FACTORY-STATUS.md` measures presence, not freshness; every version-aware check below needs this primitive |
| `scripts/preflight-buildrequires.py` `version_blocked` | ebranch `BlockedByBase` | libnotify `>= 0.8.7` unsatisfiable on both arches, found by mock 2.5 h in, twice (#480) |
| `scripts/preflight-buildrequires.py` `runtime_unsatisfied` | ebranch `check_installability` | gtkgreet → greetd, xfce4-pulseaudio-plugin → pulseaudio: runtime holes found at clean-install time after a 53-minute build (#480) |
| `scripts/check-published-hygiene.py` | hs-relmon `dupe-subpkgs` + `file-conflicts` | the createrepo_c `--update` stale-entry class (#358); 107 same-NEVRA pairs with differing checksums on xfce/10-stream (#471) |
| `scripts/check-reverse-deps.py` + the NEVER BREAK RDEPS gate in `publish-rpm-wave.sh` | ebranch `check-update` | the gnome50 bootstrap glib2 `Obsoletes` hijacking AppStream (run 32405815822); publishing a libnotify the factory could no longer rebuild |
| `scripts/extract-buildroot-manifest.py` + `scripts/diff-buildroots.py`, recorded per package by `build-chain.sh` into `artifacts/buildroots/` | koji-diff | the #480 libnotify buildroot diagnosis, reconstructed from issue comments when mock's root.log had the answer |
| `scripts/collect-cell-throughput.py` | koji-lag's measure-from-metadata approach | `docs/hummingbird-throughput.md` was a one-off hand scrape (it found concurrency 1.0 with `--jobs 2`); now re-runnable against any cell log |

## Where each runs

- **Preflight** (`preflight-buildrequires.py`): manual gate before
  dispatching a chain; now answers build-time satisfiability, version
  constraints, and runtime installability in one run.
- **Hygiene** (`check-published-hygiene.py`): ad hoc or scheduled;
  reads the same `published_index` contract every buildroot reads, so a
  clean report covers the *combination* of prefixes a buildroot sees.
  First live run found 8 findings: the gtk-layer-shell and xfconf
  families served identically from both el10 prefixes (redundant, not
  shadowing), and hummingbird clean.
- **Reverse-dep gate**: runs inside `publish-rpm-wave.sh` on every
  wave, entirely locally (staged repodata vs the synced-down served
  tree). Differential by design — it reports only what a wave *newly*
  breaks, so system-repo dependencies outside its view are never noise,
  and its blind spots all lean lenient (documented in the script).
- **Buildroot manifests**: opt-in via `BUILDROOT_MANIFESTS`, switched
  on by the cell runner; manifests land in `artifacts/buildroots/` so
  the action cache and success artifact keep the green run's state for
  a later red run to diff against.
- **Throughput**: run by hand against a downloaded cell job log when
  the 6-hour-ceiling work needs numbers.

## What was considered and NOT adapted

Recorded so the next reader does not re-survey the same ground:

- The forge/bureaucracy tooling (Bodhi, Bugzilla, FESCo, Pagure ACLs,
  meetbot, activity reporting) has no counterpart in this factory's
  problem space.
- `dbranch` assumes Debian's dist-git/PPA workflow; the deb side here
  is the backport chain (`backport-deb-chain.yml`), a different shape.
- ebranch's `fedrq` shell-outs were not carried over: the factory
  already parses primary.xml itself, and a run-time dependency on a
  Fedora-packaged query tool would not work in the deb and arch legs.
- koji-lag's SQLite store is the right shape if throughput collection
  ever becomes scheduled; for on-demand use, stateless parsing of one
  log is enough and simpler.
