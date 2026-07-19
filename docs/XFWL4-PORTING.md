# Porting Wayland XFCE to every TunaOS base

TunaOS must not ship X11 on any image. Today xfce is X11 everywhere except
EL10. This is the survey of what each ecosystem actually needs, measured
against the real base images rather than assumed.

## The finding

**Every distro needs exactly one package: `xfwl4`.** Nothing else.

The reason is XFCE 4.20, which added upstream Wayland support. Every base we
ship already has 4.20 or newer, and their `xfce4-panel` already links
`libgtk-layer-shell` and `libwayland-client`. The greeter stack
(`greetd` / `gtkgreet` / `cage`) is packaged in every one of them too.

So this is not "port a 20-package desktop stack to five ecosystems", which is
what EL10 required and what it looked like from the outside. EL10 is the
outlier: it ships essentially no XFCE at all, so `build-order-xfce.yml` builds
the whole stack. Everywhere else, rebuilding those packages would ship
worse-tested duplicates of what the distro already maintains.

`xfwl4` is the gap because it is a young Rust/Smithay compositor that only
Gentoo and AUR have picked up.

## Survey

Measured from the base images in `.github/build-config.yml` (tunaOS repo).

| Base | Variant(s) | XFCE | panel is Wayland-capable | greetd | gtkgreet | cage | rust | **xfwl4** |
|---|---|---|---|---|---|---|---|---|
| Fedora 44 | bonito, bonito-rawhide | 4.20.3/4.20.7 | ✅ | 0.10.3 | 0.8 | 0.3.1 | 1.96 | ❌ **build** |
| Debian trixie | flounder | 4.20.2/4.20.4 | ✅ | 0.10.3 | 0.8 | 0.2.0 | 1.85 | ❌ **build** |
| Debian sid | flounder-sid | ≥ trixie | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ **build** |
| Ubuntu resolute | grouper | 4.20.4/4.20.7 | ✅ | 0.10.3 | 0.8 | 0.2.1 | 1.93 | ❌ **build** |
| Arch | marlin | 4.20.4/4.20.7 | ✅ | 0.10.3 | `greetd-gtkgreet` 0.8 | 0.3.1 | 1.97 | ⚠️ AUR `xfwl4-git` |
| openSUSE TW | sailfin | 4.20.4/4.20.7 | ✅ | 0.10.3 | 0.8 | 0.3.1 | 1.97 | ❌ **build** |
| Gentoo | guppy | 4.21.2 | ✅ | in tree | 0.8 | in tree | ✅ | ✅ **`xfce-base/xfwl4` 4.21.0** |
| EL10 | yellowfin, albacore, skipjack | ✗ none | — | COPR | packaged here | base | ✅ | ✅ packaged here |

"panel is Wayland-capable" = `xfce4-panel` declares a dependency on
gtk-layer-shell **and** wayland-client, verified per base:

- deb: `apt-cache depends xfce4-panel` → `libgtk-layer-shell0`, `libwayland-client0`
- Arch: `pacman -Si xfce4-panel` → `gtk-layer-shell`
- openSUSE: `zypper info --requires` → `libgtk-layer-shell.so.0`, `libwayland-client.so.0`
- Fedora: `dnf repoquery --requires` → same two

## Work per ecosystem

Ordered by leverage. User-facing X11 exposure today is **bonito (+rawhide)** and
**flounder**; grouper/marlin/flounder-sid/sailfin are experimental per
tunaOS#641, so they are not shipping X11 to users yet.

### 1. Gentoo (guppy) — zero packaging

`xfce-base/xfwl4` 4.21.0 is already in the official Portage tree. Its
`keywords` are empty, meaning unkeyworded, so it needs an entry in
`package.accept_keywords` to install. That is a manifest change in the tunaOS
repo, not work here.

Note guppy currently has **no xfce flavor at all** (base/gnome/kde), so this is
adding a flavor rather than de-X11-ing one.

### 2. Fedora (bonito, bonito-rawhide) — reuse the RPM we have

`build-order-xfce-fedora.yml` + `mock/fedora-44-ci.cfg` already exist. One
package, one tier. Blocked only on `build-xfce-distributed.yml`, which still
hard-codes the centos-stream-10 mock runner and per-tier job blocks.

### 3. openSUSE (sailfin) — reuse the RPM, adjust macros

Same spec, different macros. Expect to differ on: `BuildRequires` names
(`pkgconfig(...)` style is portable, bare `-devel` names are not),
`%license` handling, and the `%{?rhel}` conditional which must not fire.
Skeleton: `packaging/opensuse/`.

### 4. Debian + Ubuntu (flounder, flounder-sid, grouper) — one `.deb` source

All three share one source package. Skeleton: `packaging/debian/`.

### 5. Arch (marlin) — PKGBUILD

AUR `xfwl4-git` exists and tracks git rather than the 4.21.0 release. Prefer our
own PKGBUILD pinned to the same commit the RPM uses, so all variants ship the
identical compositor. Skeleton: `packaging/arch/`.

## What makes xfwl4 harder than a normal Rust package

These constraints come from `xfwl4.spec` and apply to **every** ecosystem, so
each packaging skeleton has to solve them again:

1. **`resources/xfce-wayland-protocols` is a git submodule.** It holds custom
   XFCE Wayland protocol XML and is *not* in the release tarball. The build
   references it by relative path, so it must be unpacked to exactly
   `resources/xfce-wayland-protocols/`.

2. **Cargo dependencies must be vendored.** `Cargo.toml` pulls `smithay` from
   git, which cargo cannot fetch in a network-isolated build. The RPM uses a
   pre-vendored `vendor.tar.gz` plus a `.cargo/config.toml` that redirects both
   crates.io *and* the smithay git source to it. Debian and Arch builds are
   also network-isolated by policy, so both need the same treatment.

3. **An upstream patch is required.** `WlrBufferConstraints.dma`'s cfg gate
   omits the udev feature while three call sites guard it under udev — a
   udev-only build (ours) fails to compile without
   `0001-fix-dma-cfg-gate-for-udev-backend.patch`.

4. **Feature flags are not default.** Build with
   `--no-default-features --features udev,egl,xwayland,smithay/renderer_pixman,smithay/renderer_gl`.

5. **`GETTEXT_SYSTEM=1` must be set.** Otherwise `gettext-sys`'s build.rs
   compiles its own GNU gettext, which then fails to link against
   `libintl_gettext`. On glibc targets gettext is in libc, so no linking is
   needed at all.

6. **`RUSTFLAGS="-C relocation-model=pic"`.**

## Status

Skeletons in `packaging/` are **scaffolds, not working builds** — they encode
the constraints above and the dependency names, and every one of them still
needs a real build to be trusted. None has been built yet.
