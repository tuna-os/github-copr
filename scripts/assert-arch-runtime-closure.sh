#!/usr/bin/env bash
# Assert an installed Arch package's runtime dependency closure resolves.
#
# Usage: assert-arch-runtime-closure.sh <package> [smoke-command...]
#
# Runs inside a clean Arch container that has just installed <package> from an
# ephemeral repository, with nothing preinstalled beyond pacman's own
# resolution of the package's declared `depends`.
#
# Why this exists (#118). The Arch gate already stopped using --nodeps and a
# shared package superset, and validate-built-arch-package.py proves the built
# package carries every dependency the recipe declares. Neither catches the
# failure that actually reaches users: a recipe that *under*-declares. Remove a
# `depends` entry and the recipe and the package agree with each other, both
# missing it, and the gate stays green — pacman installs the package fine,
# `pacman -Q` prints its name, and nothing ever loads the binary.
#
# makepkg, unlike rpmbuild, does not derive shared-library dependencies
# automatically. Every Arch `depends` entry is hand-written, so under-declaring
# is the normal failure, not an exotic one.
#
# Walking the installed ELF objects and requiring every DT_NEEDED to resolve is
# what turns that from invisible into red. It covers plugins and libraries too,
# which a `--help` smoke never reaches.
set -euo pipefail

package="${1:?usage: assert-arch-runtime-closure.sh <package> [smoke-command...]}"
shift

pacman -Q "$package"

mapfile -t installed < <(pacman -Ql "$package" | awk '{print $2}')

checked=0
status=0
for path in "${installed[@]}"; do
    [ -f "$path" ] || continue
    # Only ELF objects have a link-time closure to resolve.
    case "$(head -c 4 "$path" 2>/dev/null || true)" in
    $'\x7f'ELF) ;;
    *) continue ;;
    esac

    checked=$((checked + 1))
    missing=$(ldd "$path" 2>/dev/null | grep -F 'not found' || true)
    if [ -n "$missing" ]; then
        echo "assert-arch-runtime-closure: unresolved libraries in $path" >&2
        echo "$missing" >&2
        echo "  -> ${package}'s recipe under-declares its runtime depends." >&2
        status=1
    fi
done

echo "assert-arch-runtime-closure: checked $checked ELF object(s) in $package"

if [ "$checked" -eq 0 ]; then
    # Data-only packages (udev rules, desktop files, QML) legitimately contain
    # no ELF. Say so out loud rather than reporting a silent pass, so the log
    # never reads as "closure verified" when nothing was verifiable.
    echo "assert-arch-runtime-closure: no ELF objects — closure not applicable to $package"
fi

if [ "$#" -gt 0 ]; then
    echo "assert-arch-runtime-closure: smoke: $*"
    "$@"
fi

exit "$status"
