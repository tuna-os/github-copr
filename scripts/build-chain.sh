#!/usr/bin/env bash
#
# Build Chain Engine
#
# Builds RPM packages tier-by-tier from build-order.yml using mock.
# Packages within a tier build sequentially (parallel TODO); tiers are sequential.
#
# Usage:
#   ./scripts/build-chain.sh [options]
#
# Options:
#   --manifest <path>    Path to build-order.yml (default: build-order.yml)
#   --mock-config <cfg>  Mock config to use (default: centos-stream-10-ci)
#   --local-repo <path>  Path to local repo directory (default: ./local-repo)
#   --tier <name>        Only build a specific tier
#   --package <path>     Only build a specific package (path as in manifest)
#   --dry-run            Print what would be built without building

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

MANIFEST="${REPO_ROOT}/build-order.yml"
MOCK_CONFIG="centos-stream-10-ci"
LOCAL_REPO="${REPO_ROOT}/local-repo"
FILTER_TIER=""
FILTER_PACKAGE=""
DRY_RUN=false

# --- Argument parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --manifest)    MANIFEST="$2"; shift 2 ;;
        --mock-config) MOCK_CONFIG="$2"; shift 2 ;;
        --local-repo)  LOCAL_REPO="$2"; shift 2 ;;
        --tier)        FILTER_TIER="$2"; shift 2 ;;
        --package)     FILTER_PACKAGE="$2"; shift 2 ;;
        --dry-run)     DRY_RUN=true; shift ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# --- Helpers ---
log() { echo "==> $*"; }
err() { echo "ERROR: $*" >&2; }

ensure_local_repo() {
    mkdir -p "${LOCAL_REPO}"
    if [[ ! -f "${LOCAL_REPO}/repodata/repomd.xml" ]]; then
        log "Initializing local repo at ${LOCAL_REPO}"
        createrepo_c "${LOCAL_REPO}"
    fi
}

update_local_repo() {
    log "Updating local repo metadata"
    createrepo_c --update "${LOCAL_REPO}"
}

find_spec() {
    local pkg_dir="$1"
    local spec_override="$2"

    if [[ -n "$spec_override" ]]; then
        local spec="${REPO_ROOT}/${pkg_dir}/${spec_override}"
        if [[ -f "$spec" ]]; then
            echo "$spec"
            return
        fi
        err "spec_override '${spec_override}' not found in ${pkg_dir}"
        return 1
    fi

    # Find the default spec: the one matching the directory name, or the only one
    local dir_name
    dir_name="$(basename "$pkg_dir")"
    local default_spec="${REPO_ROOT}/${pkg_dir}/${dir_name}.spec"
    if [[ -f "$default_spec" ]]; then
        echo "$default_spec"
        return
    fi

    # Fallback: find any .spec that isn't a bootstrap variant
    local specs=()
    while IFS= read -r -d '' f; do
        if [[ ! "$f" =~ -bootstrap\.spec$ ]] && [[ ! "$f" =~ -rawhide\.spec$ ]]; then
            specs+=("$f")
        fi
    done < <(find "${REPO_ROOT}/${pkg_dir}" -maxdepth 1 -name "*.spec" -print0)

    if [[ ${#specs[@]} -eq 1 ]]; then
        echo "${specs[0]}"
        return
    fi

    err "Cannot determine spec for ${pkg_dir} (found ${#specs[@]} candidates)"
    return 1
}

build_package() {
    local pkg_dir="$1"
    local spec_override="$2"

    local spec
    spec="$(find_spec "$pkg_dir" "$spec_override")"
    local pkg_name
    pkg_name="$(basename "$spec" .spec)"
    local abs_pkg_dir="${REPO_ROOT}/${pkg_dir}"

    log "Building ${pkg_name} from ${pkg_dir} (spec: $(basename "$spec"))"

    if $DRY_RUN; then
        echo "  [dry-run] Would build: ${spec}"
        return 0
    fi

    # Set up rpmbuild tree
    local builddir
    builddir="$(mktemp -d)"
    trap "rm -rf '${builddir}'" RETURN
    mkdir -p "${builddir}"/{BUILD,BUILDROOT,RPMS,SOURCES,SRPMS,SPECS}

    # Copy spec
    cp "$spec" "${builddir}/SPECS/"

    # Copy local patches and non-tarball sources from package directory
    find "$abs_pkg_dir" -maxdepth 1 -type f \
        ! -name "*.spec" \
        ! -name "sources" \
        ! -name "changelog" \
        ! -name "rpminspect.yaml" \
        ! -name "*.md" \
        ! -name "*.tar.gz" \
        ! -name "*.tar.xz" \
        ! -name "*.tar.bz2" \
        ! -name "*.tgz" \
        ! -name "*.zip" \
        -exec cp {} "${builddir}/SOURCES/" \;

    # Download tarballs from upstream URLs declared in the spec
    log "  Downloading sources via spectool..."
    spectool -g -C "${builddir}/SOURCES/" "$spec" 2>&1 | sed 's/^/    /' || {
        err "spectool failed for ${pkg_name} — check Source URLs in spec"
        return 1
    }

    # Build SRPM
    local spec_basename
    spec_basename="$(basename "$spec")"
    log "  Building SRPM..."
    rpmbuild -bs "${builddir}/SPECS/${spec_basename}" \
        --define "_topdir ${builddir}" \
        --define "dist .el10" \
        2>&1 | sed 's/^/    /'

    local srpm
    srpm="$(find "${builddir}/SRPMS" -name "*.src.rpm" | head -1)"
    if [[ -z "$srpm" ]]; then
        err "No SRPM produced for ${pkg_name}"
        return 1
    fi
    log "  SRPM: $(basename "$srpm")"

    # Build RPM with mock
    log "  Building RPMs with mock (config: ${MOCK_CONFIG})..."
    local resultdir="${builddir}/results"
    mkdir -p "$resultdir"

    mock -r "${MOCK_CONFIG}" \
        --rebuild "$srpm" \
        --resultdir="$resultdir" \
        --define "dist .el10" \
        --no-clean \
        --no-cleanup-after \
        2>&1 | sed 's/^/    /'

    # Copy results to local repo
    local rpm_count=0
    while IFS= read -r -d '' rpm; do
        cp "$rpm" "${LOCAL_REPO}/"
        log "  -> $(basename "$rpm")"
        ((rpm_count++))
    done < <(find "$resultdir" -name "*.rpm" ! -name "*.src.rpm" -print0)

    if [[ $rpm_count -eq 0 ]]; then
        err "No RPMs produced for ${pkg_name}"
        return 1
    fi

    log "  Built ${rpm_count} RPM(s) for ${pkg_name}"
}

# --- Main ---
main() {
    log "Build chain starting"
    log "  Manifest:   ${MANIFEST}"
    log "  Mock:       ${MOCK_CONFIG}"
    log "  Local repo: ${LOCAL_REPO}"
    [[ -n "$FILTER_TIER" ]] && log "  Tier filter: ${FILTER_TIER}"
    [[ -n "$FILTER_PACKAGE" ]] && log "  Pkg filter:  ${FILTER_PACKAGE}"

    if ! command -v mock &>/dev/null; then
        err "mock is not installed"
        exit 1
    fi

    ensure_local_repo

    # Get tier list
    local tiers
    tiers="$(python3 "${SCRIPT_DIR}/parse-build-order.py" "$MANIFEST" --tiers)"

    local tier_count=0
    local pkg_total=0
    local failed=()

    while IFS= read -r tier_name; do
        # Apply tier filter
        if [[ -n "$FILTER_TIER" && "$tier_name" != "$FILTER_TIER" ]]; then
            continue
        fi

        tier_count=$(( tier_count + 1 ))
        log ""
        log "===== Tier: ${tier_name} ====="

        # Get packages in this tier
        while IFS=$'\t' read -r pkg_path spec_override; do
            # Apply package filter
            if [[ -n "$FILTER_PACKAGE" && "$pkg_path" != "$FILTER_PACKAGE" ]]; then
                continue
            fi

            pkg_total=$(( pkg_total + 1 ))

            if build_package "$pkg_path" "$spec_override"; then
                : # success
            else
                err "Failed to build ${pkg_path}"
                failed+=("${pkg_path}")
            fi
        done < <(python3 "${SCRIPT_DIR}/parse-build-order.py" "$MANIFEST" --tier "$tier_name")

        # Update repo after each tier so the next tier can use the new packages
        if ! $DRY_RUN; then
            update_local_repo
        fi

    done <<< "$tiers"

    log ""
    log "===== Summary ====="
    log "Tiers processed: ${tier_count}"
    log "Packages built:  ${pkg_total}"

    if [[ ${#failed[@]} -gt 0 ]]; then
        err "Failed packages (${#failed[@]}):"
        for f in "${failed[@]}"; do
            err "  - ${f}"
        done
        exit 1
    fi

    log "All packages built successfully!"
}

main
