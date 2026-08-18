#!/usr/bin/env bash
# Lint generated .debs, failing only on a curated set of findings.
#
# Runs inside the ubuntu/debian build container. Argument: a directory of
# built .deb files. See lint-generated-rpm.sh for why the fatal set is curated
# rather than "every lintian tag": the gate exists to catch defects in what
# Tideforge rendered, and a blanket hard-fail on upstream's packaging choices
# would be disabled rather than fixed.
set -euo pipefail

deb_directory="${1:?usage: lint-generated-deb.sh <directory-of-debs>}"

# Tags that can only mean the generated debian/ metadata is wrong.
#
# Same admission rule as lint-generated-rpm.sh, and the same lesson applies
# here before it costs a red build: `wrong-file-owner-uid-or-gid` was dropped
# because an upstream archive carrying non-root ownership produces it without
# anything being wrong with what Tideforge rendered.
fatal_tags=(
    malformed-deb-archive
    control-file-has-bad-permissions
    control-file-has-bad-owner
    no-package-name
    invalid-package-name
    package-has-no-description
    debian-control-has-unusual-field-spacing
    depends-on-itself
    bad-relation
    invalid-versioned-provides
)

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
# The linter is QA tooling layered on an already-successful build, and during
# sid library transitions its own dependency chain can become uninstallable:
# on 2026-08-18 lintian -> libdata-dpath-perl -> libclass-xsaccessor-perl
# demanded perl (< 5.42.3~) after sid had moved to 5.42.3-1, and every debian
# deb cell went red for the linter's dependencies with the built .deb already
# uploaded. That is not a defect in what Tideforge rendered, so skip the gate
# loudly instead of failing a build that produced its artifact.
if ! apt-get install -y --no-install-recommends lintian >/dev/null; then
    echo "::warning::lint-generated-deb: lintian is uninstallable in this container (upstream dependency transition) -- lint gate SKIPPED, package NOT linted" >&2
    exit 0
fi

mapfile -t debs < <(find "$deb_directory" -name '*.deb' -type f | sort)
if [ "${#debs[@]}" -eq 0 ]; then
    echo "lint-generated-deb: no .debs found under $deb_directory" >&2
    exit 1
fi

report=$(mktemp)
# lintian exits non-zero on any error-level tag. Judge the report ourselves so
# the curated set decides, not lintian's own severity model.
lintian --no-tag-display-limit "${debs[@]}" > "$report" 2>&1 || true

echo "===== lintian report (baseline; only curated tags are fatal) ====="
cat "$report"
echo "================================================================="

status=0
for tag in "${fatal_tags[@]}"; do
    if grep -qE "^(E|W): .*: ${tag}([[:space:]]|$)" "$report"; then
        echo "lint-generated-deb: FATAL tag '${tag}' in generated package" >&2
        grep -E "^(E|W): .*: ${tag}([[:space:]]|$)" "$report" >&2
        status=1
    fi
done

exit "$status"
