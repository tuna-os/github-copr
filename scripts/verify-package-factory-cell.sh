#!/usr/bin/env bash
# Verify one unified matrix row. Package-format mechanics live here; session
# requirements remain recipe/queue data and are invoked through their gates.
set -eEuo pipefail

out=${OUT_DIR:-"$PWD/.factory/${CELL_ID:?}"}
artifacts="$out/artifacts"
test -d "$artifacts"

if [[ ${ENGINE:?} == build-chain ]]; then
  mapfile -d '' rpms < <(find "$artifacts" -type f -name '*.rpm' -print0)
  ((${#rpms[@]} > 0)) || { echo "native queue produced no RPMs" >&2; exit 1; }
  rpm -qp "${rpms[@]}" >/dev/null
  exit 0
fi

recipe=${RECIPE:?}
python3 scripts/tideforge.py verify "$recipe" --target "${TARGET:?}" --field smoke > "$out/smoke.sh"
install_name=$(python3 scripts/tideforge.py verify "$recipe" --target "$TARGET" --field install_name)

case ${FORMAT:?} in
  rpm)
    docker run --rm --volume "$artifacts:/artifacts:ro" \
      --volume "$PWD/scripts:/scripts:ro" "${IMAGE:?}" \
      bash /scripts/lint-generated-rpm.sh /artifacts
    docker run --rm --env INSTALL_NAME="$install_name" \
      --volume "$artifacts:/artifacts:ro" --volume "$out/smoke.sh:/smoke.sh:ro" \
      --volume "$PWD/scripts:/scripts:ro" "${IMAGE:?}" bash -lc '
        set -euo pipefail
        if command -v zypper >/dev/null; then
          zypper --non-interactive install createrepo_c
          createrepo_c /artifacts
          zypper --non-interactive addrepo --no-gpgcheck --priority 1 file:///artifacts tideforge
          zypper --non-interactive --gpg-auto-import-keys refresh tideforge
          zypper --non-interactive --no-gpg-checks install "$INSTALL_NAME"
        else
          dnf -y install createrepo_c
          createrepo_c /artifacts
          dnf -y install --nogpgcheck --repofrompath tideforge,file:///artifacts \
            --setopt=tideforge.priority=1 --enablerepo=tideforge "$INSTALL_NAME"
        fi
        rpm -q "$INSTALL_NAME"
        bash /smoke.sh
      '
    ;;
  deb)
    docker run --rm --volume "$artifacts:/artifacts:ro" \
      --volume "$PWD/scripts:/scripts:ro" "${IMAGE:?}" \
      bash /scripts/lint-generated-deb.sh /artifacts
    docker run --rm --env INSTALL_NAME="$install_name" \
      --volume "$artifacts:/artifacts:ro" --volume "$out/smoke.sh:/smoke.sh:ro" \
      "${IMAGE:?}" bash -lc '
        set -euo pipefail
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq
        apt-get install -y --no-install-recommends dpkg-dev pkg-config
        mkdir /repo && cp /artifacts/*.deb /repo/ && cd /repo
        dpkg-scanpackages . /dev/null | gzip -9c > Packages.gz
        printf "deb [trusted=yes] file:/repo ./\n" > /etc/apt/sources.list.d/tideforge.list
        printf "Package: *\nPin: origin \"\"\nPin-Priority: 1001\n" > /etc/apt/preferences.d/tideforge.pref
        apt-get update -qq
        apt-get install -y "$INSTALL_NAME"
        dpkg-query -W "$INSTALL_NAME"
        bash /smoke.sh
      '
    ;;
  pkg.tar.zst)
    python3 scripts/validate-built-arch-package.py "$recipe" "$out/package-info.txt"
    docker run --rm --user root --volume "$artifacts:/artifacts:ro" \
      --volume "$out/smoke.sh:/smoke.sh:ro" --volume "$PWD/scripts:/scripts:ro" \
      "${IMAGE:?}" bash /scripts/arch-clean-install.sh "$install_name" /artifacts bash /smoke.sh
    ;;
  *) echo "unsupported package format: $FORMAT" >&2; exit 2 ;;
esac
