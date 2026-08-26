# Tideforge build-once intermediate experiment

**Status:** theory branch only; not proposed for production or merge  
**Experimented:** 2026-08-26  
**Prototype:** `scripts/tideforge-intermediate.py`

## Short answer

Tideforge can compile a useful subset **once per CPU architecture** and wrap
the resulting staged filesystem into RPM, DEB, and pacman packages without
compiling again. Pure data packages can go further and build once for all
architectures.

It cannot safely use one distro-agnostic buildroot for the whole catalog. The
repository's native desktop libraries and compositors bind to target ABIs,
headers, filesystem layouts, compiler policy, package-generated dependencies,
and scriptlets. Reusing those binaries across all targets would exchange build
time for silent ABI and policy failures.

The useful design is therefore **one expensive portable-payload action plus
cheap target package/gate actions**, not one action that eliminates targets.

```text
checksum-pinned source + portable SDK + architecture
                         |
                         v
              staged filesystem (TFI)
                         |
           +-------------+-------------+
           |             |             |
           v             v             v
       RPM metadata   DEB metadata   PKGBUILD metadata
       + native gate  + native gate  + native gate
```

## What was measured

The current catalog has 45 Tideforge recipes, 37 of them multi-target:

| Build system | Recipes | Multi-target | Initial reuse assessment |
| --- | ---: | ---: | --- |
| custom | 17 | 14 | Mostly target-linked COSMIC/Rust; unsafe by default |
| meson | 7 | 4 | Target-linked C/C++ libraries; unsafe by default |
| cmake | 6 | 5 | Mixed; header/data-only installs may qualify |
| cargo | 5 | 5 | Must prove native dependency and symbol contract |
| go | 5 | 4 | Strong candidate when `CGO_ENABLED=0` and static ELF is enforced |
| data | 4 | 4 | Safe first cohort; architecture-independent |
| autotools | 1 | 1 | `libunwind`; explicitly target ABI-sensitive |

The immediately credible cohort is:

- all four `data` recipes: `dms`, `dms-greeter`, `oversteer-udev`, and
  `wayland-protocols` — one payload total, not one per architecture;
- the four multi-target Go recipes (`danksearch`, `dgop`, `dms-cli`, `uupd`)
  after Tideforge enforces a static/no-CGO contract;
- selected header/icon/data-like recipes after inspection (for example,
  `cli11-devel` and `pop-icon-theme`).

That is 8 high-confidence recipes now, with a few likely additions. It is a
worthwhile fast path, but not a replacement for the native build chains.

## Prototype result

The prototype seals a staged root into a deterministic TFI tar containing:

- normalized ownership and timestamps;
- package/source/build-contract identity;
- a path, mode, size, and SHA-256 inventory;
- the complete payload-tree digest;
- for each ELF, `DT_NEEDED` libraries and GLIBC/GLIBCXX/CXXABI symbol versions.

`dms-greeter` was staged once from its checksum-verified upstream source on
x86_64. The resulting payload contained 868 regular files (957 inventory
entries), and two independent seals were byte-identical:

```text
TFI archive SHA-256: 38b24235600b2560c70ac536d32d53ec372fcd4ca4b823e2b1774ce1388c5d6d
Payload tree SHA-256: db46f0b9b6fbb864e58629b8535924831cdc89f4fa0c519a4bae73bd43b95ad7
Targets planned:      el10, ubuntu, debian, opensuse-tumbleweed, arch
Compile per target:   false for all five
```

This proves the byte-reuse boundary for the easiest real package class. It
does not yet prove production-native packages, signing, or installability; the
existing factory gates remain authoritative.

## Why the full “one root per CPU” theory breaks

1. **The buildroot is an ABI input.** A linked binary records required shared
   libraries and versioned symbols. Building against a newer glibc,
   libstdc++, Qt, systemd, PipeWire, or desktop library can produce bytes that
   an older target cannot load. The TFI prototype records these requirements
   so reuse has a mechanical rejection point instead of an assumption.
2. **Library destinations differ.** Current recipes already encode
   `/usr/lib64` for RPM and Debian multiarch paths under `/usr/lib/<tuple>`.
   A single immutable library payload cannot inhabit both layouts without a
   target transform, at which point it is no longer the same payload.
3. **Package metadata is intentionally native.** RPM dependency generators,
   `dpkg-shlibdeps`, pacman dependency declarations, subpackage splits,
   ldconfig behavior, sysusers/tmpfiles handling, triggers, and maintainer
   scripts are different. Tideforge has bug history demonstrating that these
   differences are load-bearing (`xfconf` split dependencies and openSUSE
   ldconfig scriptlets are examples in `scripts/tideforge.py`).
4. **Build policy differs.** Distro hardening flags, debug packages, LTO,
   Python versions/site paths, and Rust/C FFI behavior are part of what the
   target build proves. A portable SDK replaces those policies with a new
   TunaOS ABI policy; it does not make them disappear.
5. **Install/runtime validation remains per target.** Even a perfectly
   portable executable can have differently named dependencies or fail a
   target's integration policy. Removing target roots from validation would
   violate the existing promotion contract.

## Proposed eligibility contract

A recipe may opt into a future portable-payload path only when all of these
are mechanically true:

1. one immutable, digest-pinned SDK/sysroot is declared for its architecture;
2. installation is captured under a normalized `DESTDIR`;
3. the result contains no undeclared absolute RPATH/RUNPATH, host paths, or
   build IDs carrying nondeterministic input;
4. every ELF's interpreter, `DT_NEEDED`, and symbol-version ceiling is within
   every selected target's declared ABI contract;
5. target packaging changes metadata and permitted path mappings only; it does
   not compile or mutate ELF content;
6. the native package is linted, clean-installed, and smoke-tested on every
   target exactly as today;
7. any target failure demotes the recipe to normal target builds rather than
   weakening the gate.

Suggested recipe vocabulary (not implemented):

```yaml
build_reuse:
  mode: portable-payload       # target-native remains the default
  sdk: tideforge-sdk-v0@sha256:...
  architectures: [x86_64, aarch64]
  elf_policy:
    static: true               # ideal for pure Go/Rust CLI tools
    cgo: false
```

The action key for this build must intentionally omit the target ID and native
format. It must include recipe/source/patch digests, architecture, immutable
SDK digest, toolchain flags, dependency payload keys, and reproducibility
contract. Separate target packaging keys then include the TFI tree digest,
target contract, renderer, and target-native dependency mappings.

## Sensible next experiment

Do not start with GNOME, COSMIC, `libseat`, `xfconf`, or `libunwind`. Start with
two cohorts:

1. ship the four data recipes from one `noarch` TFI through all three native
   format adapters and run the existing clean-install/smoke gates;
2. enforce `CGO_ENABLED=0`, static linking, and an empty `DT_NEEDED` set for one
   Go recipe, then package the exact same per-arch bytes for all five targets.

Measure wall time and cache storage against today's 5-target cells. Only after
those are green should the theory be widened to dynamically linked programs
built against a lowest-common-denominator SDK.

## Related prior art

- [nFPM](https://nfpm.goreleaser.com/docs/) demonstrates the narrow model:
  one prebuilt file set can be wrapped into several native package formats.
  Its own documentation also says it intentionally covers a simpler feature
  set, which matches the boundary above.
- [Flatpak](https://docs.flatpak.org/en/latest/introduction.html) achieves
  broad distro independence by defining and shipping a runtime. That validates
  the portable-runtime alternative, but it is a different product from native
  system packages used to assemble a desktop OS.
- [glibc dynamic-linker guidance](https://www.sourceware.org/glibc/manual/2.44/html_node/Dynamic-Linker-Hardening.html)
  documents inspecting versioned dynamic symbols with `readelf`; the prototype
  records those symbol requirements in every TFI manifest.

## Non-goals of this branch

- no workflow integration;
- no production publisher or R2 mutation;
- no change to `main` or the accepted RFC 011 default;
- no relaxation of target-native build/install/runtime gates;
- no claim that a generated RPM, DEB, or Arch package is interchangeable.
