#!/usr/bin/env bash
# Detach-sign a repo tree's repodata/repomd.xml.
#
# rpmsign signs the PACKAGES, which is what makes gpgcheck=1 meaningful: an
# attacker serving repo.tunaos.org cannot get an unsigned RPM installed. It
# does not stop the attacks that need no forged package signature -- replaying
# an older repomd.xml to reinstate a withdrawn version (downgrade), or serving
# current-looking metadata forever so clients never see updates (freeze).
# Signed metadata is the control for those. See #509.
#
# This lives in its own script rather than inside publish-rpm-wave.sh because
# the wave publisher is not the only thing that writes repodata/ into a served
# prefix. `rclone sync` makes the destination MATCH the source, so any
# publisher that re-indexes a tree and syncs it up without signing does not
# merely skip a step -- it DELETES the repomd.xml.asc a previous publisher
# wrote, and repo_gpgcheck=1 can never be turned on for that prefix. Every
# publisher that runs createrepo_c before a sync-up has to call this.
#
# The key is the one rpmsign is already using: the publish workflows write
# %_gpg_name into ~/.rpmmacros from the imported key, and the agent is already
# unlocked by the time a publisher gets here. Falling back to gpg's default key
# keeps a local run working for someone who signs with a single key and no
# rpmmacros.
#
# Usage: sign-repomd.sh <repo-dir>
set -euo pipefail

REPO="${1:?usage: sign-repomd.sh <repo-dir>}"

repomd="${REPO}/repodata/repomd.xml"
if [ ! -f "$repomd" ]; then
	echo "ERROR: ${repomd} missing; refusing to publish metadata that cannot be signed" >&2
	exit 1
fi

gpg_name="$(awk '$1 == "%_gpg_name" { print $2 }' "${HOME}/.rpmmacros" 2>/dev/null || true)"
sign_args=(--batch --yes --armor --detach-sign)
[ -n "$gpg_name" ] && sign_args+=(--local-user "$gpg_name")

# Deliberately fatal. Syncing a repodata/ whose signature is stale or absent is
# worse than not publishing: clients that have been told to expect
# repo_gpgcheck=1 would start failing, and clients that have not would silently
# lose the protection this step exists to add.
gpg "${sign_args[@]}" --output "${repomd}.asc" "$repomd"
echo "==> signed $(basename "$repomd") -> $(basename "$repomd").asc"
