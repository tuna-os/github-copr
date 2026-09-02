#!/usr/bin/env bash
# Sign, place and index one wave of RPMs into a local repo tree.
#
# This is the half of publishing that is pure file manipulation: no network,
# no secrets, no rclone. The caller syncs the destination down first, calls
# this, then syncs up. Splitting it out is not tidiness -- publish-tideforge
# -rpms.yml and publish-build-chain-rpms.yml both need it, and every safety
# rule below was learned once and must not have to be learned again in the
# second copy. The repo has already paid for that kind of drift twice (the
# nightly cron stagger documented but never applied; the readiness stamp read
# from two paths flatpak had stopped using).
#
# The rules, each anchored to the incident that produced it:
#
#   EMPTY WAVE      A wave with no RPMs means the build produced nothing and
#                   the publish is a no-op that would still rewrite repodata.
#                   Refuse, so a silently-empty build cannot look published.
#
#   NEVER SHRINK    #124 / INCIDENT-repo-wipe-gnome: `rclone sync` makes the
#                   destination match the source, so a locally-incomplete
#                   tree DELETES the served repo. The caller guards the
#                   sync-down; this guards the processing. Publishing adds
#                   packages -- if the tree came out smaller than it came in,
#                   something dropped files and syncing up would erase them
#                   from the bucket.
#
#   '+' IN NAMES    librepo percent-encodes '+' when building download URLs,
#                   but the repo.tunaos.org worker looks up R2 keys with the
#                   raw request path, so any filename containing '+' 404s at
#                   install time (run 32411090239: oversteer-udev-0.8.3+git…
#                   serves 200 at the literal-'+' URL and 404 at the %2b
#                   one). Renamed across the WHOLE tree, not just the staged
#                   files, so the sync also replaces any '+'-named object
#                   already in the bucket. Only the file name changes; the
#                   version inside the rpm metadata is untouched.
#
#   SRPMS EXCLUDED  Source RPMs are not installable content and bloat the
#                   index; the tideforge publisher has always excluded them.
#
#   SUPERSEDE       A publisher writes into REPO/SUBDIR, but the prefixes it
#                   writes to were served for months by earlier publishers
#                   that wrote flat at the root. Copying in leaves BOTH, and
#                   an rpm-md index with two entries for one NEVRA is
#                   ambiguous: dnf picks one, and the two are not the same
#                   bytes -- measured on xfce/10-stream-x86_64, which held
#                   107 same-NEVRA pairs with 107 differing checksums after
#                   the first build-chain wave. The staged copy is the
#                   freshly signed one, so it wins and the older file with
#                   the same name is removed from anywhere else in the tree.
#                   Subtracted from the NEVER SHRINK baseline, since this is
#                   the one shrink that is intended.
set -euo pipefail

STAGED="" REPO="" SUBDIR=""
while [ $# -gt 0 ]; do
	case "$1" in
	--staged) STAGED="$2"; shift 2 ;;
	--repo) REPO="$2"; shift 2 ;;
	--subdir) SUBDIR="$2"; shift 2 ;;
	*) echo "unknown argument: $1" >&2; exit 2 ;;
	esac
done
[ -n "$STAGED" ] && [ -n "$REPO" ] && [ -n "$SUBDIR" ] || {
	echo "usage: $0 --staged DIR --repo DIR --subdir NAME" >&2
	exit 2
}

count_rpms() { find "$1" -name '*.rpm' ! -name '*.src.rpm' 2>/dev/null | wc -l; }

staged_count=$(count_rpms "$STAGED")
if [ "$staged_count" -eq 0 ]; then
	echo "ERROR: no RPMs staged in ${STAGED}; refusing to publish an empty wave" >&2
	exit 1
fi

# NEVER BREAK RDEPS: before anything is signed or moved, simulate the
# publish against the synced-down tree's own repodata — the served state —
# and refuse a wave that leaves a surviving package unresolvable (the
# glib2-Obsoletes hijack and the libnotify version trap are the incidents;
# scripts/check-reverse-deps.py carries the receipts). Entirely local:
# the staged dir gets a throwaway index, the served state is already on
# disk. A first-ever publish has no served repodata and nothing to break.
if [ -f "${REPO}/repodata/repomd.xml" ]; then
	createrepo_c --quiet "$STAGED" || createrepo_c "$STAGED"
	python3 "$(dirname "$0")/check-reverse-deps.py" \
		--wave-repo "$STAGED" --served-repo "$REPO"
	rm -rf "${STAGED}/repodata"
else
	echo "==> no served repodata in ${REPO}; first publish, reverse-dep gate skipped"
fi

mkdir -p "$REPO"
baseline=$(count_rpms "$REPO")
echo "==> staged ${staged_count} RPM(s); repo already holds ${baseline}"

find "$STAGED" -name '*.rpm' ! -name '*.src.rpm' -exec rpmsign --addsign {} \;

mkdir -p "${REPO}/${SUBDIR}"
find "$STAGED" -name '*.rpm' ! -name '*.src.rpm' -exec cp -t "${REPO}/${SUBDIR}" {} +

# '^' joins '+': same worker, same failure. Fedora's snapshot-version
# convention puts '^' in filenames (quickshell-0.2.1^git…, signon-8.60^…);
# librepo and dnf percent-encode it to %5E, the worker looks up raw R2
# keys, and the file 404s. Found by simulate-buildroot-resolution.py's
# fetchability pass (~30 served files, every one HEAD-verified 404 at the
# encoded URL) -- and unlike '+', these are runtime packages the desktop
# lanes install with --skip-unavailable, so the failure is a silently
# thinner image rather than a red build.
find "$REPO" \( -name '*+*.rpm' -o -name '*^*.rpm' \) -print0 | while IFS= read -r -d '' f; do
	mv "$f" "$(dirname "$f")/$(basename "$f" | tr '+^' '..')"
done

# Runs AFTER the rename so a legacy 'foo+1.rpm' and a staged 'foo+1.rpm'
# compare as the same name rather than surviving as a stale duplicate.
superseded=0
while IFS= read -r staged_file; do
	name=$(basename "$staged_file")
	while IFS= read -r older; do
		echo "==> superseding older copy: $older"
		rm -f "$older"
		superseded=$((superseded + 1))
		# Excluded by PATH, not by comparing against the staged file's own
		# path: `find repo/ ...` and `find repo//build-chain ...` print the
		# same file under different strings, so a string compare would let a
		# trailing slash in --repo make the wave delete what it just staged.
	done < <(find "$REPO" -name "$name" ! -name '*.src.rpm' ! -path "*/${SUBDIR}/*")
done < <(find "${REPO}/${SUBDIR}" -name '*.rpm' ! -name '*.src.rpm')
[ "$superseded" -eq 0 ] || echo "==> superseded ${superseded} older copy/copies"

final=$(count_rpms "$REPO")
if [ "$final" -lt $((baseline - superseded)) ]; then
	echo "ERROR: repo shrank from ${baseline} to ${final} RPMs" \
	     "(${superseded} superseded); refusing to sync" >&2
	echo "       a sync from a smaller tree DELETES the difference from the bucket" >&2
	exit 1
fi
echo "==> repo now holds ${final} RPM(s)"

createrepo_c --update "$REPO" 2>/dev/null || createrepo_c "$REPO"

# Detached signature over repomd.xml.
#
# rpmsign above signs the PACKAGES, which is what makes gpgcheck=1 meaningful:
# an attacker serving repo.tunaos.org cannot get an unsigned RPM installed.
# It does not stop the attacks that need no forged package signature —
# replaying an older repomd.xml to reinstate a withdrawn version (downgrade),
# or serving current-looking metadata forever so clients never see updates
# (freeze). Signed metadata is the control for those, and it was the missing
# half: contrib/install.sh and contrib/install-gnome49.sh both carry
# repo_gpgcheck=0 with a comment explaining that no repomd.xml.asc is
# published. This publishes it. See #509.
#
# The apt side of this same pipeline already does the equivalent —
# publish-tideforge-debs.yml signs both InRelease and Release.gpg with this
# key — so this brings the rpm side level rather than introducing a new
# requirement.
#
# The key is the one rpmsign is already using: both publish workflows write
# %_gpg_name into ~/.rpmmacros from the imported key, and the agent is already
# unlocked by the time we get here. Falling back to gpg's default key keeps a
# local run working for someone who signs with a single key and no rpmmacros.
repomd="${REPO}/repodata/repomd.xml"
if [ ! -f "$repomd" ]; then
	echo "ERROR: ${repomd} missing after createrepo_c; refusing to publish" \
	     "metadata that cannot be signed" >&2
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
