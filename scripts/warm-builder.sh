#!/usr/bin/env bash
#
# Build a cell on a host that REMEMBERS, so a failure costs one package
# instead of a run.
#
# ## Why
#
# Every leg of this factory runs on an ephemeral runner, and the only thing
# that survives between legs is the published index -- which a fan-out
# updates once, after its last band. So the loop that bringing up a desktop
# actually consists of --
#
#     dispatch -> wait 4h -> read the tail -> fix one spec -> dispatch again
#
# -- re-pays for every package that already built, every time. On the night
# of 2026-08-28 two waves were cancelled mid-flight (three hours each) and
# published nothing at all; the third rebuilt from the same 580 served
# packages the first had.
#
# Nothing in build-chain.sh requires that. It already skips a package whose
# exact NVR sits in the local repo (check_package_exists), and it already
# shares one mock root cache across a chain when MOCK_CACHE_DIR is set. Both
# mechanisms are per-run only because the directories they use are per-run.
# Point them at a persistent volume and the same code converges instead:
#
#     first run     builds the chain, banks every RPM
#     spec fix      --forget <pkg> drops that package's RPMs
#     next run      rebuilds that package and whatever needs it; skips the rest
#
# ## What persists
#
#   <state>/local-repo             every RPM built so far, indexed. The skip.
#   <state>/mock-cache/<cfg>/root_cache
#                                  the minimal buildroot tarball. Rebuilding
#                                  it per package is 34.1% of all mock time
#                                  (docs/hummingbird-throughput.md Finding 2).
#   <state>/served-nvrs.txt        what the published index carries, refreshed
#                                  each run so CI's progress is skipped too.
#
# ## What this is NOT
#
# Not a publisher. It never touches R2, never signs anything, and its
# local-repo is not a repository anyone consumes -- promotion stays with the
# gated publishers, for the reasons INCIDENT-repo-wipe-gnome.md records. This
# is the bringup loop: get the chain green here, then let CI build and
# publish it from a clean runner, where the result is reproducible rather
# than merely present.
#
# Usage:
#   scripts/warm-builder.sh --cell hummingbird-x86_64
#   scripts/warm-builder.sh --cell hummingbird-x86_64 --forget gtk4
#   scripts/warm-builder.sh --cell hummingbird-x86_64 --status
#   scripts/warm-builder.sh --cell gnome51-el10-x86_64 --tiers bootstrap-00
#
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CELL=""
STATE_ROOT="${TUNAOS_WARM_STATE:-${XDG_CACHE_HOME:-$HOME/.cache}/tunaos-warm}"
FORGET=()
STATUS=false
REFRESH_SERVED=true
PASSTHROUGH=()

usage() {
    sed -n '2,/^set -euo/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//;$d'
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)   usage; exit 0 ;;
        --cell)      CELL="$2";       shift 2 ;;
        --state)     STATE_ROOT="$2"; shift 2 ;;
        --forget)    FORGET+=("$2");  shift 2 ;;
        --status)    STATUS=true;     shift ;;
        --offline)   REFRESH_SERVED=false; shift ;;
        # Everything build-chain.sh understands rides through unchanged:
        # --tiers, --package, --packages-file, --jobs, --dry-run, --force.
        *)           PASSTHROUGH+=("$1"); shift ;;
    esac
done

[[ -n "$CELL" ]] || { echo "ERROR: --cell is required" >&2; usage >&2; exit 2; }

# The cell's shape comes from manifests/package-builds.yaml, never from flags.
# A warm builder that took its own manifest and mock config would be a second
# definition of what a cell is, and the two would drift -- which is the defect
# that made a cache serve output built from the wrong spec.
if ! _cell_env="$(python3 - "$CELL" << 'PY'
import sys, shlex, yaml
cell_id = sys.argv[1]
builds = yaml.safe_load(open("manifests/package-builds.yaml"))
for cell in builds["native_builds"]:
    if cell["id"] == cell_id:
        break
else:
    ids = ", ".join(c["id"] for c in builds["native_builds"])
    sys.exit(f"{cell_id} is not a cell. Have: {ids}")
factory = yaml.safe_load(open("manifests/package-factory.yaml"))
target = factory["targets"].get(cell["target"], {})
index = (target.get("published_index") or {}).get(cell["architecture"]) or []
if isinstance(index, str):
    index = [index]
print(f"MANIFEST={shlex.quote(cell['manifest'])}")
print(f"MOCK_CONFIG={shlex.quote(cell['mock_config'])}")
print(f"BUILD_IMAGE={shlex.quote(cell['image'])}")
print(f"SERVED_URL={shlex.quote(index[0] if index else '')}")
PY
)"; then
    # Non-zero here means the cell is unknown or the manifests do not parse.
    # eval'ing the resolver's output on that path would run whatever it
    # managed to print before dying, so the check comes first and the eval
    # only ever sees a complete, successful resolution.
    exit 2
fi
eval "$_cell_env"

STATE="${STATE_ROOT}/${CELL}"
LOCAL_REPO="${STATE}/local-repo"
SERVED="${STATE}/served-nvrs.txt"
mkdir -p "$LOCAL_REPO" "${STATE}/mock-cache"

banked() { find "$LOCAL_REPO" -maxdepth 1 -name '*.rpm' 2>/dev/null | wc -l; }

# --forget: drop everything a source package produced, so the next run
# rebuilds it. This is the whole fix-and-retry loop, and it has to be exact in
# both directions.
#
# Deleting too LITTLE is the dangerous half. build-chain.sh's skip matches the
# main binary's NVR only (`ls <name>-<v>-<r>*.rpm`), so removing just that
# leaves gtk4-devel-4.23.1 sitting in the local repo: the rebuilt gtk4 lands
# beside stale headers from the build that failed, and every dependent
# compiles against a -devel its own gtk4 never produced.
#
# Deleting too MUCH is the other half: gtk4-layer-shell is a different source
# package that merely shares a prefix, and forgetting it turns a one-package
# retry into a chain.
#
# %{SOURCERPM} answers both exactly, so it is asked first. The version-release
# fallback exists for a host without rpm(1): subpackages carry their source's
# exact V-R, so `gtk4-*-4.23.1-1.fc43.*` is the same set, while
# gtk4-layer-shell's 1.2.0-1.fc43 is not.
forget_one() {
    local name="$1" rpm_file source_rpm vr matched=0
    if command -v rpm >/dev/null 2>&1; then
        while IFS= read -r rpm_file; do
            source_rpm="$(rpm -qp --nosignature --qf '%{SOURCERPM}' \
                "$rpm_file" 2>/dev/null || true)"
            # gtk4-4.23.1-1.fc43.src.rpm -> gtk4
            if [[ "${source_rpm%-*-*}" == "$name" ]]; then
                rm -f -- "$rpm_file"
                matched=$((matched + 1))
            fi
        done < <(find "$LOCAL_REPO" -maxdepth 1 -name "${name}-*.rpm")
        if (( matched )); then
            printf 'forgetting %s (%d rpm(s), by %%{SOURCERPM})\n' \
                "$name" "$matched" >&2
            return 0
        fi
    fi
    while IFS= read -r rpm_file; do
        # <name>-<version>-<release>.<arch>.rpm -> <version>-<release>
        vr="$(basename "$rpm_file" .rpm)"
        vr="${vr%.*}"
        vr="${vr#"${name}"-}"
        [[ "$vr" == *-* ]] || continue
        while IFS= read -r sibling; do
            rm -f -- "$sibling"
            matched=$((matched + 1))
        done < <(find "$LOCAL_REPO" -maxdepth 1 -name "${name}-*${vr}.*.rpm")
    done < <(find "$LOCAL_REPO" -maxdepth 1 -name "${name}-[0-9]*.rpm")
    if (( matched )); then
        printf 'forgetting %s (%d rpm(s), by version-release)\n' \
            "$name" "$matched" >&2
    else
        echo "nothing banked for ${name}; it will build anyway" >&2
    fi
}

for name in ${FORGET+"${FORGET[@]}"}; do
    forget_one "$name"
done
if (( ${#FORGET[@]} )); then
    # The index must stop advertising what was just deleted, or the buildroot
    # resolves a package whose file is gone and the build fails on a 404
    # rather than rebuilding.
    rm -rf "${LOCAL_REPO}/repodata" "${LOCAL_REPO}/.repodata"
    createrepo_c "$LOCAL_REPO" >/dev/null
fi

# Reported AFTER any --forget above, so `--forget gtk4 --status` shows the
# repo the next build will see rather than the one before the drop.
if [[ "$STATUS" == true ]]; then
    echo "cell        ${CELL}"
    echo "state       ${STATE}"
    echo "manifest    ${MANIFEST}"
    echo "mock config ${MOCK_CONFIG}"
    echo "banked RPMs $(banked)"
    echo "root cache  $(du -sh "${STATE}/mock-cache" 2>/dev/null | cut -f1 || echo 0)"
    if [[ -f "$SERVED" ]]; then
        echo "served NVRs $(wc -l < "$SERVED") (as of $(date -r "$SERVED" '+%F %T'))"
    fi
    exit 0
fi

# Skip what CI already published as well as what this host built. Without
# this the warm builder happily rebuilds the 580 packages the index serves.
if [[ "$REFRESH_SERVED" == true && -n "$SERVED_URL" ]]; then
    python3 "${REPO_ROOT}/scripts/list-served-nvrs.py" "$SERVED_URL" > "$SERVED" || true
fi
[[ -f "$SERVED" ]] || : > "$SERVED"

before="$(banked)"
echo "==> ${CELL}: ${before} RPM(s) banked, $(wc -l < "$SERVED") served; building"

# MOCK_CACHE_DIR is what makes the second package cheap: build-chain.sh mounts
# <dir>/<config>/root_cache into mock, and mock unpacks the minimal buildroot
# instead of creating it. package-factory-cell.yml points it at runner.temp
# deliberately -- there the win is only WITHIN a job. Here it is across runs,
# which is the entire point of a warm host.
export MOCK_CACHE_DIR="${STATE}/mock-cache"

set +e
bash "${REPO_ROOT}/scripts/build-chain.sh" \
    --manifest "${REPO_ROOT}/${MANIFEST}" \
    --mock-config "$MOCK_CONFIG" \
    --image "$BUILD_IMAGE" \
    --local-repo "$LOCAL_REPO" \
    --served-nvrs "$SERVED" \
    ${PASSTHROUGH+"${PASSTHROUGH[@]}"}
rc=$?
set -e

after="$(banked)"
echo "==> ${CELL}: banked ${before} -> ${after} (+$((after - before))) in ${LOCAL_REPO}"
if (( rc != 0 )); then
    echo "==> chain exited ${rc}. Fix the spec, then:" >&2
    echo "      scripts/warm-builder.sh --cell ${CELL} --forget <package>" >&2
    echo "    Everything else stays banked; only that package and its" >&2
    echo "    dependents rebuild." >&2
fi
exit "$rc"
