# Targeting Hummingbird

What "build for Hummingbird" means in this repository, stated once with the
measurements behind it, so the same facts stop being re-derived from
version strings.  Written 2026-09-02 after comparing this factory with
[projectbluefin/utah-packages](https://github.com/projectbluefin/utah-packages),
which built GNOME 51 for Hummingbird in a fraction of the time this
repository has spent on it.  Every number below came out of a real
`primary.xml`; the reproduction is
`scripts/check-hummingbird-installability.py` and
`scripts/gap_engine.py --catalog manifests/hummingbird-desktops.yaml`.

**Hummingbird's own documentation is authoritative** over anything here.
When the two disagree, theirs wins and this file is the bug
(<https://hummingbird-project.io/docs/>, <https://gitlab.com/redhat/hummingbird>).

## 1. What Hummingbird is, by ABI

Indexes read 2026-09-02, x86_64 (`primary.xml` sha256 prefixes:
public-hummingbird `5c75eb01881b`, Fedora 44 `c48e47563bbf`, Rawhide
`8daf5868c675`):

| package | hummingbird | fedora 44 | rawhide |
|---|---|---|---|
| glibc | 2.43-8.4.hum1 | 2.43-2.fc44 | 2.44.9000-1.fc46 |
| openssl-libs | 3.5.8-0.1.hum1 (`libcrypto.so.3`) | 3.5.5-1.fc44 (`.so.3`) | 4.0.2-1.fc46 (**`.so.4`**) |
| python3 | 3.14.7-1.hum1 | 3.14.3-2.fc44 | 3.15.0~rc1-1.fc45 |
| perl-libs | 5.42.2-525.hum1 | 5.42.1-523.fc44 | 5.44.0-527.fc45 |
| libxml2 | 2.15.3-0.1.4.hum1 | 2.12.10-6.fc44 | 2.13.9-4.fc45 |
| glib2 | 2.89.3-1.hum1 | 2.88.0-1.fc44 | 2.89.4-1.fc46 |
| harfbuzz | 14.3.1-1.hum1 | 12.3.2-1.fc44 | 14.4.0-1.fc46 |

Two things are true at once, and the 2026-08-06 measurement
(`docs/hummingbird-desktop-gap.md`, Finding 1) saw only the first:

- The packages Hummingbird **rebuilds** (glib2, harfbuzz, gcc, rust, meson)
  are at Rawhide's versions.  That is why "30 of 38 core packages match
  Rawhide" was a true sentence.
- The packages that **define the ABI** -- glibc, openssl, python, perl -- are
  Fedora 44's.  Hummingbird is an overlay of rebuilt packages on a pinned
  Fedora release; its own container repository maps the "rawhide" variant to
  `fedora-44.repo` (`redhat/hummingbird/containers`, `images/variables.yml`),
  and its `mock/mock.cfg` composes the build root from that release's
  repositories with the Hummingbird Pulp repos shadowing them by priority.

So the build root is **Fedora 44 plus public-hummingbird at higher
priority**.  That is what Hummingbird builds in, what utah-packages builds
in, and -- since 2026-09-02 -- what `mock/hummingbird-ci*.cfg` builds in.

## 2. What the Rawhide root cost

The Rawhide root was not a harmless approximation.  Read off our own
published prefix, `repo.tunaos.org/hummingbird/20251124-x86_64` (index
`dacef1b3b4c9…`, 8738 binaries):

```
libm.so.6(GLIBC_2.44)(64bit)   needed by gstreamer1-plugins-good, libavutil-free, zvbi
```

Those three were built, signed, published, and cannot install on the target
they were built for: Hummingbird's glibc is 2.43.  utah-packages hit the
same class one soname over (`gnome-shell` built on Rawhide needing
`libcrypto.so.4`) and documented it as the reason for the Fedora 44 root.
The three interpreter pins the old config carried (`[fedora-44-python]`,
`[fedora-44-perl]`, `[fedora-44-mpich]`, each an `includepkgs` list) were
patching Fedora 44 back in one namespace at a time, and each said "remove
when Hummingbird catches up with Rawhide".  It was never going to.

## 3. Does what we publish resolve on Hummingbird?

The question a consumer image asks, and the one utah-packages gates its
publish on (it runs the consumer transaction inside the bootc-os image with
only Hummingbird and its factory enabled).  Static answer, 2026-09-02, roots
from `manifests/hummingbird-desktops.yaml`, closure over
public-hummingbird ∪ the named repository, nothing pre-installed:

| repositories enabled | gnome roots absent | closure | unresolved capabilities |
|---|---|---|---|
| hummingbird alone | 53 of 58 | 94 | 5 |
| hummingbird + **utah-packages** (Pages mirror, 421 binaries) | 33 | 208 | 185 |
| hummingbird + **tunaos-hummingbird** (8738 binaries) | 3 | 602 | **30** |
| hummingbird + Fedora 44 (if a consumer enabled it) | 0 | 695 | 0 |

Per desktop, against our prefix: gnome 30 unresolved, kde 25, cosmic 9,
niri 28, xfce 18 -- **no desktop is resolvable today**, and the blockers are
concrete (`scripts/check-hummingbird-installability.py` prints them):

- the GLIBC_2.44 leak above (gnome, kde, cosmic all reach it);
- `gdm` requires `gnome50-el10-compat`, an EL10-only package, because
  `src/gnome-51` is a byte copy of `src/gnome-50` (#537);
- `gtk4` requires `libgstplay-1.0.so.0` and nothing ships
  `gstreamer1-plugins-bad-free` (#540);
- libraries the closure needs and the chain has not produced: libcanberra,
  evolution-data-server (`libecal`, `libedataserver`), webkitgtk6.0,
  libosinfo, samba (`libsmbclient`), udisks2, libvorbis, poppler-data;
- roots in neither repository: `fprintd-pam`, `gnome-disk-utility`,
  `gnome-user-share`.

Two readings of that table matter more than the counts.  First, the
utah-packages row is **not** evidence that utah's approach fails: its Pages
mirror lags the OCI image utah consumes, and its consumer contract is
Bluefin's list, not this catalog's 58 roots.  Second, the Fedora 44 row is
the shape of the shortcut: a Hummingbird image that enabled Fedora 44
would resolve GNOME 50 entirely, modulo the name conflicts the walk cannot
see (`libxml2` 2.12 vs 2.15 under one name).  This factory exists because
consumer images do not enable Fedora 44; that row is the ceiling, not the
plan.

`scripts/check-hummingbird-installability.py` runs daily
(`.github/workflows/hummingbird-installability.yml`), advisory, per arch.
It becomes a gate the day a desktop first resolves.

## 4. What utah-packages does differently, and what this repository took

| | utah-packages | tunaos-packages before | after 2026-09-02 |
|---|---|---|---|
| build root | Fedora 44 + public-hummingbird (priority) | Rawhide + hummingbird + three F44 pins | Fedora 44 + public-hummingbird + our prefix |
| recipes | Rawhide dist-git, pinned by commit | Rawhide dist-git, imported at build time | unchanged |
| sources | upstream release tarballs, SHA-512 locked | dist-git lookaside | unchanged (see §6) |
| what gets built | a hand-curated, dependency-first list (193 sources) | the measured runtime closure (670 sources, 18 tiers) | unchanged (see §5) |
| staging | 5 stages, each a local repo for the next | tiers over one topological order, `[local-build]` | unchanged |
| disttag | `.hum1.bfin` (sorts above `.hum1`) | `.bfin1` (sorts below `.hum1`) | unchanged, deliberate: a rebuild never shadows the base |
| publish | OCI image, consumed with `COPY --from` by digest | R2 prefix behind a Worker | unchanged |
| **installability gate** | dnf transaction inside the bootc-os image before publish | none | static checker, daily; container gate is the next step |
| preflight | resolves every recipe's BuildRequires in the real root, as a worklist | `scripts/preflight-buildrequires.py` exists | unchanged |

The root and the gate are the two that decide whether output is usable.
The rest is scope.

## 5. Why the gap did not shrink when the reference moved

An obvious hypothesis was that measuring the closure against Rawhide
inflated it.  Measured, same day, same roots:

| reference | gnome sources to build | kde | cosmic | niri | xfce |
|---|---|---|---|---|---|
| Rawhide (committed) | 301 | 375 | 175 | 297 | 268 |
| Fedora 44 | 311 | 378 | 152 | 306 | 256 |

No.  The closure is what the roots need that Hummingbird does not ship, and
Hummingbird ships no desktop stack at all; every cairo, gdk-pixbuf and
pipewire is a gap whichever Fedora you read the Requires: from.  The
reference stays Rawhide, because the recipes are Rawhide's and Rawhide's
binary index is the closest proxy for what those recipes produce.

What utah-packages did about the size was not a measurement trick.  It
built a *narrower contract* -- one desktop, Bluefin's list -- and it built
it in the right root, so what came out installed.  This catalog declares
five desktops; that is a scope decision for the maintainer, and §7 makes
the case.

## 6. Open, and deliberately not asserted

- **Rawhide recipes on a Fedora 44 root will hit version floors.**  Rawhide
  specs BuildRequire what Rawhide has.  The toolchain floors are covered --
  Hummingbird itself ships gcc 16, rust 1.97, meson 1.11 at priority 10 --
  but library floors (utah met `pango >= 1.58`, `wayland-protocols >=
  1.48`, `gsettings-desktop-schemas >= 51.alpha`) will surface as
  `preflight-buildrequires.py` findings and become build-order entries.
  That is the expected cost, and it is the cost utah paid.
- **The three GLIBC_2.44 packages must be rebuilt**, and the prefix should
  be re-verified for any other symbol-version leak (`GLIBC_2.44`,
  `OPENSSL_3.5`+, `libpython3.15`).  The checker's `needer_from:
  published` column is the list.
- **Name masking is the overlay's inherent cost.**  dnf's priority filter
  drops a *name* from every lower-priority repo, so a Fedora 44 package that
  needs a library the base ships under the same name at a different soname
  cannot resolve: F44 `fontforge` wants `libxml2.so.2`, the base's
  `libxml2` 2.15 provides `.so.16`, and F44's `libxml2` is never a
  candidate.  The old `includepkgs` list handled four such names by keeping
  them *out*; the answer per package is the same either way -- exclude the
  Fedora name or build the package against the base -- and it is a
  per-package decision, not a global list.  utah-packages carries exactly
  this list as `HB_EXCLUDE` (libicu, ruby-default-gems, gpgme, qt6-qtbase).
- **Upstream sources.**  utah's direct-source model (fetch the release
  tarball, verify SHA-512, fail closed) is the Hummingbird project's own
  freshness model; this repository still builds from dist-git lookaside.
  Not changed here; it is orthogonal to whether output installs.
- **The container gate.**  The static checker cannot judge version
  constraints or conflicts.  The next step is utah's step verbatim: run the
  catalog's roots through `dnf --assumeno install` inside
  `quay.io/hummingbird-community/bootc-os` with only public-hummingbird
  and our prefix enabled, in `verify-package-factory-cell.sh`, and refuse
  to publish a wave that regresses it.

## 7. The decision this measurement asks for

tunaOS's hummingbird images consume `ghcr.io/projectbluefin/common` and
`ghcr.io/ublue-os/brew` by digest today.  `ghcr.io/projectbluefin/utah-packages`
is published the same way, is Bluefin's GNOME 51 for Hummingbird, and is
built by the project tunaOS is derived from.  Building a second GNOME 51 for
the same base, in this repository, on a smaller team, is the part of the
plan that has not been paying back.

Proposed split, for the maintainer to decide (tracked in the issue that
accompanies this document):

- **GNOME on hummingbird: consume utah-packages.**  tunaOS's
  `manifests/desktops/gnome.yaml` hummingbird section points at the OCI
  repository by digest; `src/gnome-51` here stops being a second copy.
- **This factory builds what utah does not:** the KDE, COSMIC, Niri and
  XFCE stacks for Hummingbird, in the Fedora 44 root, gated on
  installability -- the same shape, one desktop at a time, dependency-first.
- **Both factories share the base-image audit** (`components:` in the
  catalog) so a package neither builds is a named gap, not a surprise.

That is the model utah-packages proved: right root, one contract, a gate
that asks the consumer's question.  Not a bigger build order.
