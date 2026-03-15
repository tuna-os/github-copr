# COPR Package Audit

Generated: 2026-03-14

## Summary

- **Total packages in COPR**: 57
- **Using Fedora dist-git rawhide (no local spec)**: 37 — can rebuild with `copr-cli rebuild` or distgit trigger
- **Using local/modified spec (SCM or SRPM upload)**: 12 packages with local specs that diverge from rawhide
- **Custom packages not in Fedora**: 2 (`gnome50-el10-compat`, `selinux-policy` as custom build)
- **Obsolete/stale local specs** (have local spec but COPR uses distgit): 7 — local specs exist in the repo but COPR is already pointed at distgit rawhide; the local specs may be outdated

---

## COPR Source Type Reference

| Source Type | Meaning |
|-------------|---------|
| `distgit` + `rawhide` | COPR pulls directly from Fedora dist-git rawhide — no local spec needed |
| `scm` + `main` | COPR pulls from our GitHub repo's `main` branch |
| `upload` | SRPM was uploaded manually — local spec was used to produce the SRPM |

---

## Packages Using Fedora Dist-Git Rawhide (No Local Spec Needed)

These 37 packages are already set to `distgit rawhide` in COPR and build directly from Fedora's dist-git. They do **not** require a local spec in this repo.

| Package | COPR Source | Notes |
|---------|-------------|-------|
| meson | distgit/rawhide | Pure Python noarch build tool |
| autoconf | distgit/rawhide | Has local spec in `src/deps/autoconf/` — SUPERSEDED by distgit |
| libldac | distgit/rawhide | Audio codec library; has local spec but COPR uses distgit |
| python-smartypants | distgit/rawhide | gi-docgen dep |
| python-typogrify | distgit/rawhide | gi-docgen dep |
| wayland-protocols | distgit/rawhide | Has local spec in `src/deps/wayland-protocols/` — SUPERSEDED |
| libxcvt | distgit/rawhide | Has local spec in `src/deps/libxcvt/` — SUPERSEDED |
| shaderc | distgit/rawhide | Has local spec in `src/deps/shaderc/` — SUPERSEDED |
| umockdev | distgit/rawhide | Has local spec in `src/deps/umockdev/` — SUPERSEDED |
| python-dbusmock | distgit/rawhide | Has local spec in `src/deps/python-dbusmock/` — SUPERSEDED |
| gi-docgen | distgit/rawhide | **But** local spec diverges significantly — see below |
| avahi | distgit/rawhide | Has local spec in `src/deps/avahi/` — SUPERSEDED |
| blueprint-compiler | distgit/rawhide | No local spec |
| gdm | distgit/rawhide | **But** local spec adds `Requires: gnome50-el10-compat` — see below |
| gnome-session | distgit/rawhide | No local spec |
| gnome-control-center | distgit/rawhide | Has local spec in `src/gnome-50/gnome-control-center/` — SUPERSEDED |
| xdg-desktop-portal-gnome | distgit/rawhide | **But** local spec expands meson macros manually — see below |
| cairo | distgit/rawhide | Has local spec in `src/deps/cairo/` — SUPERSEDED |
| fontconfig | distgit/rawhide | **But** local spec diverges — see below |
| gjs | distgit/rawhide | **But** local spec diverges (tests disabled, manual meson) — see below |
| glycin | distgit/rawhide | **But** local spec diverges significantly — see below |
| icu | distgit/rawhide | Has local spec in `src/deps/icu/` — SUPERSEDED (complex; see notes) |
| libadwaita | distgit/rawhide | No local spec |
| libei | distgit/rawhide | Has local spec in `src/deps/libei/` — SUPERSEDED |
| mozjs140 | distgit/rawhide | **But** local spec diverges — see below |
| mutter | distgit/rawhide | **But** local spec diverges significantly — see below |
| nautilus | distgit/rawhide | No local spec |
| pango | distgit/rawhide | **But** local spec diverges (bundled fontconfig, manual meson) — see below |
| pipewire | distgit/rawhide | **But** local spec diverges (version, disabled features) — see below |
| xdg-desktop-portal | distgit/rawhide | **But** local spec expands meson macros manually — see below |
| gobject-introspection | distgit/rawhide | Has local spec (bootstrap variant) in `src/gnome-50/gobject-introspection/` |
| gsettings-desktop-schemas | distgit/rawhide | Has local spec in `src/gnome-50/gsettings-desktop-schemas/` — SUPERSEDED |
| gnome-settings-daemon | distgit/rawhide | Has local spec in `src/gnome-50/gnome-settings-daemon/` — SUPERSEDED |
| gnome-shell | distgit/rawhide | Has local spec in `src/gnome-50/gnome-shell/` — SUPERSEDED |
| gtk4 | distgit/rawhide | Has local spec in both `src/gnome-50/gtk4/` and `src/deps/gtk4/` — SUPERSEDED |
| libnotify | distgit/rawhide | No local spec |
| docbook-utils | distgit/rawhide | No local spec |
| docbook-style-xsl | distgit/rawhide | No local spec |
| gexiv2 | distgit/rawhide | No local spec (note: `libgexiv2` is the package name) |
| localsearch | distgit/rawhide | Has local spec in `src/deps/localsearch/` — SUPERSEDED |
| tinysparql | distgit/rawhide | No local spec |
| evolution-data-server | distgit/rawhide | Has local spec in `src/deps/evolution-data-server/` — SUPERSEDED (intentionally excluded per CLAUDE.md; libicu conflict) |
| gnome-online-accounts | distgit/rawhide | Has local spec in `src/deps/gnome-online-accounts/` — SUPERSEDED |
| mod_dnssd | distgit/rawhide | Has local spec in `src/deps/mod_dnssd/` — SUPERSEDED |
| libical | distgit/rawhide | Has local spec in `src/deps/libical/` — SUPERSEDED (per CLAUDE.md: intentionally excluded) |
| libebur128 | distgit/rawhide | Has local spec in `src/deps/libebur128/` — SUPERSEDED |
| libzip | distgit/rawhide | Has local spec in `src/deps/libzip/` — SUPERSEDED |
| lzo | distgit/rawhide | Has local spec in `src/deps/lzo/` — SUPERSEDED |

---

## Modified Packages (Local Spec Required or Meaningful Divergence)

### glib2

- **Path**: `src/gnome-50/glib2/`
- **Our version**: 2.87.3-2
- **Rawhide version**: 2.87.5 (tracking behind)
- **COPR source**: `upload` (SRPM)
- **Diverges from rawhide**: Yes — significantly
- **Changes from rawhide**:
  - No `BuildRequires: pkgconfig(gi-docgen)` — gi-docgen not available as pkgconfig on EL10 at the time of build
  - No `BuildRequires: /usr/bin/g-ir-scanner` and `/usr/bin/rst2man` — replaced with `BuildRequires: gobject-introspection-devel`
  - No `BuildRequires: shared-mime-info`, `dbus-daemon`, `update-desktop-database` (test deps removed)
  - No `gnutls` Requires guard — simplified
  - `Conflicts: gobject-introspection < 1.79.1` removed — avoids complications with EL10 stock gobject-introspection
  - **Build system**: Rawhide uses `%meson` / `%meson_build` / `%meson_install` macros; ours manually calls `meson setup --prefix=/usr --libdir=/usr/lib64 --buildtype=plain build` then `meson compile -C build` then `DESTDIR=%{buildroot} meson install -C build`. This avoids the `BuildSystem: meson` macro which had EL10 compat issues.
  - Rawhide's `glib2.spec` does not include `%transfiletriggerin` / `%transfiletriggerpostun` scriptlets for `glib-2.0/schemas`; our version adds them to fix missing schema compilation on EL10.
  - Additional patch: `glib-do-not-install-localtime-test.patch` in our spec (Patch2).
  - Our spec has a `%package static` subpackage; rawhide also has it — parity.
  - `%files` section in our spec uses broad `%{_libdir}/girepository-1.0/*.typelib` glob; rawhide ships additional `gi-compile-repository`/`gi-decompile-typelib`/`gi-inspect-typelib` binaries — we include those too.
  - Version behind: rawhide is 2.87.5, we have 2.87.3.
- **Can switch to rawhide distgit?**: No — rawhide's build system depends on Fedora-specific macros and BRs (`/usr/bin/rst2man`, `shared-mime-info`) not available in EL10. The frexp mock environment fix is also EL10-specific. Must remain as SRPM upload.
- **Build method**: SRPM upload (`copr-cli build`)

---

### gdm

- **Path**: `src/gnome-50/gdm/`
- **Our version**: 50~rc (same as rawhide)
- **Rawhide version**: 50~rc
- **COPR source**: `distgit` / rawhide
- **Diverges from rawhide**: Yes — one meaningful addition
- **Changes from rawhide**:
  - `Requires: gnome50-el10-compat` added — this pulls in the PAM fix for dynamic GDM greeter users on EL10. Rawhide has no such Requires.
  - All BuildRequires, patches, and install sections are otherwise identical to rawhide.
- **Can switch to rawhide distgit?**: Currently COPR IS using distgit/rawhide, which means this change is NOT applied. The `gnome50-el10-compat` requirement is missing from the installed GDM RPM.
- **Action needed**: Either (a) switch COPR back to SCM build using `src/gnome-50/gdm/gdm.spec`, or (b) ensure `gnome50-el10-compat` is installed separately by the user/documentation. Currently the dependency on the PAM fix is not enforced.
- **Build method**: Currently `just copr-scm-build src/gnome-50/gdm` to apply the local spec

---

### gjs

- **Path**: `src/gnome-50/gjs/`
- **Our version**: 1.87.90-1
- **Rawhide version**: 1.87.90 (same)
- **COPR source**: `distgit` / rawhide
- **Diverges from rawhide**: Yes
- **Changes from rawhide**:
  - `%bcond_with tests` added — tests are disabled by default; rawhide unconditionally runs tests via `xwfb-run`.
  - Rawhide has `BuildRequires: gtk3`, `dbus-x11`, `mesa-dri-drivers`, `mutter`, `xwayland-run` — these are all under `%if %{with tests}` in our spec, so they won't be installed when tests are off.
  - Rawhide uses `%meson` / `%meson_build` / `%meson_install` macros; ours manually calls `meson setup --prefix=/usr --libdir=/usr/lib64 --buildtype=plain build`.
  - `%ldconfig_scriptlets` present in our spec, absent in rawhide (rawhide apparently handles it differently).
  - `%files tests` section in rawhide is populated; ours states "Tests are disabled."
  - Our spec omits `%{_datadir}/gjs-1.0/lsan` and `%{_datadir}/gjs-1.0/valgrind` file globs (present in rawhide %files).
- **Can switch to rawhide distgit?**: No — EL10 lacks `xwayland-run`, `dbus-x11`, and potentially `mutter` at build time. Tests would fail to even set up. Must keep local spec with tests disabled. COPR currently uses distgit/rawhide which will likely fail or produce a broken build.
- **Build method**: `just copr-scm-build src/gnome-50/gjs`

---

### mutter

- **Path**: `src/gnome-50/mutter/`
- **Our version**: 50~rc-1
- **Rawhide version**: 50~rc
- **COPR source**: `distgit` / rawhide
- **Diverges from rawhide**: Yes — build system and source
- **Changes from rawhide**:
  - Rawhide uses `Source0: http://download.gnome.org/sources/...` with a computed tarball URL; ours uses `Source0: mutter-50.rc.tar.xz` (local/pre-downloaded tarball).
  - Rawhide uses `%meson -Degl_device=true` / `%meson_build` / `%meson_install` macros; ours manually invokes `meson setup --prefix=/usr --libdir=/usr/lib64 --buildtype=plain build -Degl_device=true` then compiles/installs manually.
  - `%prep` in our spec is `%autosetup -n mutter-50.rc -p1`; rawhide uses `%autosetup -S git -n mutter-...` (git-based patch application).
  - `Release: 1%{?dist}` in our spec vs `%autorelease` in rawhide.
  - Our `%files` section is slimmed down — missing `%{_libexecdir}/mutter-x11-frames` listing (it's there in rawhide).
  - Our spec has a separate `mutter-rawhide.spec` file that closely tracks upstream.
- **Can switch to rawhide distgit?**: Probably yes IF the source tarball is available via the dist-git lookaside. COPR IS already using distgit/rawhide. The local spec with the hardcoded Source0 exists as a fallback/offline build variant.
- **Build method**: Currently `distgit/rawhide` in COPR

---

### glycin

- **Path**: `src/deps/glycin/`
- **Our version**: 2.0.8-100
- **Rawhide version**: 2.0.8 (same upstream version)
- **COPR source**: `distgit` / rawhide
- **Diverges from rawhide**: Yes — critically different
- **Changes from rawhide**:
  - `Release: 100%{?dist}` (bumped high to override any EL10 stock builds)
  - `Source0: glycin-2.0.8.tar.xz` — local file vs rawhide's GNOME download URL
  - `Source1: glycin-2.0.8-vendor.tar.xz` — local vendor tarball vs rawhide's auto-generated one
  - Rawhide's `%prep` uses `%cargo_prep -v vendor` then `rm -rf vendor` (unusual pattern); ours manually creates `.cargo/config.toml` pointing to the vendored sources.
  - Our spec deletes `"tests"` from `Cargo.toml` workspace to avoid serde_yaml dependency issue; rawhide applies `0001-fix-invalid-crate-manifest-for-tests-workspace-membe.patch` instead.
  - Rawhide has `Obsoletes: gdk-pixbuf2 < 2.43.5-1`; ours omits this (per CLAUDE.md: intentionally removed to avoid conflicts on EL10).
  - `%bcond check 1` — rawhide has this too, but tests pass differently; ours runs `%meson_test || :` (soft failure) since loaders fail on EL10.
  - Build flags otherwise similar: both disable heif/jpegxl on RHEL.
- **Can switch to rawhide distgit?**: No — the Rust vendor tarball setup is different, and the `Obsoletes: gdk-pixbuf2` in rawhide would conflict with EL10's stock gdk-pixbuf2. The local source tarball (offline build) is also required. Must remain custom. COPR currently uses distgit/rawhide — this may be fine if rawhide's build works for EL10, but the `Obsoletes` line is dangerous.
- **Build method**: Should be `just copr-scm-build src/deps/glycin` or SRPM upload; currently `distgit/rawhide`

---

### mozjs140

- **Path**: `src/deps/mozjs140/`
- **Our version**: 140.6.0 (same as rawhide)
- **Rawhide version**: 140.6.0
- **COPR source**: `distgit` / rawhide
- **Diverges from rawhide**: Yes — build system completely rewritten
- **Changes from rawhide**:
  - Rawhide uses `%configure` with `--with-system-icu` and `%make_build` / `%make_install` (autoconf-based); our spec also uses `%configure` with `--with-system-icu` — **these are actually the same**.
  - Both use `BuildRequires: libicu-devel` (system ICU, NOT a separate libicu-77). This is correct — see CLAUDE.md warning.
  - `Release: %autorelease -b4` in our spec vs `%autorelease -b3` in rawhide (we bumped the base release to ensure our build wins over any distgit build).
  - Both omit `nasm` on RHEL (`%if !0%{?rhel}`).
  - No other meaningful differences in the spec structure.
- **Assessment**: Our spec is functionally equivalent to rawhide but with a bumped base release. The `-b4` vs `-b3` ensures our SRPM version wins in COPR. COPR is currently set to `distgit/rawhide` which builds from the `-b3` base — this is a version conflict risk.
- **Can switch to rawhide distgit?**: Potentially yes, but the `-b4` release bump exists for a reason (to override something). Keep local spec for safety. See CLAUDE.md: built with `--with-system-icu` — must NOT install a separate libicu-77 in the build environment.
- **Build method**: Currently `distgit/rawhide`; should be local SRPM for release control

---

### pipewire

- **Path**: `src/deps/pipewire/`
- **Our version**: 1.6.1-2
- **Rawhide version**: 1.6.1-3 (same version, different release)
- **COPR source**: `distgit` / rawhide
- **Diverges from rawhide**: Yes — significant feature differences
- **Changes from rawhide**:
  - `baserelease 2` in our spec vs `baserelease 3` in rawhide
  - Our spec's BuildRequires are from an older copy — missing several newer deps that rawhide's full spec has. Specifically, the rawhide pipewire spec is hundreds of lines long with many feature conditionals.
  - Our spec appears to be a **stripped-down copy** focused on the core build — missing optional plugins (ldac, spandsp per CLAUDE.md: "disabled optional ldac/spandsp").
  - The `%bcond_without ldac` block in our spec has empty body (`%ifnarch s390x` / `%endif` with nothing inside), indicating ldac was intentionally removed from BuildRequires while the conditional remains.
  - `BuildRequires: pkgconfig(fdk-aac)` is present in our spec but rawhide conditionally includes it based on `%with fdk_aac`.
  - Rawhide has significantly more subpackages (jack, pulse, bluetooth, etc.) with full conditionals; our spec is simplified.
- **Can switch to rawhide distgit?**: Yes — rawhide's spec handles RHEL via `%if 0%{?rhel}` conditionals which disable many optional features. COPR is already using distgit/rawhide. The local spec in `src/deps/pipewire/` is likely a stale copy from an earlier bootstrap phase. Rawhide build should be preferred.
- **Build method**: Currently `distgit/rawhide` — this is correct

---

### pango

- **Path**: `src/deps/pango/`
- **Our version**: 1.57.0 (same as rawhide)
- **Rawhide version**: 1.57.0
- **COPR source**: `distgit` / rawhide
- **Diverges from rawhide**: Yes — build method and fontconfig bundling
- **Changes from rawhide**:
  - Rawhide uses `%meson` / `%meson_build` / `%meson_install` macros; ours manually invokes `meson setup --prefix=/usr --libdir=/usr/lib64 --buildtype=plain -Dfontconfig=enabled build`.
  - Our spec includes `rm -rf subprojects/fontconfig/ && rm -f subprojects/fontconfig.wrap` in `%prep` to prevent meson from trying to download fontconfig as a subproject (EL10 compat fix for offline builds).
  - `%install` section: our spec explicitly removes fontconfig files installed by the bundled meson subproject: `rm -rf %{buildroot}/etc/fonts %{buildroot}/usr/bin/fc-* %{buildroot}/usr/lib64/libfontconfig* ...` (15+ paths). This is because pango's meson build optionally builds fontconfig from its subproject directory.
  - Rawhide does not need this cleanup since `%meson` handles wrap modes differently.
  - Our `%files` sections use broad globs (`%{_bindir}/*`, `%{_libdir}/*.so.*`); rawhide is more precise.
  - `Release: %autorelease` in rawhide vs no autorelease macro in our spec.
- **Can switch to rawhide distgit?**: Potentially yes — rawhide's `%meson` should handle the fontconfig wrap correctly. But the EL10 build environment may not support `--wrap-mode=nodownload` properly without `meson.options`. Test carefully. COPR is already `distgit/rawhide`.
- **Build method**: Currently `distgit/rawhide` — the local spec exists as a bootstrap artifact

---

### fontconfig

- **Path**: `src/deps/fontconfig/`
- **Our version**: 2.17.0-4 (same as rawhide)
- **Rawhide version**: 2.17.0-4
- **COPR source**: `distgit` / rawhide
- **Diverges from rawhide**: Yes — stripped doc toolchain
- **Changes from rawhide**:
  - Rawhide has `BuildRequires: docbook-utils docbook-utils-pdf` (per CLAUDE.md: "Stripped doc toolchain"); ours omits these and adds `docbook-utils` and `docbook-style-xsl` as separate COPR packages to satisfy the dep.
  - Our `%build` invocation: `meson setup ... -Ddoc=disabled` (docs explicitly disabled) vs rawhide which builds docs via `-Ddoc=auto` or similar.
  - Our `%files` uses broad globs (`/etc/fonts/*`, `/usr/share/xml/fontconfig/*`) vs rawhide's more granular listing with `%config(noreplace)` guards and scriptlets.
  - Our spec **omits** the `%post`, `%postun`, `%preun` scriptlets present in rawhide (fontconfig cache management, xml-common registration).
  - Our spec omits `Requires(pre): xml-common` and `Requires(postun): xml-common`.
  - Our spec's `%package devel-doc` exists but has no content — rawhide populates it.
- **Can switch to rawhide distgit?**: Yes, IF `docbook-utils` and `docbook-utils-pdf` are available in EL10 (they are — we have them as separate COPR packages). But the missing cache scriptlets in our version may cause stale font caches. COPR is already `distgit/rawhide` which includes proper scriptlets. The local spec in this repo is a stale bootstrap artifact.
- **Build method**: Currently `distgit/rawhide` — local spec is a stale backup

---

### gi-docgen

- **Path**: `src/deps/gi-docgen/`
- **Our version**: 2026.1-1
- **Rawhide version**: 2026.1
- **COPR source**: `distgit` / rawhide
- **Diverges from rawhide**: Yes — significantly different build system
- **Changes from rawhide**:
  - Rawhide uses `BuildSystem: pyproject` (modern RPM Python packaging macro); our spec uses `python3 setup.py bdist_wheel` + `pip3 install --root=%{buildroot} --no-deps` — this is the old pre-pyproject approach.
  - Rawhide's `BuildSystem: pyproject` requires `python3-wheel`, `python3-pip`, etc. through the macro infrastructure; ours explicitly lists these.
  - Rawhide produces a richer package with more metadata files; ours only ships `gidocgen/`, `gi_docgen-*.dist-info/`, the binary, `.pc` file, and man page.
  - Rawhide has a `%bcond source_code_pro` conditional for font handling (skipped on RHEL/ELN); ours doesn't address this.
  - `License: Apache-2.0 OR GPL-3.0-or-later` in our spec is simplified vs rawhide's full SPDX compound expression.
- **Can switch to rawhide distgit?**: Yes — COPR is already using `distgit/rawhide`. The `pyproject` BuildSystem works in EL10's COPR build environment (COPR installs `python3-wheel` etc.). The local spec in this repo is an early bootstrap that should be retired.
- **Build method**: Currently `distgit/rawhide` — correct

---

### xdg-desktop-portal

- **Path**: `src/gnome-50/xdg-desktop-portal/`
- **Our version**: 1.21.0
- **Rawhide version**: 1.21.0
- **COPR source**: `distgit` / rawhide
- **Diverges from rawhide**: Yes — build system expansion
- **Changes from rawhide**:
  - Rawhide uses `%meson %{!?with_docs:-Ddocumentation=disabled}` / `%meson_build` / `%meson_install`; our spec manually invokes `meson setup` with all prefix/libdir/etc arguments explicitly spelled out, and `ninja -C redhat-linux-build` directly.
  - `--auto-features=enabled` flag present in our spec; rawhide doesn't pass this.
  - `-Dsystemduserunitdir` etc. are passed via the expanded macro call in ours; rawhide relies on RPM macro defaults.
  - `DESTDIR=%{buildroot} ninja -C redhat-linux-build install` in our spec vs `%meson_install` in rawhide.
  - The `%{_sbin}` variable reference in our spec is unusual and may evaluate incorrectly on some systems.
  - `%if %{undefined rhel}` conditionals for `python3-pytest-xdist` are identical to rawhide.
- **Can switch to rawhide distgit?**: Yes — COPR is already `distgit/rawhide`. The manual meson expansion in our local spec was an early workaround for `%meson` macro failures on EL10 COPR. That appears to be resolved now. Local spec is a stale artifact.
- **Build method**: Currently `distgit/rawhide` — correct

---

### xdg-desktop-portal-gnome

- **Path**: `src/gnome-50/xdg-desktop-portal-gnome/`
- **Our version**: 50~rc
- **Rawhide version**: 50~rc
- **COPR source**: `distgit` / rawhide
- **Diverges from rawhide**: Yes — build system expansion (same pattern as xdg-desktop-portal)
- **Changes from rawhide**:
  - Rawhide uses `%meson -Dsystemduserunitdir=%{_userunitdir}` / `%meson_build` / `%meson_install`; our spec manually expands all meson prefix/path arguments and uses `ninja -C redhat-linux-build` directly.
  - `--auto-features=enabled` in our spec vs not in rawhide.
  - `DESTDIR=%{buildroot} ninja install` in ours vs `%meson_install` in rawhide.
  - `desktop-file-validate` call in our `%install` section (present in rawhide too — parity).
- **Can switch to rawhide distgit?**: Yes — COPR is already `distgit/rawhide`. Same pattern as xdg-desktop-portal: the expanded meson call was a workaround. Stale artifact.
- **Build method**: Currently `distgit/rawhide` — correct

---

### gnome-desktop3

- **Path**: `src/gnome-50/gnome-desktop3/`
- **Our version**: 44.5
- **Rawhide version**: 44.5
- **COPR source**: `scm` / `main` branch
- **Diverges from rawhide**: Yes — build flag and gtk3 dep removed
- **Changes from rawhide**:
  - Rawhide has `BuildRequires: pkgconfig(gtk+-3.0) >= %{gtk3_version}` and builds with `-Dgtk_doc=true -Dinstalled_tests=true`; our spec removes the gtk3 BuildRequires and adds `-Dlegacy_library=false` to meson options.
  - `-Dlegacy_library=false` disables the gtk3-based `libgnome-desktop-3` legacy library. This is critical — EL10 does not have gtk3 available in the COPR build environment.
  - Our spec removes `BuildRequires: pkgconfig(gtk+-3.0)` entirely.
  - Our `%files` section omits `%{_libdir}/libgnome-desktop-3*` (since it's not built).
  - Rawhide includes `gnome-desktop3` (the gtk3 package), `gnome-desktop3-devel`, `gnome-desktop4`, `gnome-desktop4-devel`, `tests` subpackages. Our spec keeps `gnome-desktop3` (as a compatibility empty/stub), `gnome-desktop3-devel`, `gnome-desktop4`, `gnome-desktop4-devel`, `tests`.
  - Build system: both use manual `meson setup` invocation style.
- **Can switch to rawhide distgit?**: No — rawhide requires `gtk+-3.0` which is not available in EL10 COPR. Must keep local spec with `-Dlegacy_library=false`.
- **Build method**: `scm/main` — correct; uses `src/gnome-50/gnome-desktop3/gnome-desktop3.spec`

---

### gnome-autoar

- **Path**: `src/deps/gnome-autoar/`
- **Our version**: 0.4.5-4
- **Rawhide version**: 0.4.5-4 (same)
- **COPR source**: `scm` / `main` branch
- **Diverges from rawhide**: Yes — gtk3 widget disabled
- **Changes from rawhide**:
  - Rawhide has `BuildRequires: pkgconfig(gtk+-3.0)` and builds the gtk3 widget subpackage (`gnome-autoar-gtk`) with `-Dgtk_doc=true`; our spec passes `-Dgtk=false` to disable the gtk3 widget entirely.
  - Our spec also passes `-Dvapi=false` (no Vala bindings) and `-Dgtk_doc=false` (no gtk-doc) and `-Dtests=false`.
  - `gnome-autoar-gtk` subpackage is absent in our spec (not built since `-Dgtk=false`).
  - Changelog entry: "Disable gtk3 widget subpackage (not available on EL10)".
- **Can switch to rawhide distgit?**: No — rawhide builds the gtk3 widget which requires `gtk+-3.0` not available in EL10. Must keep local spec.
- **Build method**: `scm/main` — correct; uses `src/deps/gnome-autoar/gnome-autoar.spec`

---

### libgexiv2

- **Path**: `src/deps/libgexiv2/`
- **Our version**: 0.16.0-2
- **Rawhide version**: 0.16.0-2 (identical version)
- **COPR source**: `upload` (SRPM)
- **Diverges from rawhide**: Minimal — one patch added
- **Changes from rawhide**:
  - Our spec and rawhide are very close. Both have `Patch: 0001-gexiv2-fix-package-name-in-gir-file-to-have-0.16-suf.patch`.
  - Rawhide uses `%meson` / `%meson_build` / `%meson_install` / `%meson_test`; our spec also uses these macros — **identical build system**.
  - Minor: our `%files` section explicitly lists `%dir %{_libdir}/girepository-1.0` and `%dir %{_datadir}/gir-1.0` etc. while rawhide also lists those.
  - The changelog is essentially copied from rawhide. The spec is very close to rawhide.
- **Assessment**: This package appears to be rawhide's spec with minor formatting differences. It may have been uploaded as an SRPM because distgit was not yet configured for it in COPR.
- **Can switch to rawhide distgit?**: Yes — the spec is nearly identical to rawhide. Set `source_type=distgit` for this package.
- **Build method**: SRPM upload — should be switched to `distgit/rawhide`

---

### gnome-user-share

- **Path**: `src/deps/gnome-user-share/`
- **Our version**: 48.1
- **Rawhide version**: 48.1
- **COPR source**: `upload` (SRPM)
- **Diverges from rawhide**: Yes — vendor tarball approach
- **Changes from rawhide**:
  - Rawhide uses `BuildRequires: cargo-rpm-macros` (non-RHEL) — same as ours.
  - `Source1: %{name}-%{tarball_version}-vendor.tar.xz` — both have a vendor tarball, same approach.
  - Our spec manually creates `.cargo/config.toml` pointing to vendored sources in `%prep`; rawhide presumably uses `%cargo_prep`.
  - `%build` in our spec: `%meson` / `%meson_build`; rawhide is identical.
  - `echo "Vendored dependencies." > LICENSE.dependencies` in our spec — rawhide likely handles this via cargo macros.
  - No meaningful functional difference — the Rust vendoring approach is the same.
- **Can switch to rawhide distgit?**: Potentially yes — but the vendor tarball must be accessible to COPR. Rawhide's lookaside cache has it. The SRPM upload exists because the vendor tarball was generated locally. Worth testing a distgit build.
- **Build method**: SRPM upload; could potentially switch to `distgit/rawhide`

---

### selinux-policy (custom)

- **Path**: `src/deps/selinux-policy/`
- **Our version**: 43.1-1
- **Rawhide version**: 43.1-1 (same!)
- **COPR source**: `upload` (SRPM)
- **Diverges from rawhide**: The source tarball points to a specific commit `f5ead57eed9c9322165762f6781b01353f2de870` from the fedora-selinux GitHub repo — this is the same as what rawhide tracks.
- **Assessment**: This was uploaded as an SRPM likely because SELinux policy builds are complex and the rawhide distgit build may not produce the exact policy modules needed for EL10's xdm_t GDM workarounds (documented in CLAUDE.md). The `selinux-policy` package in COPR provides a baseline; the actual GDM-specific policy modules (`gdm-gnome50.pp`, `gdm-userdb-connect.pp`) are shipped by `gnome50-el10-compat`.
- **Can switch to rawhide distgit?**: Possibly — the spec is identical to rawhide. However, the SELinux policy build is complex (requires `checkpolicy`, specific tools). Test carefully. The EL10-specific policy overrides are in `gnome50-el10-compat`, not this package.
- **Build method**: SRPM upload; test switching to `distgit/rawhide`

---

## Packages NOT in Fedora (Custom / EL10-Specific)

These packages exist only in our repo and have no equivalent in Fedora rawhide:

| Package | Path | Notes |
|---------|------|-------|
| `gnome50-el10-compat` | `src/deps/gnome50-el10-compat/` | Ships `/etc/pam.d/systemd-user` override to fix dynamic GDM greeter user authentication on EL10. This is an EL10-specific workaround. Not in Fedora because Fedora's PAM setup doesn't have this problem. COPR source: `upload` |

**Note on `icu` / `libicu77`**: The `src/deps/icu/` directory contains `libicu77-bootstrap.spec` and `libicu77.spec` (parallel libicu-77 packaging). Per CLAUDE.md, this should NOT be installed into the COPR repo as a system-replacement package — it would upgrade away libicu-74 and break gtk3/pango/everything compiled against it. The `icu` package in COPR is set to `distgit/rawhide` which builds the standard libicu package, not the parallel libicu-77.

---

## Local Specs That Are Orphaned / Superseded

These directories exist in `src/` but the corresponding COPR package is already using `distgit/rawhide`. The local spec files are stale and should either be deleted or documented as historical:

| Local Spec Path | COPR Package | Status |
|----------------|-------------|--------|
| `src/deps/autoconf/autoconf.spec` | `autoconf` (distgit) | Superseded |
| `src/deps/avahi/avahi.spec` | `avahi` (distgit) | Superseded |
| `src/deps/cairo/cairo.spec` | `cairo` (distgit) | Superseded |
| `src/deps/libei/libei.spec` | `libei` (distgit) | Superseded |
| `src/deps/libxcvt/libxcvt.spec` | `libxcvt` (distgit) | Superseded |
| `src/deps/libldac/libldac.spec` | `libldac` (distgit) | Superseded |
| `src/deps/meson/meson.spec` | `meson` (distgit) | Superseded |
| `src/deps/shaderc/shaderc.spec` | `shaderc` (distgit) | Superseded |
| `src/deps/umockdev/umockdev.spec` | `umockdev` (distgit) | Superseded |
| `src/deps/wayland-protocols/wayland-protocols.spec` | `wayland-protocols` (distgit) | Superseded |
| `src/deps/python-dbusmock/python-dbusmock.spec` | `python-dbusmock` (distgit) | Superseded |
| `src/deps/python-smartypants/python-smartypants.spec` | `python-smartypants` (distgit) | Superseded |
| `src/deps/python-typogrify/python-typogrify.spec` | `python-typogrify` (distgit) | Superseded |
| `src/deps/localsearch/localsearch.spec` | `localsearch` (distgit) | Superseded |
| `src/deps/libebur128/libebur128.spec` | `libebur128` (distgit) | Superseded |
| `src/deps/libical/libical.spec` | `libical` (distgit) | Per CLAUDE.md: intentionally excluded due to libicu-77 conflict |
| `src/deps/libzip/libzip.spec` | `libzip` (distgit) | Superseded |
| `src/deps/lzo/lzo.spec` | `lzo` (distgit) | Superseded |
| `src/deps/mod_dnssd/mod_dnssd.spec` | `mod_dnssd` (distgit) | Superseded |
| `src/deps/evolution-data-server/evolution-data-server.spec` | `evolution-data-server` (distgit) | Per CLAUDE.md: intentionally excluded due to libicu-77 conflict |
| `src/deps/gnome-online-accounts/gnome-online-accounts.spec` | `gnome-online-accounts` (distgit) | Superseded |
| `src/gnome-50/gnome-control-center/gnome-control-center.spec` | `gnome-control-center` (distgit) | Superseded |
| `src/gnome-50/gnome-settings-daemon/gnome-settings-daemon.spec` | `gnome-settings-daemon` (distgit) | Superseded |
| `src/gnome-50/gnome-shell/gnome-shell.spec` | `gnome-shell` (distgit) | Superseded |
| `src/gnome-50/gobject-introspection/gobject-introspection.spec` | `gobject-introspection` (distgit) | Bootstrap spec superseded (bootstrap served its purpose) |
| `src/gnome-50/gsettings-desktop-schemas/gsettings-desktop-schemas.spec` | `gsettings-desktop-schemas` (distgit) | Superseded |
| `src/gnome-50/gtk4/gtk4.spec` + `src/deps/gtk4/gtk4.spec` | `gtk4` (distgit) | Superseded |
| `src/gnome-50/libadwaita/libadwaita.spec` | `libadwaita` (distgit) | Superseded |
| `src/gnome-50/nautilus/nautilus.spec` | `nautilus` (distgit) | Superseded |

**Bootstrap-only specs** (served their build purpose, now defunct):
- `src/gnome-50/glib2/glib2-bootstrap.spec`
- `src/gnome-50/gjs/gjs-bootstrap.spec`
- `src/gnome-50/gobject-introspection/gobject-introspection-bootstrap.spec`
- `src/gnome-50/mutter/mutter-rawhide.spec` (rawhide tracking copy)
- `src/deps/icu/libicu77-bootstrap.spec` and `src/deps/icu/libicu77.spec` (per CLAUDE.md: not to be installed)
- `src/deps/pango-fresh/pango.spec` (alternate pango build — superseded)
- `src/deps/pipewire-el10/`, `src/deps/pipewire-f43/` (alternate pipewire builds — superseded by `distgit/rawhide`)
- `src/deps/mozjs128/mozjs128.spec` (older mozjs, replaced by mozjs140)

---

## Action Items

### High Priority

- [ ] **Fix gdm dependency**: COPR uses `distgit/rawhide` for gdm, which means the `Requires: gnome50-el10-compat` is NOT applied. Either switch gdm back to SCM build (`just copr-scm-build src/gnome-50/gdm`), or document that `gnome50-el10-compat` must be manually installed.

- [ ] **Audit glycin Obsoletes danger**: COPR uses `distgit/rawhide` for glycin, which includes `Obsoletes: gdk-pixbuf2 < 2.43.5-1`. On EL10, `gdk-pixbuf2` is a system package — this Obsoletes could remove it. Verify that COPR's rawhide glycin build does not conflict with EL10's gdk-pixbuf2 at install time.

- [ ] **Update glib2**: Our SRPM is at 2.87.3; rawhide is at 2.87.5. Rebase to 2.87.5, carrying forward the EL10-specific changes (frexp workaround, transfiletrigger scriptlets, simplified BRs).

### Medium Priority

- [ ] **Switch libgexiv2 from upload to distgit**: The spec is nearly identical to rawhide. Run `copr-cli modify-package --source-type distgit --distgit fedora --committish rawhide jreilly1821/c10s-gnome-50 libgexiv2` (but confirm package name is `libgexiv2` not `gexiv2` in Fedora dist-git).

- [ ] **Evaluate mozjs140 release bump**: Our local spec uses `-b4` vs rawhide's `-b3` to ensure version precedence. Document why or switch to a simple `Epoch: 1` approach if needed.

- [ ] **Switch gjs back to SCM build**: COPR uses `distgit/rawhide` which will try to build tests (requires `xwayland-run`, `dbus-x11`, `mesa-dri-drivers`, `mutter` at build time — none available in EL10 COPR). This build likely fails or produces an incomplete package. Switch to `just copr-scm-build src/gnome-50/gjs`.

- [ ] **Evaluate gnome-user-share upload vs distgit**: Check if COPR can build it from `distgit/rawhide` (vendor tarball must be in Fedora's lookaside). If so, switch.

### Low Priority / Cleanup

- [ ] **Delete orphaned local specs**: Remove superseded spec files from `src/` to reduce confusion. Candidates: all specs listed in the "Orphaned/Superseded" table above. Keep bootstrap specs only if they might be needed again.

- [ ] **Document pipewire local spec**: The `src/deps/pipewire/` spec is a stale copy. `distgit/rawhide` is already being used. The local spec should be deleted.

- [ ] **Document pango/fontconfig/xdg-portal local specs**: Same — stale bootstrap artifacts. `distgit/rawhide` is working. Remove.

- [ ] **Add `gnome-autoar` scm config to justfile**: The `scm/main` source requires that the GitHub repo URL is configured in COPR. Confirm `copr-cli modify-package --source-type scm --clone-url https://github.com/... --spec src/deps/gnome-autoar/gnome-autoar.spec` is set correctly.

---

## COPR Source Configuration Quick Reference

```bash
# Packages that MUST use local spec (SCM or SRPM):
# glib2           → SRPM upload (EL10 frexp workaround + transfiletrigger fix + version lag)
# gdm             → SCM (adds gnome50-el10-compat Requires)
# gjs             → SCM (tests disabled, xwayland-run not available on EL10)
# gnome-desktop3  → SCM (gtk3 removed, -Dlegacy_library=false)
# gnome-autoar    → SCM (gtk3 removed, -Dgtk=false)
# gnome50-el10-compat → SRPM upload (custom package, not in Fedora)
# selinux-policy  → SRPM upload (policy needs evaluation)

# Packages using distgit/rawhide (correct):
# mutter, pipewire, pango, fontconfig, gi-docgen, glycin, mozjs140,
# xdg-desktop-portal, xdg-desktop-portal-gnome, and all others listed
# in "Using Fedora Dist-Git" section above

# Packages that SHOULD be switched from SRPM to distgit:
# libgexiv2 → switch to distgit/rawhide
# gnome-user-share → evaluate; likely switch to distgit/rawhide
```
