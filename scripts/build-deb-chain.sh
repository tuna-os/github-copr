#!/usr/bin/env bash
# Rebuild a tiered deb backport: donor-suite sources, target-suite buildroot.
#
# The deb twin of build-chain.sh. That script drives mock over native specs in
# tier order with a --local-repo accumulating each tier's output; this one does
# the same for deb, with two differences that matter.
#
# 1. THERE IS NO PACKAGING IN THIS REPOSITORY. A backport rebuilds a source
#    package that the donor suite already ships, so the unit of work is
#    (source name, exact donor version) rather than a path to a spec. That is
#    what makes a deb backport far cheaper than the EL10 GNOME one: nobody
#    authors a debian/ directory.
#
# 2. THE DONOR IS ADDED AS deb-src ONLY, NEVER deb. This is the property the
#    whole engine rests on. A binary `deb` line for the donor would let apt
#    satisfy build dependencies from the donor suite, so the packages would be
#    built against stonking rather than resolute -- they would compile, look
#    fine, and then fail to install on the target because their shared-library
#    dependencies resolve to versions the target does not have. The result is
#    not a backport at all. deb-src carries no binaries, so it cannot do this.
#
# The local repo needs no apt pinning: every package this chain builds is
# NEWER than the target archive's, and apt prefers the higher version at equal
# priority. Pinning it above 500 would additionally let it outrank the target
# archive for packages we did NOT build, which is exactly the failure mode the
# rpm path hit at priority=999 (the glib2 Obsoletes incident, publish run
# 32405815822).
#
# Usage:
#   scripts/build-deb-chain.sh --order build-order-gnome51-ubuntu.yml \
#     --image docker.io/library/ubuntu:26.04 --out .factory/gnome51-ubuntu
set -eEuo pipefail

order="" image="" out="" backend="${BACKEND:-docker}" only_tier=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --order) order=$2; shift 2 ;;
    --image) image=$2; shift 2 ;;
    --out) out=$2; shift 2 ;;
    --backend) backend=$2; shift 2 ;;
    --tier) only_tier=$2; shift 2 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
done
[[ -n $order && -n $image && -n $out ]] || {
  echo "usage: $0 --order ORDER.yml --image IMAGE --out DIR [--tier NAME]" >&2
  exit 2
}

mkdir -p "$out"/{artifacts,logs,repo}
# Absolute, because docker reads a RELATIVE --volume source as a NAMED VOLUME
# rather than a host path, and then blames the characters in the name rather
# than the relativeness:
#
#   docker: Error response from daemon: create .factory/backport-ubuntu:
#   ".factory/backport-ubuntu" includes invalid characters for a local volume
#   name, only "[a-zA-Z0-9][a-zA-Z0-9_.-]" are allowed.
#
# Resolved here rather than at the call site so every caller is safe, not just
# the workflow that happened to hit it (run 32641183871).
out=$(cd "$out" && pwd)

# The order is parsed on the HOST. The target image is a stock distro
# container: it has python3 but no pyyaml, and installing one to read our own
# manifest would be a build dependency of the factory leaking into the
# buildroot. A tab-separated work list is something plain shell can read.
python3 - "$order" "$only_tier" > "$out/worklist" <<'PY'
import sys, yaml
order = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
only = sys.argv[2] if len(sys.argv) > 2 else ""
for tier in order.get("tiers", []):
    if only and tier["name"] != only:
        continue
    for pkg in tier.get("packages") or []:
        print(f"{tier['name']}\t{pkg['source']}\t{pkg['version']}")
PY

donor_suite=$(python3 -c "import yaml,sys;print(yaml.safe_load(open(sys.argv[1]))['donor_suite'])" "$order")
target_suite=$(python3 -c "import yaml,sys;print(yaml.safe_load(open(sys.argv[1]))['target_suite'])" "$order")
count=$(wc -l < "$out/worklist")
echo "==> $target_suite <- $donor_suite: $count source packages to rebuild"

: "${SOURCE_DATE_EPOCH:=$(date -u +%s)}"
export SOURCE_DATE_EPOCH

"$backend" run --rm \
  --env SOURCE_DATE_EPOCH --env DONOR_SUITE="$donor_suite" \
  --env TZ=UTC --env LANG=C.UTF-8 --env LC_ALL=C.UTF-8 \
  --volume "$out:/work" "$image" bash -lc '
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive

    # Ubuntu keeps part of the GNOME stack in universe; Debian has no such
    # component and no ubuntu.sources, so this is a no-op there. The buildroot
    # must not depend on whichever components the base image happens to ship.
    if [ -f /etc/apt/sources.list.d/ubuntu.sources ]; then
      sed -i -E "s/^Components:.*/Components: main restricted universe multiverse/" \
        /etc/apt/sources.list.d/ubuntu.sources
    fi

    apt-get update -qq
    apt-get install -y --no-install-recommends \
      build-essential devscripts dpkg-dev ca-certificates

    # SOURCES ONLY from the donor. See the header: a `deb` line here would
    # silently build the whole chain against the donor suite and produce
    # packages that install nowhere on the target.
    . /etc/os-release
    if [ "${ID:-}" = "ubuntu" ]; then
      donor_url="http://archive.ubuntu.com/ubuntu"
    else
      donor_url="http://deb.debian.org/debian"
    fi
    printf "deb-src %s %s main universe\n" "$donor_url" "$DONOR_SUITE" \
      > /etc/apt/sources.list.d/donor-src.list
    # Debian has no `universe`; asking for it is a hard error there.
    if [ "${ID:-}" != "ubuntu" ]; then
      printf "deb-src %s %s main\n" "$donor_url" "$DONOR_SUITE" \
        > /etc/apt/sources.list.d/donor-src.list
    fi

    # The accumulating local repo. Empty on the first pass, which apt accepts
    # only if the Packages file exists.
    mkdir -p /work/repo
    : > /work/repo/Packages
    printf "deb [trusted=yes] file:///work/repo ./\n" \
      > /etc/apt/sources.list.d/chain-local.list

    apt-get update > /tmp/apt-update.log 2>&1 || { cat /tmp/apt-update.log >&2; exit 1; }
    if grep -q "Failed to fetch" /tmp/apt-update.log; then
      cat /tmp/apt-update.log >&2
      echo "ERROR: a declared apt source could not be fetched (see above)." >&2
      echo "       Failing here rather than later as a missing build dependency." >&2
      exit 1
    fi

    built=0 failed=""
    mkdir -p /work/build
    while IFS="$(printf "\t")" read -r tier source version; do
      [ -n "$source" ] || continue
      echo "==> [$tier] $source $version"
      rm -rf "/work/build/$source"
      mkdir -p "/work/build/$source"
      cd "/work/build/$source"
      if ! apt-get source "$source=$version" > "/work/logs/$source.source.log" 2>&1; then
        echo "    FAILED to fetch source" >&2
        tail -20 "/work/logs/$source.source.log" >&2 || true
        failed="$failed $source"
        continue
      fi
      tree=$(find . -maxdepth 1 -mindepth 1 -type d | head -1)
      cd "$tree"
      if ! apt-get build-dep -y --no-install-recommends "$PWD" \
            > "/work/logs/$source.builddep.log" 2>&1; then
        echo "    FAILED build-dep" >&2
        tail -30 "/work/logs/$source.builddep.log" >&2 || true
        failed="$failed $source"
        continue
      fi
      if ! dpkg-buildpackage -us -uc -b > "/work/logs/$source.build.log" 2>&1; then
        echo "    FAILED build" >&2
        tail -40 "/work/logs/$source.build.log" >&2 || true
        failed="$failed $source"
        continue
      fi
      cp ../*.deb /work/repo/ 2>/dev/null || true
      cp ../*.deb /work/artifacts/ 2>/dev/null || true
      # Re-index so the NEXT tier can resolve what this one produced. This is
      # the whole reason the chain is ordered.
      ( cd /work/repo && dpkg-scanpackages . /dev/null > Packages 2>/dev/null )
      apt-get update -qq
      built=$((built + 1))
      echo "    ok"
    done < /work/worklist

    echo "==> built $built package(s)"
    if [ -n "$failed" ]; then
      echo "ERROR: failed:$failed" >&2
      exit 1
    fi
  '
