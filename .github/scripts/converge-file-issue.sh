#!/usr/bin/env bash
# One issue per request, refreshed -- never one issue per wave.
#
# A loop that opens an issue every run buries the one that matters under
# duplicates of itself, and a backlog full of near-identical build reports is
# worse than none: nobody, human or agent, can tell which is current. So the
# title is derived from the request and the body is replaced each time, which
# makes the issue a live status rather than a log.
#
# The `hive` label is the handoff: this is the point where a residue stops
# being something rebuilding can fix and becomes packaging work.
#
# env: GH_TOKEN, REQUEST, GITHUB_REPOSITORY.
set -euo pipefail
: "${GH_TOKEN:?}" "${REQUEST:?}" "${GITHUB_REPOSITORY:?}"

title="converge: ${REQUEST}"
{
    cat converge-report.md
    echo
    echo "---"
    echo "_Refreshed by [Converge](https://github.com/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}) — one issue per request, replaced each run._"
} > /tmp/issue-body.md

existing="$(gh issue list --repo "$GITHUB_REPOSITORY" --state open \
    --search "\"${title}\" in:title" --json number,title \
    --jq "[.[] | select(.title == \"${title}\")] | .[0].number // empty")"

if [[ -n "$existing" ]]; then
    gh issue edit "$existing" --repo "$GITHUB_REPOSITORY" \
        --body-file /tmp/issue-body.md
    echo "refreshed issue #${existing}"
else
    gh issue create --repo "$GITHUB_REPOSITORY" --title "$title" \
        --body-file /tmp/issue-body.md \
        --label package-factory --label hive
fi
