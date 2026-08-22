#!/usr/bin/env bash
# Build one row emitted by plan-package-factory.py. Family and distro are data;
# this file contains only native package-format adapters.
set -eEuo pipefail

cell_id=${CELL_ID:?}
engine=${ENGINE:?}
target=${TARGET:?}
: "${ARCHITECTURE:?}"
image=${IMAGE:?}
out=${OUT_DIR:-"$PWD/.factory/$cell_id"}
mkdir -p "$out/artifacts"

export SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:?}
export TZ=UTC LANG=C.UTF-8 LC_ALL=C.UTF-8

if [[ $engine == build-chain ]]; then
    if grep -q '^[[:space:]]*distgit:' "${MANIFEST:?}"; then
      tier_args=()
      if [[ -n ${TIERS:-} ]]; then
        IFS=',' read -ra selected_tiers <<< "$TIERS"
        for tier in "${selected_tiers[@]}"; do tier_args+=(--tier "$tier"); done
      fi
      python3 scripts/import-fedora-distgit.py \
        --build-order "$MANIFEST" "${tier_args[@]}" \
        --branch rawhide --state "$out/import-state.json" \
        --release-bump --jobs 4
    fi
    args=(--manifest "${MANIFEST:?}" --backend podman --image "$image"
          --mock-config "${MOCK_CONFIG:?}" --local-repo "$out/artifacts"
          --with-checks)
    if [[ -n ${TIERS:-} ]]; then
      args+=(--stream --tiers "$TIERS")
    fi
    ./scripts/build-chain.sh "${args[@]}"
    exit 0
fi

[[ $engine == tideforge ]] || { echo "unknown factory engine: $engine" >&2; exit 2; }
recipe=${RECIPE:?}
python3 scripts/tideforge.py validate "$recipe"
python3 scripts/verify-tideforge-source.py "$recipe" --cache-dir "$HOME/.cache/tideforge/sources"

case ${FORMAT:?} in
  rpm)
    # Cross-cell BUILD dependency resolution — the build-side twin of #440's
    # verify fix: a package whose BuildRequires are themselves factory
    # products (gtkgreet needs gtk-layer-shell-devel, xfwl4 needs
    # xfconf-devel/libxfce4ui-devel, quickshell needs cpptrace-devel — run
    # 32382594650) can only resolve them from the PUBLISHED factory repo,
    # built by earlier waves. Same manifest field the verify reads; empty
    # (e.g. el10/aarch64, which has no served index yet) adds nothing.
    # Space-separated because an arch may declare several indexes (#467):
    # el10/x86_64 has both the tideforge mirror and the xfce build-chain
    # prefix, and xfwl4's BuildRequires only resolve from the second. URLs
    # never contain whitespace, so word-splitting in the container is safe.
    published_index="$(python3 scripts/published_index.py "$target" "${ARCHITECTURE:-}" --join)"
    root="$out/rpm"
    python3 scripts/tideforge.py render "$recipe" --target "$target" --output "$root/rpmbuild/SPECS"
    mkdir -p "$root/rpmbuild"/{BUILD,BUILDROOT,RPMS,SOURCES,SRPMS}
    python3 scripts/fetch-tideforge-sources.py "$recipe" "$root/rpmbuild/SOURCES" \
      --cache-dir "$HOME/.cache/tideforge/sources"
    if [[ $target == opensuse-tumbleweed ]]; then
      docker run --rm --env SOURCE_DATE_EPOCH --env TZ --env LANG --env LC_ALL \
        --env TARGET="$target" \
        --volume "$root:/work" "$image" bash -lc '
          set -euo pipefail
          zypper --non-interactive --gpg-auto-import-keys refresh
          zypper --non-interactive install rpm-build
          mapfile -t requirements < <(rpmspec -q --buildrequires /work/rpmbuild/SPECS/*.spec)
          ((${#requirements[@]} == 0)) || zypper --non-interactive install "${requirements[@]}"
          rpmbuild -ba --define "_topdir /work/rpmbuild" /work/rpmbuild/SPECS/*.spec
        '
    else
      docker run --rm --env SOURCE_DATE_EPOCH --env TZ --env LANG --env LC_ALL \
        --env TARGET="$target" --env PUBLISHED_INDEX="$published_index" \
        --volume "$root:/work" "$image" bash -lc '
          set -euo pipefail
          dnf -y install dnf-plugins-core rpm-build
          if [[ "${TARGET:-}" == el10 ]]; then
            dnf -y install epel-release
            dnf config-manager --set-enabled crb
          fi
          # The published index is a GAP-FILLER, never an upgrader: it may
          # resolve only names the system repos lack (gtk-layer-shell-devel,
          # cpptrace-devel - the cross-cell BuildRequires it exists for) and
          # must never displace a base package. Publish runs 32396660104 and
          # 32400889983 both failed when the served repo GNOME-50 glib2
          # 2.87 (whose glib2-devel is a 6.4kB stub with no gir files) beat
          # AppStream full 2.80 by VERSION and starved g-ir-scanner of
          # GObject-2.0.gir - the AGENTS.md ICU repo-poisoning hazard, live.
          # A --setopt priority on a --repofrompath repo does not take
          # effect (run 32400889983 proved it: priority=999 still upgraded
          # glib2 from the repo), so write a real repo file, where
          # priority=999 (worse than the system repos default 99)
          # reliably excludes every name a system repo already carries.
          # One [tunaos-published-N] section per declared index (#467),
          # each with the same gap-filler settings. Appended rather than
          # written once: el10/x86_64 declares two.
          index_n=0
          for published_url in ${PUBLISHED_INDEX:-}; do
            {
              echo "[tunaos-published-${index_n}]"
              echo "name=TunaOS published index ${index_n} (cross-cell gap filler)"
              echo "baseurl=${published_url}"
              echo "enabled=1"
              echo "gpgcheck=0"
              echo "priority=999"
              # priority cannot stop an OBSOLETER: the served repo retains
              # stale gnome-50 bootstrap builds glib2-2.87.3-1.el10 and
              # glib2-devel-2.87.3-1.el10 (a 6.4kB stub with no pkgconfig or
              # gir payload) whose "Obsoletes: glib2 < 2.87.3" REPLACES the
              # AppStream packages in any transaction regardless of repo
              # priority — publish run 32405815822 failed on exactly this
              # with the priority fix (#454) fully in effect. Later builds
              # (-2, 2.88.0-*) dropped the self-obsolete; only the stale -1
              # pair hijacks. Exclude the family here: a BUILDROOT must
              # never take glib2 from the published repo — the system repos
              # always carry it. Cleaning the stale pair out of the served
              # repo itself is tracked separately (it affects image
              # consumers too).
              echo "excludepkgs=glib2 glib2-devel glib2-static"
            } >> /etc/yum.repos.d/tunaos-published.repo
            index_n=$((index_n + 1))
          done
          dnf -y builddep /work/rpmbuild/SPECS/*.spec
          rpmbuild -ba --define "_topdir /work/rpmbuild" /work/rpmbuild/SPECS/*.spec
        '
    fi
    find "$root/rpmbuild/RPMS" -type f -name '*.rpm' -exec cp -t "$out/artifacts" {} +
    ;;
  deb)
    root="$out/deb"
    python3 scripts/tideforge.py render "$recipe" --target "$target" --output "$root/rendered"
    python3 scripts/assemble-deb-source-tree.py "$recipe" "$root"
    docker run --rm --env SOURCE_DATE_EPOCH --env TZ --env LANG --env LC_ALL \
      --volume "$root:/work" "$image" bash -lc '
        set -euo pipefail
        export DEBIAN_FRONTEND=noninteractive
        # Ubuntu keeps a large share of Debian-synced packages in `universe`,
        # and quickshell needs two of them (libcli11-dev, libcpptrace-dev).
        # Debian has no such component and no ubuntu.sources, so this is a
        # no-op there. It is also a no-op when universe is already enabled --
        # the point is that the buildroot must not depend on whichever
        # components the base image happens to ship with.
        if [ -f /etc/apt/sources.list.d/ubuntu.sources ]; then
          sed -i -E "s/^Components:.*/Components: main restricted universe multiverse/" \
            /etc/apt/sources.list.d/ubuntu.sources
        fi
        apt-get update -qq
        apt-get install -y --no-install-recommends build-essential ca-certificates
        cd "$(cat /work/source-dir)"
        # apt-get build-dep reports an unsatisfiable dependency as a cascade:
        # the one genuinely missing package is buried under a dozen "but it is
        # not going to be installed" lines for packages that are fine. Printing
        # the policy for each declared build-dep first names the real one, so a
        # failure here does not need a second run to interpret.
        echo "==> build-dependency availability"
        awk "/^Build-Depends:/{f=1} f{print} /^$/{f=0}" debian/control \
          | tr "," "\n" | sed -E "s/^Build-Depends: *//; s/\(.*\)//; s/^ +| +$//g" \
          | grep -vE "^$|^debhelper-compat" \
          | while read -r dep; do
              printf "%-28s %s\n" "$dep" \
                "$(apt-cache policy "$dep" 2>/dev/null | awk "/Candidate:/{print \$2; found=1} END{if(!found) print \"NOT AVAILABLE\"}")"
            done
        apt-get build-dep -y --no-install-recommends "$PWD"
        dpkg-buildpackage -us -uc -b
        mkdir -p /work/artifacts
        cp ../*.deb /work/artifacts/
      '
    cp "$root"/artifacts/*.deb "$out/artifacts/"
    ;;
  pkg.tar.zst)
    root="$out/arch"
    python3 scripts/tideforge.py render "$recipe" --target "$target" --output "$root"
    docker run --rm --env SOURCE_DATE_EPOCH --env TZ --env LANG --env LC_ALL \
      --volume "$root:/work" --workdir /work "$image" bash -lc '
        set -euo pipefail
        echo "Server = https://geo.mirror.pkgbuild.com/\$repo/os/\$arch" > /etc/pacman.d/mirrorlist
        pacman -Syu --noconfirm
        pacman -S --needed --noconfirm base-devel sudo
        useradd --create-home builder
        echo "builder ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/builder
        chmod 0440 /etc/sudoers.d/builder
        chown -R builder:builder /work
        su builder -s /bin/bash -c "cd /work && PKGDEST=/work/artifacts makepkg --syncdeps --noconfirm"
        pacman -Qip /work/artifacts/*.pkg.tar.* > /work/package-info.txt
      '
    cp "$root"/artifacts/*.pkg.tar.* "$out/artifacts/"
    cp "$root/package-info.txt" "$out/package-info.txt"
    ;;
  *) echo "unsupported package format: $FORMAT" >&2; exit 2 ;;
esac

find "$out/artifacts" -type f -print
