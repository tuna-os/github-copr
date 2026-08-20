#!/usr/bin/env bash
# Verify one unified matrix row. Package-format mechanics live here; session
# requirements remain recipe/queue data and are invoked through their gates.
set -eEuo pipefail

out=${OUT_DIR:-"$PWD/.factory/${CELL_ID:?}"}
artifacts="$out/artifacts"
test -d "$artifacts"

if [[ ${ENGINE:?} == build-chain ]]; then
  mapfile -d '' rpms < <(find "$artifacts" -type f -name '*.rpm' ! -name '*.src.rpm' -print0)
  ((${#rpms[@]} > 0)) || { echo "native queue produced no RPMs" >&2; exit 1; }
  docker run --rm --entrypoint /bin/bash --volume "$artifacts:/artifacts:ro" \
    --volume "$PWD/scripts:/scripts:ro" "${IMAGE:?}" \
    /scripts/lint-generated-rpm.sh /artifacts
  docker run --rm --entrypoint /bin/bash \
    --env TARGET="${TARGET:?}" --volume "$artifacts:/artifacts:ro" "${IMAGE:?}" -lc '
    set -euo pipefail
    dnf -y install createrepo_c
    mkdir /factory-repo
    find /artifacts -maxdepth 1 -type f -name "*.rpm" ! -name "*.src.rpm" -exec cp -t /factory-repo {} +
    createrepo_c /factory-repo
    dnf -y install --nogpgcheck --repofrompath factory,file:///factory-repo \
      --setopt=factory.priority=1 --enablerepo=factory /factory-repo/*.rpm
    mapfile -t names < <(rpm -qp --qf "%{NAME}\n" /factory-repo/*.rpm | sort -u)
    rpm -q "${names[@]}"
    rpm -V "${names[@]}"
  '
  exit 0
fi

recipe=${RECIPE:?}
if python3 - "$recipe" <<'PY'
import pathlib, sys, yaml
recipe = yaml.safe_load(pathlib.Path(sys.argv[1]).read_text()) or {}
raise SystemExit(0 if recipe.get("verify") else 1)
PY
then
  python3 scripts/tideforge.py verify "$recipe" --target "${TARGET:?}" --field smoke > "$out/smoke.sh"
  install_name=$(python3 scripts/tideforge.py verify "$recipe" --target "$TARGET" --field install_name)
else
  printf 'true\n' > "$out/smoke.sh"
  install_name=$(python3 - "$recipe" <<'PY'
import pathlib, sys, yaml
recipe = yaml.safe_load(pathlib.Path(sys.argv[1]).read_text()) or {}
print(recipe.get("name") or pathlib.Path(sys.argv[1]).parent.name)
PY
)
fi

case ${FORMAT:?} in
  rpm)
    # Cross-cell dependency resolution (#440): a clean-install verify of a
    # package whose runtime deps are themselves in the gap (e.g. niri needs
    # libseat) can only resolve them from the PUBLISHED factory repo, built by
    # earlier waves. The target contract's `published_index` (served read URL,
    # distinct from `r2_path`) is added as a lower-priority dnf/zypper repo so
    # the local cell artifacts win and the published repo only fills in deps.
    published_index="$(python3 - "$TARGET" "${ARCHITECTURE:-}" <<'PY'
import pathlib, sys, yaml
d = yaml.safe_load(pathlib.Path("manifests/package-factory.yaml").read_text()) or {}
t = d.get("targets", {}).get(sys.argv[1]) or {}
print((t.get("published_index") or {}).get(sys.argv[2], ""))
PY
)"
    docker run --rm --entrypoint /bin/bash --volume "$artifacts:/artifacts:ro" \
      --volume "$PWD/scripts:/scripts:ro" "${IMAGE:?}" \
      /scripts/lint-generated-rpm.sh /artifacts
    docker run --rm --entrypoint /bin/bash --env INSTALL_NAME="$install_name" \
      --env PUBLISHED_INDEX="$published_index" \
      --volume "$artifacts:/artifacts:ro" --volume "$out/smoke.sh:/smoke.sh:ro" \
      --volume "$PWD/scripts:/scripts:ro" "${IMAGE:?}" -lc '
        set -euo pipefail
        mkdir /factory-repo
        cp /artifacts/*.rpm /factory-repo/
        if command -v zypper >/dev/null; then
          zypper --non-interactive install createrepo_c
          createrepo_c /factory-repo
          zypper --non-interactive addrepo --no-gpgcheck --priority 1 file:///factory-repo tideforge
          if [ -n "$PUBLISHED_INDEX" ]; then
            zypper --non-interactive addrepo --no-gpgcheck --priority 50 "$PUBLISHED_INDEX" tunaos-published
          fi
          zypper --non-interactive --gpg-auto-import-keys refresh
          zypper --non-interactive --no-gpg-checks install "$INSTALL_NAME"
        else
          dnf -y install createrepo_c
          createrepo_c /factory-repo
          dnf -y install --nogpgcheck --repofrompath tideforge,file:///factory-repo \
            --setopt=tideforge.priority=1 --enablerepo=tideforge \
            ${PUBLISHED_INDEX:+--repofrompath tunaos,"$PUBLISHED_INDEX" --setopt=tunaos.priority=50 --enablerepo=tunaos} \
            "$INSTALL_NAME"
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
