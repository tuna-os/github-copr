#!/usr/bin/env bash
# Assert that the xfconf split package really splits.
#
# Usage: assert-xfconf-split.sh <el10|ubuntu|debian> <directory-of-artifacts>
#
# #119 asks the staged gate to cover "at least one split package (xfconf)".
# Building xfconf and installing its runtime package does not do that: a
# renderer that silently dropped the subpackage stanza and shipped one fat
# package would pass it. This asserts the property that makes it a split:
#
#   1. both halves exist as separate installable artifacts,
#   2. the development half depends on the runtime half,
#   3. the headers are in the development half and NOT in the runtime half.
#
# (3) is the one that catches a collapsed split, and it is the one a
# file-existence check will never notice.
set -euo pipefail

target="${1:?usage: assert-xfconf-split.sh <target> <artifact-directory>}"
artifacts="${2:?usage: assert-xfconf-split.sh <target> <artifact-directory>}"

fail() {
    echo "assert-xfconf-split: $*" >&2
    exit 1
}

# Match a pattern against captured text WITHOUT a pipeline.
#
# `producer | grep -q pattern` is unsafe under `set -o pipefail`: grep -q exits
# the moment it matches, the producer gets SIGPIPE, and pipefail reports the
# whole pipeline as failed *because* the match succeeded. That is not
# hypothetical — it failed the ubuntu and debian split jobs on run 30592649133
# with "libxfconf-0-dev does not contain the xfconf headers" while the package
# contained them all along:
#
#   $ set -euo pipefail; dpkg-deb -c libxfconf-0-dev.deb | grep -q 'xfconf\.h$'
#   dpkg-deb: error: tar subprocess was killed by signal (Broken pipe)
#
# Capture first, match second. No pipe, no signal, no false verdict.
# A here-string, not a pipe: bash supplies the input itself, so there is no
# producer process left to receive SIGPIPE when grep -q exits early.
contains() {
    grep -qE "$2" <<<"$1"
}

case "$target" in
el10)
    runtime_package=xfconf
    devel_package=xfconf-devel

    dnf -y install epel-release createrepo_c >/dev/null
    cp -a "$artifacts" /tmp/tideforge-rpms
    createrepo_c /tmp/tideforge-rpms >/dev/null

    # 1. Both halves were produced as distinct RPMs.
    runtime_rpm=$(find /tmp/tideforge-rpms -name "${runtime_package}-[0-9]*.rpm" -type f | head -1)
    devel_rpm=$(find /tmp/tideforge-rpms -name "${devel_package}-[0-9]*.rpm" -type f | head -1)
    [ -n "$runtime_rpm" ] || fail "no ${runtime_package} RPM was produced — the split collapsed"
    [ -n "$devel_rpm" ] || fail "no ${devel_package} RPM was produced — the split collapsed"
    echo "split halves: $(basename "$runtime_rpm") / $(basename "$devel_rpm")"

    # 3. Headers belong to the development half only.
    devel_listing=$(rpm -qlp "$devel_rpm")
    runtime_listing=$(rpm -qlp "$runtime_rpm")
    if ! contains "$devel_listing" 'xfconf/xfconf\.h$'; then
        echo "$devel_listing" >&2
        fail "${devel_package} does not contain the xfconf headers"
    fi
    if contains "$runtime_listing" '/usr/include/'; then
        echo "$runtime_listing" >&2
        fail "${runtime_package} ships files under /usr/include — the split is not a split"
    fi

    # 2. Installing the development half pulls in the runtime half.
    dnf -y install --nogpgcheck --repofrompath tideforge,file:///tmp/tideforge-rpms \
        --setopt=tideforge.priority=1 --enablerepo=tideforge "$devel_package" >/dev/null
    rpm -q "$devel_package" "$runtime_package" \
        || fail "installing ${devel_package} did not pull in ${runtime_package}"
    test -f /usr/lib64/pkgconfig/libxfconf-0.pc || fail "pkg-config metadata missing from ${devel_package}"
    xfconf-query --version >/dev/null || fail "xfconf-query from ${runtime_package} is not runnable"
    ;;

ubuntu | debian)
    runtime_package=libxfconf-0-4
    devel_package=libxfconf-0-dev

    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y --no-install-recommends dpkg-dev >/dev/null

    mkdir -p /var/lib/tideforge
    cp "$artifacts"/*.deb /var/lib/tideforge/
    cd /var/lib/tideforge
    dpkg-scanpackages . /dev/null 2>/dev/null | gzip -9c > Packages.gz
    printf 'deb [trusted=yes] file:/var/lib/tideforge ./\n' > /etc/apt/sources.list.d/tideforge.list
    apt-get update -qq

    # 1. Both halves were produced as distinct .debs.
    runtime_deb=$(find /var/lib/tideforge -name "${runtime_package}_*.deb" -type f | head -1)
    devel_deb=$(find /var/lib/tideforge -name "${devel_package}_*.deb" -type f | head -1)
    [ -n "$runtime_deb" ] || fail "no ${runtime_package} .deb was produced — the split collapsed"
    [ -n "$devel_deb" ] || fail "no ${devel_package} .deb was produced — the split collapsed"
    echo "split halves: $(basename "$runtime_deb") / $(basename "$devel_deb")"

    # 3. Headers belong to the development half only.
    devel_listing=$(dpkg-deb -c "$devel_deb")
    runtime_listing=$(dpkg-deb -c "$runtime_deb")
    if ! contains "$devel_listing" 'xfconf/xfconf\.h$'; then
        echo "$devel_listing" >&2
        fail "${devel_package} does not contain the xfconf headers"
    fi
    if contains "$runtime_listing" ' \./usr/include/'; then
        echo "$runtime_listing" >&2
        fail "${runtime_package} ships files under /usr/include — the split is not a split"
    fi

    # 2. Installing the development half pulls in the runtime half.
    apt-get install -y "$devel_package" >/dev/null
    dpkg-query -W "$devel_package" "$runtime_package" \
        || fail "installing ${devel_package} did not pull in ${runtime_package}"
    xfconf-query --version >/dev/null || fail "xfconf-query from ${runtime_package} is not runnable"
    ;;

*)
    fail "unsupported target: $target"
    ;;
esac

echo "assert-xfconf-split: ${target} split-package contract holds"
