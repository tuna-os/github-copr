#!/usr/bin/env bash
# Publish one fanout cell's wave: sync-down, sign+index, sync-up.
# Copied from publish-build-chain-rpms.yml's publish job so the fanout
# publisher carries the SAME #519 protections -- most importantly, a failed
# sync-down must stop everything BEFORE the destructive sync-up.
#
# env: R2_BUCKET, R2_PATH, STAGED (dir holding this cell's wave), and
# DRY_RUN=true to skip the sync-up.
set -euo pipefail

: "${R2_BUCKET:?}" "${R2_PATH:?}" "${STAGED:?}"

repo="repo-${R2_PATH//\//-}"
mkdir -p "$repo"

# NOT `|| true`. The sync-up later makes the bucket MATCH the local tree, so
# any object that failed to come down here would be DELETED there. That is
# how repo/10/x86_64 lost ~160 served package names (#519), and the same
# shape as #124 / INCIDENT-repo-wipe-gnome. rclone exit 3 is "directory not
# found" -- the legitimate first-publish case; everything else stops us.
set +e
rclone sync "r2:${R2_BUCKET}/${R2_PATH}/" "$repo/" --exclude "repodata/**"
_rc=$?
set -e
if (( _rc == 3 )); then
    echo "::notice::no existing objects at ${R2_PATH} -- treating as first publish"
elif (( _rc != 0 )); then
    echo "::error::sync-down of ${R2_PATH} failed (rclone rc=${_rc}); refusing to continue -- the sync-up would DELETE every object that failed to come down"
    exit 1
fi
echo "synced down $(find "$repo" -name '*.rpm' | wc -l) RPM(s) from ${R2_PATH}"

bash scripts/publish-rpm-wave.sh --staged "$STAGED" --repo "$repo" --subdir build-chain

if [[ "${DRY_RUN:-false}" == "true" ]]; then
    echo "::notice::dry run -- signed and indexed ${R2_PATH} but synced nothing"
    exit 0
fi
rclone sync "$repo/" "r2:${R2_BUCKET}/${R2_PATH}/"
