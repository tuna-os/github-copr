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

donor_suites=$(python3 -c "import yaml,sys;print(' '.join(yaml.safe_load(open(sys.argv[1]))['donor_suites']))" "$order")
target_suite=$(python3 -c "import yaml,sys;print(yaml.safe_load(open(sys.argv[1]))['target_suite'])" "$order")
count=$(wc -l < "$out/worklist")
echo "==> $target_suite <- $donor_suites: $count source packages to rebuild"

: "${SOURCE_DATE_EPOCH:=$(date -u +%s)}"
export SOURCE_DATE_EPOCH

"$backend" run --rm \
  --env SOURCE_DATE_EPOCH --env DONOR_SUITES="$donor_suites" \
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

    # Lift the container image dpkg exclusions BEFORE installing anything.
    #
    # Ubuntu container images ship /etc/dpkg/dpkg.cfg.d/excludes, which drops
    # translation catalogues and manpages to keep the image small. That is
    # correct for a runtime image and wrong for a buildroot: an sbuild chroot,
    # which is what the Ubuntu builders use and what this is imitating, is a
    # full install.
    #
    # Measured consequence, run 32665378407, once the chain was made to surface
    # the meson testlog:
    #
    #   # Ignoring `C.UTF-8` as a locale, since it lacks translations
    #   # Ignoring `en_US.UTF-8` as a locale, since it lacks translations
    #   not ok /languages/using-null-locale - GnomeDesktop-FATAL-WARNING:
    #     Could not read list of available locales from libc, guessing possible
    #     locales from available translations, but list may be incomplete!
    #   Bail out!
    #
    # The locales existed -- locale-gen had run. Every one was discarded for
    # having no translation files, the list came out empty, and glib turns that
    # warning into a fatal. Two earlier guesses at this failure were wrong
    # because the log showed only a summary line; this is what the log said
    # once it showed anything.
    #
    # It must come first: dpkg applies the exclusions at unpack time, so a
    # package installed before this runs keeps its files stripped.
    apt-get update -qq
    apt-get install -y --no-install-recommends \
      build-essential devscripts dpkg-dev ca-certificates locales
    # Translations for a real language, not just the C locale. gnome-desktop
    # enumerates locales and keeps only those that have them.
    #
    # --reinstall matters: dpkg applies path-exclude at UNPACK time, so a
    # package already on the image kept its files stripped, and a plain
    # install of something already present is a no-op that changes nothing.
    apt-get install -y --no-install-recommends language-pack-en || true
    apt-get install -y --reinstall --no-install-recommends \
      language-pack-en-base || true

    # A UTF-8 locale. Correct on its own terms -- a buildroot should have one,
    # and a minimal Ubuntu image ships almost no locale data -- but READ THE
    # NEXT PARAGRAPH before treating it as the fix for anything.
    #
    # It was added to explain this, in run 32653189343:
    #
    #   4/6 gnome-desktop:languages  FAIL  (exit status 134 or signal 6 SIGABRT)
    #
    # on the theory that `is_utf8: FALSE`, visible in the same suite, meant the
    # process had no UTF-8 locale. Run 32659338235 DISPROVED that as a
    # sufficient cause: locale-gen ran, and both the SIGABRT and `is_utf8:
    # FALSE` are unchanged. So the cause is still unknown, and the honest
    # record is that this did not fix gnome-desktop. What it may have fixed is
    # nothing -- gnome-shell passed in the second run having failed in the
    # first, but its failure was a compositor integration test complaining
    # about a session bus, which is not obviously locale-related and is exactly
    # the shape that flakes.
    #
    # gnome-desktop failing takes gnome-control-center with it, because
    # libgnome-desktop-4-dev never reaches the local repo, so this one package
    # costs two of eighteen.
    #
    # The Ubuntu builders do not hit this: an sbuild chroot is a full
    # install, not a container image with the locale data stripped out. Same
    # class as the ca-certificates ordering in run-package-factory-cell.sh --
    # a buildroot that is not the chroot upstream assumed.
    #
    # NO APOSTROPHES BELOW THIS POINT, and none above it either: this whole
    # body is a single-quoted `bash -lc` string, so one apostrophe ends it
    # early and bash then reports `unexpected EOF` at the last line of the
    # script rather than at the comment that broke it. Writing this very
    # comment cost that lesson twice.
    locale-gen C.UTF-8 en_US.UTF-8

    # Assert it against a GENERATED locale, not against C.UTF-8.
    #
    # The first version of this check asked `LC_ALL=C.UTF-8 locale charmap`,
    # which cannot fail: C.UTF-8 is built into glibc and resolves with zero
    # generated locales. It would have passed on the unmodified image it was
    # written to catch. en_US.UTF-8 exists only if locale-gen actually ran.
    charmap=$(LC_ALL=en_US.UTF-8 locale charmap 2>/dev/null || true)
    if [ "$charmap" != "UTF-8" ]; then
      echo "ERROR: locale-gen did not produce a usable UTF-8 locale." >&2
      echo "       LC_ALL=en_US.UTF-8 locale charmap reported: ${charmap:-nothing}" >&2
      echo "       Failing here rather than later inside a package test suite." >&2
      exit 1
    fi
    # Ubuntu ships package translations in /usr/share/locale-langpack, not in
    # /usr/share/locale. gettext finds them there via an Ubuntu patch; code
    # that looks in its own GNOMELOCALEDIR does not.
    #
    # Read out of gnome-desktop 51~alpha, libgnome-desktop/gnome-languages.c,
    # rather than guessed. collect_locales() warns only when BOTH collectors
    # fail:
    #
    #   collect_locales_from_localebin()  runs `locale -a` and keeps a locale
    #     only if add_locale() accepts it -- and add_locale rejects any locale
    #     with no .mo under GNOMELOCALEDIR/<code>/LC_MESSAGES, trying in turn
    #     the full name, the id, and the bare language code.
    #   collect_locales_from_directory()  scandirs LIBLOCALEDIR for
    #     DIRECTORIES -- and locale-gen writes a single locale-archive FILE,
    #     so it matches nothing.
    #
    # Both false, so it emits the fatal warning and the test aborts. The
    # locales were never the problem; where the catalogues live is.
    #
    # Presenting the langpack tree at the path the default localedir names is
    # what an sbuild chroot effectively has and this container did not.
    for langdir in /usr/share/locale-langpack/*/; do
      [ -d "$langdir" ] || continue
      lang=$(basename "$langdir")
      mkdir -p "/usr/share/locale/$lang/LC_MESSAGES"
      cp -n "$langdir"/LC_MESSAGES/*.mo "/usr/share/locale/$lang/LC_MESSAGES/" \
        2>/dev/null || true
    done

    # Report the predicate gnome-desktop actually evaluates, every run, pass
    # or fail. Four guesses at this failure were wrong while the log showed
    # only a summary; a number here costs one line and settles it.
    usable=0
    for loc in $(locale -a 2>/dev/null); do
      lang=${loc%%_*}; lang=${lang%%.*}
      if find "/usr/share/locale/$lang/LC_MESSAGES" -name "*.mo" -print -quit \
           2>/dev/null | grep -q . ; then
        usable=$((usable + 1))
      fi
    done
    echo "==> locales that gnome-desktop would accept: $usable"

    # And that translations survived. A locale with no message catalogue is
    # exactly what gnome-desktop discards, so checking only the charmap would
    # pass on the buildroot that produced the Bail out above.
    # -print -quit, NOT a pipe into head. See the note above the loop below:
    # under `set -o pipefail` a pipeline whose head closes early reports the
    # SIGPIPE, and this assertion spent a run claiming the buildroot had no
    # catalogues while standing next to them.
    catalogue=$(find /usr/share/locale /usr/share/locale-langpack \
                     -name "*.mo" -print -quit 2>/dev/null || true)
    if [ -z "$catalogue" ]; then
      echo "ERROR: the buildroot has no translation catalogues." >&2
      echo "       A package that enumerates locales will discard every one." >&2
      # Print the evidence rather than leave the next person to guess. Three
      # guesses at the gnome-desktop:languages failure were wrong before the
      # chain was made to show what the test actually said; the same rule
      # applies to the buildroot itself.
      echo "---- dpkg configuration" >&2
      cat /etc/dpkg/dpkg.cfg /etc/dpkg/dpkg.cfg.d/* 2>/dev/null >&2 || true
      echo "---- locale trees" >&2
      ls -d /usr/share/locale* /usr/lib/locale* 2>/dev/null >&2 || true
      find /usr/share/locale /usr/share/locale-langpack -maxdepth 2 2>/dev/null \
        | head -20 >&2 || true
      echo "---- what the language pack shipped" >&2
      dpkg -L language-pack-en-base 2>/dev/null | head -20 >&2 || true
      exit 1
    fi

    # SOURCES ONLY from the donor. See the header: a `deb` line here would
    # silently build the whole chain against the donor suite and produce
    # packages that install nowhere on the target.
    . /etc/os-release
    if [ "${ID:-}" = "ubuntu" ]; then
      donor_url="http://archive.ubuntu.com/ubuntu"
    else
      donor_url="http://deb.debian.org/debian"
    fi
    # One deb-src line per donor suite. Ubuntu needs -proposed alongside the
    # release pocket because an in-flight transition can leave a source
    # unbuildable from the release pocket alone: wayland-protocols 1.49-1
    # needs libwayland-dev >= 1.25.0 and wayland is 1.24.0-2 in both stonking
    # and resolute, with 1.26.0-1 waiting in stonking-proposed.
    #
    # Debian has no `universe`; asking for it there is a hard error.
    if [ "${ID:-}" = "ubuntu" ]; then components="main universe"; else components="main"; fi
    : > /etc/apt/sources.list.d/donor-src.list
    for donor_suite in $DONOR_SUITES; do
      printf "deb-src %s %s %s\n" "$donor_url" "$donor_suite" "$components" \
        >> /etc/apt/sources.list.d/donor-src.list
    done
    echo "==> donor sources:"; cat /etc/apt/sources.list.d/donor-src.list

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
      tree=$(find . -maxdepth 1 -mindepth 1 -type d -print -quit)
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
        # A failing TEST SUITE prints a summary line here and buffers its own
        # output somewhere else. meson writes it to meson-logs/testlog*.txt and
        # the build log carries only:
        #
        #   4/6 gnome-desktop:languages  FAIL  (exit status 134 or signal 6 SIGABRT)
        #
        # which names the test and says nothing about why. Two full chain runs
        # were spent on that -- 1h47m each -- guessing at a cause the log could
        # not confirm. The evidence exists inside the build tree, which is not
        # uploaded, so copy it out and print it. autotools writes the same
        # thing to test-suite.log.
        # THE PIPEFAIL / SIGPIPE TRAP, and this script is run with
        # `set -euo pipefail`. `find | head -N` makes head close the pipe once
        # it has N lines; find then dies of SIGPIPE (141), and pipefail
        # reports the whole pipeline as failed. Under `set -e` that aborts the
        # chain -- here it would abort exactly when a package has just failed
        # and the logs matter most. It stays hidden while fewer than N lines
        # are produced, which is why it survived the run that added it.
        # Collect first, then take the head of a FILE, which has no upstream
        # process to kill.
        find "/work/build/$source" \
             \( -name "testlog*.txt" -o -name "test-suite.log" \) \
             -type f > /tmp/testlogs.txt 2>/dev/null || true
        head -4 /tmp/testlogs.txt | while read -r testlog; do
          echo "    ---- $testlog" >&2
          tail -100 "$testlog" >&2 || true
          cp "$testlog" "/work/logs/$source.$(basename "$testlog")" 2>/dev/null || true
        done
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
