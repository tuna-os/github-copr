# Gentoo (guppy) — no packaging required

`xfce-base/xfwl4` **4.21.0 is already in the official Portage tree**, so there
is deliberately no ebuild here. Writing one would fork a package Gentoo already
maintains.

Verified via `packages.gentoo.org/packages/xfce-base/xfwl4.json`:

```
atom:     xfce-base/xfwl4
desc:     Xfce's [experimental] Wayland Compositor
version:  4.21.0   keywords: ['']
```

## The one catch: it is unkeyworded

`keywords: ['']` means no arch is keyworded, not even `~amd64`. Portage will
refuse to merge it until it is explicitly accepted, so the tunaOS image build
needs:

```
# /etc/portage/package.accept_keywords/xfwl4
xfce-base/xfwl4 **
```

`**` (rather than `~amd64`) is required precisely because the ebuild carries no
keywords at all.

## Rest of the stack

Gentoo also already has everything else a Wayland-only XFCE session needs —
`gui-apps/gtkgreet` 0.8, `gui-libs/gtk-layer-shell` 0.10.1, and
`xfce-base/xfce4-panel` 4.21.2, which is newer than every other base we ship.

## Note on scope

guppy currently has **no xfce flavor at all** (base/gnome/kde only), so this is
adding a flavor, not de-X11-ing an existing one — no X11 is being shipped here
today.
