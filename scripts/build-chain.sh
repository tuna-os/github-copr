#!/usr/bin/env bash
#
# Build Chain Engine
#
# Builds RPM packages tier-by-tier from build-order.yml.
# Packages within a tier build in parallel (--jobs N); tiers are sequential.
#
# Backends:
#   podman  - runs rpmbuild inside a CentOS Stream 10 container (default)
#   mock    - uses mock chroots (requires mock group membership)
#
# Usage:
#   ./scripts/build-chain.sh [options]
#
# Options:
#   --manifest <path>    Path to build-order.yml (default: build-order.yml)
#   --backend <name>     Build backend: podman or mock (default: podman)
#   --image <ref>        Container image for podman backend
#                        (default: quay.io/centos/centos:stream10)
#   --mock-config <cfg>  Mock config name (default: centos-stream-10-ci)
#   --local-repo <path>  Path to local repo directory (default: ./local-repo)
#   --jobs <N>           Parallel jobs within a tier (default: nproc/2)
#   --tier <name>        Only build a specific tier
#   --package <path>     Only build a specific package path
#   --dry-run            Print what would be built without building

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

MANIFEST="${REPO_ROOT}/build-order.yml"
BACKEND="podman"
BUILD_IMAGE="ghcr.io/tuna-os/mock-runner:centos-stream-10"
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
        --manifest)    MANIFEST="$2";    shift 2 ;;
        --backend)     BACKEND="$2";     shift 2 ;;
        --image)       BUILD_IMAGE="$2"; shift 2 ;;
        --mock-config) MOCK_CONFIG="$2"; shift 2 ;;
        --local-repo)  LOCAL_REPO="$2";  shift 2 ;;
        --jobs)        JOBS="$2";        shift 2 ;;
        --tier)        FILTER_TIER="$2"; shift 2 ;;
        --package)     FILTER_PACKAGE="$2"; shift 2 ;;
        --dry-run)     DRY_RUN=true;     shift ;;
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

    local dir_name
    dir_name="$(basename "$pkg_dir")"
    local default_spec="${REPO_ROOT}/${pkg_dir}/${dir_name}.spec"
    if [[ -f "$default_spec" ]]; then
        echo "$default_spec"
        return
    fi

    # Fallback: any .spec that isn't a bootstrap/rawhide variant
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

# Prepare a build tree (spec + patches + downloaded sources) in $builddir.
# Does NOT build — just stages everything so a backend can pick it up.
prepare_sources() {
    local builddir="$1"
    local spec="$2"
    local abs_pkg_dir="$3"
    local pkg_name
    pkg_name="$(basename "$spec" .spec)"

    mkdir -p "${builddir}"/{BUILD,BUILDROOT,RPMS,SOURCES,SRPMS,SPECS}

    cp "$spec" "${builddir}/SPECS/"

    # Copy patches and non-tarball sources
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

    echo "==> [${pkg_name}] Downloading sources via spectool..."
    spectool -g -C "${builddir}/SOURCES/" "$spec" || {
        echo "ERROR: spectool failed for ${pkg_name}" >&2
        return 1
    }
}

# --- Podman backend (mock-in-podman) ---
#
# Builds the SRPM on the host, then runs `mock --rebuild` inside a
# privileged Fedora container. Mock handles all CentOS 10 dep resolution
# and package name mappings correctly. The local-repo is bind-mounted into
# the container so mock can see RPMs built in earlier tiers.
build_package_podman() {
    local pkg_dir="$1"
    local spec_override="$2"

    local spec pkg_name abs_pkg_dir
    spec="$(find_spec "$pkg_dir" "$spec_override")"
    pkg_name="$(basename "$spec" .spec)"
    abs_pkg_dir="${REPO_ROOT}/${pkg_dir}"

    echo "==> [${pkg_name}] Building (podman+mock) from ${pkg_dir}"

    local builddir
    builddir="$(mktemp -d)"
    trap "rm -rf '${builddir}'" RETURN

    prepare_sources "$builddir" "$spec" "$abs_pkg_dir"

    # Build SRPM on the host (just file prep, no target-distro deps needed)
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

    local resultdir="${builddir}/results"
    mkdir -p "$resultdir"

    # Write the mock config for use inside the container
    local mock_cfg="${builddir}/centos-stream-10-ci.cfg"
    cat > "$mock_cfg" << 'MOCKCFG'
include('/etc/mock/centos-stream-10-x86_64.cfg')
config_opts['root'] = 'centos-stream-10-ci'
config_opts['yum.conf'] += """
[local-build]
name=Local Build Repo
baseurl=file:///local-repo
enabled=1
gpgcheck=0
priority=1
module_hotfixes=1

[epel]
name=Extra Packages for Enterprise Linux 10 - x86_64
baseurl=https://dl.fedoraproject.org/pub/epel/10/Everything/x86_64
enabled=1
gpgcheck=0
priority=10
"""
config_opts['plugin_conf']['bind_mount_enable'] = True
config_opts['plugin_conf']['bind_mount_opts']['dirs'].append(
    ('/local-repo', '/local-repo')
)
MOCKCFG

    echo "==> [${pkg_name}] Running mock inside podman (${BUILD_IMAGE})..."

    podman run --rm --privileged \
        --pull=missing \
        -v "${builddir}:/builddir:Z" \
        -v "${LOCAL_REPO}:/local-repo:Z" \
        "${BUILD_IMAGE}" \
        bash -exc "
            createrepo_c /local-repo/
            mock -r centos-stream-10-ci \
                --uniqueext='${pkg_name}' \
                --rebuild /builddir/SRPMS/*.src.rpm \
                --resultdir=/builddir/results \
                --define 'dist .el10' \
                --no-clean \
                --no-cleanup-after
        "

    # Collect RPMs from results
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

# --- Mock backend ---
build_package_mock() {
    local pkg_dir="$1"
    local spec_override="$2"

    local spec pkg_name abs_pkg_dir builddir
    spec="$(find_spec "$pkg_dir" "$spec_override")"
    pkg_name="$(basename "$spec" .spec)"
    abs_pkg_dir="${REPO_ROOT}/${pkg_dir}"

    echo "==> [${pkg_name}] Building (mock) from ${pkg_dir}"

    builddir="$(mktemp -d)"
    trap "rm -rf '${builddir}'" RETURN

    prepare_sources "$builddir" "$spec" "$abs_pkg_dir"

    local spec_basename
    spec_basename="$(basename "$spec")"

    # Build SRPM
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

    echo "==> [${pkg_name}] Rebuilding with mock (uniqueext=${pkg_name})..."
    local resultdir="${builddir}/results"
    mkdir -p "$resultdir"

    mock -r "${MOCK_CONFIG}" \
        --uniqueext="${pkg_name}" \
        --rebuild "$srpm" \
        --resultdir="$resultdir" \
        --define "dist .el10" \
        --no-clean \
        --no-cleanup-after

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

# Dispatch to the selected backend
build_package() {
    local pkg_dir="$1"
    local spec_override="$2"

    if $DRY_RUN; then
        local spec
        spec="$(find_spec "$pkg_dir" "$spec_override")"
        echo "==> [$(basename "$spec" .spec)] [dry-run] Would build: ${spec}"
        return 0
    fi

    case "$BACKEND" in
        podman) build_package_podman "$pkg_dir" "$spec_override" ;;
        mock)   build_package_mock   "$pkg_dir" "$spec_override" ;;
        *)
            err "Unknown backend '${BACKEND}' — use 'podman' or 'mock'"
            return 1
            ;;
    esac
}

# Run all packages in a tier with up to $JOBS parallel workers.
build_tier() {
    local tier_name="$1"
    local -n _tier_pkg_total="$2"
    local -n _tier_failed="$3"

    local logdir
    logdir="$(mktemp -d)"
    trap "rm -rf '${logdir}'" RETURN

    local pids=()
    local pkg_paths=()
    local active=0

    wait_one() {
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

        while [[ $active -ge $JOBS ]]; do
            wait_one
        done

        local logfile="${logdir}/$(basename "$pkg_path").log"
        build_package "$pkg_path" "$spec_override" > "$logfile" 2>&1 &
        pids+=($!)
        pkg_paths+=("$pkg_path")
        active=$(( active + 1 ))
        log "  Queued ${pkg_path} (pid $!)"

    done < <(python3 "${SCRIPT_DIR}/parse-build-order.py" "$MANIFEST" --tier "$tier_name")

    while [[ $active -gt 0 ]]; do
        wait_one
    done
}

# --- Main ---
main() {
    log "Build chain starting"
    log "  Manifest:   ${MANIFEST}"
    log "  Backend:    ${BACKEND}"
    [[ "$BACKEND" == "podman" ]] && log "  Image:      ${BUILD_IMAGE}"
    [[ "$BACKEND" == "mock"   ]] && log "  Mock cfg:   ${MOCK_CONFIG}"
    log "  Local repo: ${LOCAL_REPO}"
    log "  Jobs:       ${JOBS}"
    [[ -n "$FILTER_TIER" ]]    && log "  Tier filter: ${FILTER_TIER}"
    [[ -n "$FILTER_PACKAGE" ]] && log "  Pkg filter:  ${FILTER_PACKAGE}"

    if ! $DRY_RUN; then
        case "$BACKEND" in
            podman) command -v podman &>/dev/null || { err "podman not found"; exit 1; } ;;
            mock)   command -v mock   &>/dev/null || { err "mock not found";   exit 1; } ;;
        esac
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
        log "===== Tier: ${tier_name} (backend=${BACKEND}, jobs=${JOBS}) ====="

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
