#!/usr/bin/env bash
# Clean-install a generated Arch package from an ephemeral repository.
#
# Usage: arch-clean-install.sh <package> <artifact-dir> [smoke-command...]
#
# This lives in a file rather than inline in the workflow because the inline
# version was silently not running. It built an ephemeral repository with a
# heredoc:
#
#     docker run ... bash -lc '
#       ...
#       cat > /tmp/tideforge-pacman.conf <<EOF
#       [options]
#       ...
#       EOF
#       pacman --config /tmp/tideforge-pacman.conf -S --noconfirm $package
#       pacman -Q $package
#     '
#
# Two independent defects, either of which is fatal:
#
#   1. The terminator was indented. An unquoted heredoc terminator has to be at
#      column 0 (only <<- strips leading TABS, and YAML block scalars indent
#      with spaces), so it never matched and the heredoc ran to end of script.
#   2. The delimiter was written <<'EOF' inside a single-quoted bash -lc string.
#      Those quotes close the outer string early — the same landmine already
#      documented in this workflow at 7af9ae1.
#
# The result: every command after the heredoc was swallowed as heredoc body.
# The package was never installed, `pacman -Q` never ran, and the job still
# went green, because the last command that actually executed (repo-add)
# succeeded and bash only *warns* about an unterminated heredoc. Run
# 30592649130 shows all nine matrix entries passing this way.
#
# So the "clean install" gate asserted nothing at all. Keeping the script in a
# file removes both quoting hazards: no nesting, no heredoc.
set -euo pipefail

package="${1:?usage: arch-clean-install.sh <package> <artifact-dir> [smoke...]}"
artifacts="${2:?usage: arch-clean-install.sh <package> <artifact-dir> [smoke...]}"
shift 2

pacman -Sy --noconfirm pacman-contrib

repo-add /tmp/tideforge.db.tar.gz "$artifacts"/*.pkg.tar.*
mkdir -p /var/lib/tideforge
cp "$artifacts"/*.pkg.tar.* /var/lib/tideforge/
# pacman resolves a repository named "tideforge" as tideforge.db. repo-add
# writes a compressed archive, so expose it under the name the file://
# repository client actually requests.
cp /tmp/tideforge.db.tar.gz /var/lib/tideforge/tideforge.db

# CI artifacts are deliberately unsigned. Production promotion has a separate
# signing gate; this isolated repository exists solely to prove pacman's
# dependency solver and payload installation.
#
# Keep the repository definition out of /etc: hosted container engines may
# user-map root and make image-owned files read-only, and recent Arch images
# no longer guarantee a copied /etc/pacman.conf survives that mapping. Write a
# small, complete configuration of our own instead.
{
    echo '[options]'
    echo 'Architecture = auto'
    echo 'SigLevel = Required DatabaseOptional'
    echo 'LocalFileSigLevel = Optional'
    echo
    echo '[core]'
    echo 'Include = /etc/pacman.d/mirrorlist'
    echo
    echo '[extra]'
    echo 'Include = /etc/pacman.d/mirrorlist'
    echo
    echo '[tideforge]'
    echo 'SigLevel = Optional TrustAll'
    echo 'Server = file:///var/lib/tideforge'
} > /tmp/tideforge-pacman.conf

pacman --config /tmp/tideforge-pacman.conf -Sy --noconfirm
pacman --config /tmp/tideforge-pacman.conf -S --noconfirm "$package"

# Prove the install really happened before anything downstream trusts it. The
# defect above is exactly the kind this line exists to catch.
pacman -Q "$package"

exec bash /scripts/assert-arch-runtime-closure.sh "$package" "$@"
