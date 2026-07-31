#!/usr/bin/env bash
# Lint generated RPMs, failing only on a curated set of findings.
#
# Runs inside the el10 build container. Argument: a directory of built RPMs.
#
# Issue #119 asks for package lint on the formats package-factory.yaml marks
# supported. The point is not "rpmlint is clean" — no real package tree is —
# but that a *renderer* defect cannot ship. rpmlint emits hundreds of findings
# that reflect upstream's choices rather than Tideforge's, so a blanket
# hard-fail would be turned off within a week and assert nothing thereafter.
#
# So: print the whole report (it is the baseline, and it goes to the job log),
# and hard-fail on the findings that can only mean the generated spec is
# wrong. `unexpanded-macro` is the flagship case — it is precisely the
# "syntactically emitted but malformed native metadata" that #119 names.
set -euo pipefail

rpm_directory="${1:?usage: lint-generated-rpm.sh <directory-of-rpms>}"

# Findings that indicate a defect in what Tideforge generated, not in what
# upstream shipped. Keep this list short and justified; every entry should be
# something no correct rendering can produce.
#
# Deliberately NOT fatal: `files-duplicate`. It fires when two packaged paths
# have identical content, which is a property of the tree upstream ships rather
# than of anything Tideforge emits. wayland-protocols is the worked example: its
# `stable/tablet/README` and `unstable/tablet/README` are byte-identical in the
# pinned tarball, so a *faithful* rendering of that data package necessarily
# trips the check. Making it fatal would demand we mutate upstream content to
# satisfy a linter. It still prints in the baseline report below.
#
# `htaccess-file` was removed under the same rule, for a duller reason: it
# flags Apache .htaccess files in a package. Nothing this factory builds is
# web content, so it could never fire on a real defect here — it was list
# padding, and padding is how a curated list stops being curated.
fatal_checks=(
    unexpanded-macro
    specfile-error
    invalid-spec-name
    binary-or-shlib-defines-rpath
    no-changelogname-tag
    invalid-license
)

# This script runs inside whichever RPM build container the calling job used,
# so it cannot assume dnf. openSUSE Tumbleweed (issue #139) ships zypper and
# has no EPEL; rpmlint is in the base repositories there. Detect rather than
# branch on a target name, so a future rpm-family target needs no edit here.
if command -v zypper >/dev/null 2>&1; then
    zypper --non-interactive install rpmlint >/dev/null
else
    dnf -y install epel-release >/dev/null
    dnf -y install rpmlint >/dev/null
fi

mapfile -t rpms < <(find "$rpm_directory" -name '*.rpm' -type f | sort)
if [ "${#rpms[@]}" -eq 0 ]; then
    echo "lint-generated-rpm: no RPMs found under $rpm_directory" >&2
    exit 1
fi

report=$(mktemp)
# rpmlint exits non-zero whenever it reports anything at all, which is almost
# always. Capture the report and judge it ourselves rather than trusting the
# exit code; `|| true` here is deliberate and is not masking a crash, because
# an empty report is caught below.
rpmlint "${rpms[@]}" > "$report" 2>&1 || true

echo "===== rpmlint report (baseline; only curated checks are fatal) ====="
cat "$report"
echo "===================================================================="

if [ ! -s "$report" ]; then
    echo "lint-generated-rpm: rpmlint produced no output at all — treating as a" >&2
    echo "lint failure rather than a pass, because a silent linter is not a gate." >&2
    exit 1
fi

status=0
for check in "${fatal_checks[@]}"; do
    if grep -qE "(^|[[:space:]])(E|W): .*${check}" "$report"; then
        echo "lint-generated-rpm: FATAL finding '${check}' in generated RPM" >&2
        grep -E "(^|[[:space:]])(E|W): .*${check}" "$report" >&2
        status=1
    fi
done

exit "$status"
