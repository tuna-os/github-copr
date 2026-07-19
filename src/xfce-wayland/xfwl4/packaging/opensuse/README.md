# openSUSE (sailfin) — reuse the RPM, with macro adjustments

openSUSE Tumbleweed is RPM, so `../../xfwl4.spec` is the starting point rather
than a new packaging format. There is no separate spec here on purpose: forking
it would mean maintaining two specs that must stay byte-compatible on the six
upstream constraints (vendored cargo tree, protocol submodule, dma cfg patch,
feature flags, `GETTEXT_SYSTEM`, PIC relocation).

Tumbleweed already has everything else: `xfce4-panel` 4.20.7 requires
`libgtk-layer-shell.so.0` and `libwayland-client.so.0`, and `greetd` 0.10.3,
`gtkgreet` 0.8, `cage` 0.3.1, `rust`/`cargo` 1.97 are all in the repos. `xfwl4`
is the only gap — repology confirms no openSUSE packaging of it exists.

## Expected differences from the Fedora/EL10 spec

1. **`%{?rhel}` conditional must not fire.** The spec sets
   `__cargo_requires_buildrequires` under `0%{?rhel} >= 10`; on openSUSE that
   is simply skipped, which is correct, but verify it does not trip
   `rpmlint`'s unresolved-BuildRequires check.

2. **BuildRequires naming.** The `pkgconfig(...)` style entries port as-is.
   The bare `-devel` names do not reliably: expect to map
   `mesa-libgbm-devel` → `Mesa-libgbm-devel`, `libxkbcommon-devel` →
   `libxkbcommon-devel` (same), `gtk3-devel` → `gtk3-devel` (same),
   `libSM-devel` → `libSM-devel` (same). Prefer converting each to
   `pkgconfig(...)` where one exists — that is portable across both.

3. **`%license` vs `%doc`.** Supported on Tumbleweed; no change expected.

4. **Group tag.** openSUSE still wants `Group:` in some submission paths
   (OBS/Factory), unlike Fedora which dropped it.

## Build route

Either:

- **OBS** (`devel:XFCE` or a TunaOS home project) — the idiomatic route if
  these are ever submitted upstream to Factory; or
- **our own mock/rpmbuild chain**, once `build-chain.sh` grows an openSUSE
  target. `derive_dist()` currently understands fedora/centos/epel only, so it
  would need an arm for openSUSE — Tumbleweed is rolling and conventionally
  uses no dist tag, so this likely means passing `--dist ''` explicitly rather
  than deriving.

Nothing here has been built. Treat every mapping above as a hypothesis until a
real build confirms it.
