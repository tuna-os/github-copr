#!/usr/bin/env bash
# Build one row emitted by plan-package-factory.py. Family and distro are data;
# this file contains only native package-format adapters.
set -eEuo pipefail

cell_id=${CELL_ID:?}
engine=${ENGINE:?}
target=${TARGET:?}
architecture=${ARCHITECTURE:?}
image=${IMAGE:?}
out=${OUT_DIR:-"$PWD/.factory/$cell_id"}
mkdir -p "$out/artifacts"

export SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:?}
export TZ=UTC LANG=C.UTF-8 LC_ALL=C.UTF-8

if [[ $engine == build-chain ]]; then
    args=(--manifest "${MANIFEST:?}" --backend podman --image "$image"
          --mock-config "${MOCK_CONFIG:?}" --local-repo "$out/artifacts"
          --with-checks)
    ./scripts/build-chain.sh "${args[@]}"
    exit 0
fi

[[ $engine == tideforge ]] || { echo "unknown factory engine: $engine" >&2; exit 2; }
recipe=${RECIPE:?}
python3 scripts/tideforge.py validate "$recipe"
python3 scripts/verify-tideforge-source.py "$recipe" --cache-dir "$HOME/.cache/tideforge/sources"

case ${FORMAT:?} in
  rpm)
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
        --volume "$root:/work" "$image" bash -lc '
          set -euo pipefail
          dnf -y install dnf-plugins-core rpm-build
          if [[ "${TARGET:-}" == el10 ]]; then
            dnf -y install epel-release
            dnf config-manager --set-enabled crb
          fi
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
        apt-get update -qq
        apt-get install -y --no-install-recommends build-essential ca-certificates
        cd "$(cat /work/source-dir)"
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
