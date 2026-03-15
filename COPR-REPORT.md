# GNOME 50 COPR Project Report: `jreilly1821/c10s-gnome-50`

This report details the origin and status of all packages currently tracked in the COPR project.

## 1. Custom / Manually Created Packages
*Built from local sources and uploaded as SRPMs to COPR.*

| Package Name | Source Path | Description |
| :--- | :--- | :--- |
| `gnome50-el10-compat` | `src/deps/gnome50-el10-compat` | **Custom**: Provides the `systemd-user` PAM workaround for dynamic GDM users. |
| `gi-docgen` | `src/deps/gi-docgen` | **Modified**: Local SRPM used to fix `BuildSystem: pyproject` incompatibility on EL10. |
| `libgexiv2` | `src/deps/libgexiv2` | **Custom**: Backported to resolve Nautilus dependencies. |

## 2. Modified Backports
*Backported from Fedora Rawhide with local patches or configuration changes, built from local `src/` directories.*

| Package Name | Source Path | Status |
| :--- | :--- | :--- |
| `glib2` | `src/gnome-50/glib2` | Built from local SRPM with schema triggers. |
| `selinux-policy` | `src/deps/selinux-policy` | Backported full Rawhide policy. |

## 3. Unmodified Rawhide Builds
*Currently pulling directly from Fedora Rawhide Dist-Git via COPR's `distgit` source type.*

**Tools & Build Deps:**
* `meson`
* `autoconf`
* `blueprint-compiler`
* `docbook-utils`
* `docbook-style-xsl`

**Libraries:**
* `cairo`
* `fontconfig`
* `icu`
* `pango`
* `libadwaita`
* `libei`
* `libxcvt`
* `shaderc`
* `mozjs140`
* `gjs`
* `glycin`
* `libnotify`
* `libldac`
* `gobject-introspection`
* `gsettings-desktop-schemas`
* `tinysparql`
* `localsearch`

**Core Desktop Components:**
* `gdm`
* `gnome-session`
* `gnome-shell`
* `mutter`
* `gtk4`
* `gnome-control-center`
* `gnome-settings-daemon`
* `nautilus`
* `pipewire`
* `xdg-desktop-portal`
* `xdg-desktop-portal-gnome`
* `avahi`
* `umockdev`
* `python-dbusmock`
* `python-smartypants`
* `python-typogrify`
* `wayland-protocols`

## Summary of Infrastructure
* **Project**: [jreilly1821/c10s-gnome-50](https://copr.fedorainfracloud.org/coprs/jreilly1821/c10s-gnome-50/)
* **Chroot**: `epel-10-x86_64`
* **Strategy**: Use Rawhide `distgit` for speed and simplicity where possible; override with local SRPMs only for EL10-specific fixes or dependency resolution issues.
