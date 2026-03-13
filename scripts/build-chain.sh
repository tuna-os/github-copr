#!/usr/bin/env bash
#
# Build Chain Engine
#
# Builds RPM packages tier-by-tier from build-order.yml using mock.
# Packages within a tier build in parallel (--jobs N); tiers are sequential.
#
# Usage:
#   ./scripts/build-chain.sh [options]
#
# Options:
#   --manifest <path>    Path to build-order.yml (default: build-order.yml)
#   --mock-config <cfg>  Mock config to use (default: centos-stream-10-ci)
#   --local-repo <path>  Path to local repo directory (default: ./local-repo)
#   --jobs <N>           Parallel jobs within a tier (default: nproc/2, min 1)
#   --tier <name>        Only build a specific tier
#   --package <path>     Only build a specific package (path as in manifest)
#   --dry-run            Print what would be built without building

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

MANIFEST="${REPO_ROOT}/build-order.yml"
MOCK_CONFIG="centos-stream-10-ci"
LOCAL_REPO="${REPO_ROOT}/local-repo"
JOBS=$(( $(nproc) / 2 ))
[[ $JOBS -lt 1 ]] && JOBS=1
FILTER_TIER=""
FILTER_PACKAGE=""
DRY_RUN=false

# --- Argument parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --manifest)    MANIFEST="$2"; shift 2 ;;
        --mock-config) MOCK_CONFIG="$2"; shift 2 ;;
        --local-repo)  LOCAL_REPO="$2"; shift 2 ;;
        --jobs)        JOBS="$2"; shift 2 ;;
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
log()  { echo "==> $*"; }
err()  { echo "ERROR: $*" >&2; }
plog() { echo "[${1}] ${2}"; }  # prefixed log for parallel output

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

    # Fallback: find any .spec that isn't a bootstrap/rawhide variant
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

# Build a single package. All output goes to stdout so callers can redirect
# to a per-job log file for clean parallel output.
build_package() {
    local pkg_dir="$1"
    local spec_override="$2"

    local spec
    spec="$(find_spec "$pkg_dir" "$spec_override")"
    local pkg_name
    pkg_name="$(basename "$spec" .spec)"
    local abs_pkg_dir="${REPO_ROOT}/${pkg_dir}"

    echo "==> [${pkg_name}] Building from ${pkg_dir} (spec: $(basename "$spec"))"

    if $DRY_RUN; then
        echo "  [dry-run] Would build: ${spec}"
        return 0
    fi

    # Isolated build tree per package
    local builddir
    builddir="$(mktemp -d)"
    trap "rm -rf '${builddir}'" RETURN
    mkdir -p "${builddir}"/{BUILD,BUILDROOT,RPMS,SOURCES,SRPMS,SPECS}

    # Copy spec
    cp "$spec" "${builddir}/SPECS/"

    # Copy local patches and non-tarball sources
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

    # Download tarballs from upstream URLs in the spec
    echo "==> [${pkg_name}] Downloading sources via spectool..."
    spectool -g -C "${builddir}/SOURCES/" "$spec" || {
        echo "ERROR: spectool failed for ${pkg_name} — check Source URLs in spec" >&2
        return 1
    }

    # Build SRPM
    local spec_basename
    spec_basename="$(basename "$spec")"
    echo "==> [${pkg_name}] Building SRPM..."
    rpmbuild -bs "${builddir}/SPECS/${spec_basename}" \
        --define "_topdir ${builddir}" \
        --define "dist .el10"

    local srpm
    srpm="$(find "${builddir}/SRPMS" -name "*.src.rpm" | head -1)"
    if [[ -z "$srpm" ]]; then
        echo "ERROR: No SRPM produced for ${pkg_name}" >&2
        return 1
    fi
    echo "==> [${pkg_name}] SRPM: $(basename "$srpm")"

    # Build RPM with mock — each invocation gets its own unique root name
    # to avoid chroot collisions when running in parallel
    local mock_root="${MOCK_CONFIG}-${pkg_name}"
    echo "==> [${pkg_name}] Building RPMs with mock (root: ${mock_root})..."
    local resultdir="${builddir}/results"
    mkdir -p "$resultdir"

    mock -r "${MOCK_CONFIG}" \
        --uniqueext="${pkg_name}" \
        --rebuild "$srpm" \
        --resultdir="$resultdir" \
        --define "dist .el10" \
        --no-clean \
        --no-cleanup-after

    # Copy results to local repo (atomic per-file cp — safe for parallel callers)
    local rpm_count=0
    while IFS= read -r -d '' rpm; do
        cp "$rpm" "${LOCAL_REPO}/"
        echo "==> [${pkg_name}] -> $(basename "$rpm")"
        rpm_count=$(( rpm_count + 1 ))
    done < <(find "$resultdir" -name "*.rpm" ! -name "*.src.rpm" -print0)

    if [[ $rpm_count -eq 0 ]]; then
        echo "ERROR: No RPMs produced for ${pkg_name}" >&2
        return 1
    fi

    echo "==> [${pkg_name}] Built ${rpm_count} RPM(s)"
}

# Run all packages in a tier with up to $JOBS parallel workers.
# Streams each package's log to stdout as it completes.
build_tier() {
    local tier_name="$1"
    local -n _tier_pkg_total="$2"   # nameref to accumulate count
    local -n _tier_failed="$3"      # nameref to accumulate failures

    local logdir
    logdir="$(mktemp -d)"
    trap "rm -rf '${logdir}'" RETURN

    # Arrays for tracking in-flight jobs
    local pids=()
    local pkg_paths=()
    local active=0

    wait_one() {
        # Wait for any one job to finish; print its log; record failure if needed
        for i in "${!pids[@]}"; do
            local pid="${pids[$i]}"
            local path="${pkg_paths[$i]}"
            if ! kill -0 "$pid" 2>/dev/null; then
                local logfile="${logdir}/$(basename "$path").log"
                cat "$logfile"
                if wait "$pid"; then
                    : # success
                else
                    err "Failed: ${path}"
                    _tier_failed+=("${path}")
                fi
                unset 'pids[$i]' 'pkg_paths[$i]'
                active=$(( active - 1 ))
                return
            fi
        done
        # Nothing finished yet — sleep briefly and retry
        sleep 0.5
        wait_one
    }

    while IFS=$'\t' read -r pkg_path spec_override; do
        if [[ -n "$FILTER_PACKAGE" && "$pkg_path" != "$FILTER_PACKAGE" ]]; then
            continue
        fi

        _tier_pkg_total=$(( _tier_pkg_total + 1 ))

        if $DRY_RUN; then
            build_package "$pkg_path" "$spec_override"
            continue
        fi

        # Throttle to $JOBS concurrent workers
        while [[ $active -ge $JOBS ]]; do
            wait_one
        done

        local logfile="${logdir}/$(basename "$pkg_path").log"
        build_package "$pkg_path" "$spec_override" > "$logfile" 2>&1 &
        pids+=($!)
        pkg_paths+=("$pkg_path")
        active=$(( active + 1 ))
        log "  Started ${pkg_path} (pid $!)"

    done < <(python3 "${SCRIPT_DIR}/parse-build-order.py" "$MANIFEST" --tier "$tier_name")

    # Drain remaining jobs
    while [[ $active -gt 0 ]]; do
        wait_one
    done
}

# --- Main ---
main() {
    log "Build chain starting"
    log "  Manifest:   ${MANIFEST}"
    log "  Mock:       ${MOCK_CONFIG}"
    log "  Local repo: ${LOCAL_REPO}"
    log "  Jobs:       ${JOBS}"
    [[ -n "$FILTER_TIER" ]]    && log "  Tier filter: ${FILTER_TIER}"
    [[ -n "$FILTER_PACKAGE" ]] && log "  Pkg filter:  ${FILTER_PACKAGE}"

    if ! $DRY_RUN && ! command -v mock &>/dev/null; then
        err "mock is not installed"
        exit 1
    fi

    ensure_local_repo

    local tiers
    tiers="$(python3 "${SCRIPT_DIR}/parse-build-order.py" "$MANIFEST" --tiers)"

    local tier_count=0
    local pkg_total=0
    local failed=()

    while IFS= read -r tier_name; do
        if [[ -n "$FILTER_TIER" && "$tier_name" != "$FILTER_TIER" ]]; then
            continue
        fi

        tier_count=$(( tier_count + 1 ))
        log ""
        log "===== Tier: ${tier_name} (jobs=${JOBS}) ====="

        build_tier "$tier_name" pkg_total failed

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
