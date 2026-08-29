#!/usr/bin/env bash

# Native rpmbuild backend for build-chain.sh.
#
# Contract supplied by the orchestrator:
#   globals: FORCE, DIST, LOCAL_REPO, REPO_ROOT, RPM_SOURCES_CACHE (optional)
#   functions: find_spec, log, err
build_package_native() {
    local pkg_dir="$1"
    local spec_override="$2"

    local spec pkg_name abs_pkg_dir
    spec="$(find_spec "$pkg_dir" "$spec_override")"
    pkg_name="$(basename "$spec" .spec)"
    abs_pkg_dir="${REPO_ROOT}/${pkg_dir}"

    if ! $FORCE; then
        local nvr
        nvr=$(rpm -q --specfile "$spec" \
            --define "dist ${DIST}" \
            --queryformat "%{NAME}-%{VERSION}-%{RELEASE}\n" 2>/dev/null | head -1)
        if [[ -n "$nvr" ]] && ls "${LOCAL_REPO}/${nvr}"*.rpm &>/dev/null 2>&1; then
            log "[${pkg_name}] Skipping: ${nvr} already in local repo"
            return 0
        fi
    fi

    log "[${pkg_name}] Building (native rpmbuild) from ${pkg_dir}"

    local builddir
    builddir="$(mktemp -d)"
    # shellcheck disable=SC2064
    trap "rm -rf '${builddir}'" RETURN

    mkdir -p "${builddir}"/{BUILD,BUILDROOT,RPMS,SOURCES,SRPMS,SPECS}

    local spec_basename
    spec_basename="$(basename "$spec")"
    cp "$spec" "${builddir}/SPECS/"

    find "$abs_pkg_dir" -maxdepth 1 -type f \
        ! -name "*.spec" \
        ! -name "sources" \
        ! -name "changelog" \
        ! -name "rpminspect.yaml" \
        ! -name "*.md" \
        -exec cp {} "${builddir}/SOURCES/" \;

    log "[${pkg_name}] Downloading sources..."
    local sources_cache="${RPM_SOURCES_CACHE:-}"
    if [[ -n "$sources_cache" ]]; then
        mkdir -p "$sources_cache"
        spectool -g -C "$sources_cache" "${builddir}/SPECS/${spec_basename}" || {
            err "spectool failed for ${pkg_name}"
            return 1
        }
        find "$sources_cache" -maxdepth 1 -type f \
            -exec ln -f {} "${builddir}/SOURCES/" \; 2>/dev/null \
            || cp "$sources_cache"/* "${builddir}/SOURCES/" 2>/dev/null || true
    else
        spectool -g -C "${builddir}/SOURCES/" "${builddir}/SPECS/${spec_basename}" || {
            err "spectool failed for ${pkg_name}"
            return 1
        }
    fi

    log "[${pkg_name}] Installing BuildRequires..."
    dnf builddep -y \
        --define "dist ${DIST}" \
        "${builddir}/SPECS/${spec_basename}" || {
        err "dnf builddep failed for ${pkg_name}"
        return 1
    }

    log "[${pkg_name}] Running rpmbuild..."
    rpmbuild -bb \
        --define "_topdir ${builddir}" \
        --define "dist ${DIST}" \
        "${builddir}/SPECS/${spec_basename}" || {
        err "rpmbuild failed for ${pkg_name}"
        return 1
    }

    local rpm_count=0
    while IFS= read -r -d '' rpm; do
        cp "$rpm" "${LOCAL_REPO}/"
        log "[${pkg_name}] -> $(basename "$rpm")"
        rpm_count=$(( rpm_count + 1 ))
    done < <(find "${builddir}/RPMS" -name "*.rpm" -print0)

    if [[ $rpm_count -eq 0 ]]; then
        err "No RPMs produced for ${pkg_name}"
        return 1
    fi

    log "[${pkg_name}] Built ${rpm_count} RPM(s)"
}
