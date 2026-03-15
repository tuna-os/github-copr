#!/usr/bin/env bash
#
# watch-pipeline.sh — Monitor and manage GNOME 49 GitHub Actions pipeline
#
# Usage:
#   scripts/watch-pipeline.sh               # Show latest run status
#   scripts/watch-pipeline.sh run           # Trigger a full bootstrap run and watch
#   scripts/watch-pipeline.sh watch [id]    # Watch an existing run (latest if no id)
#   scripts/watch-pipeline.sh package <path>  # Trigger a single-package build
#   scripts/watch-pipeline.sh status        # Show all recent runs (last 10)
#
set -euo pipefail

WORKFLOW_BOOTSTRAP="build-gnome49-distributed.yml"
WORKFLOW_PACKAGE="build-gnome49-package.yml"
REPO="tuna-os/github-copr"
BRANCH="gnome-49-pipeline"

cmd="${1:-status}"
shift || true

case "${cmd}" in
  run)
    echo "Triggering full GNOME 49 bootstrap build..."
    gh workflow run "${WORKFLOW_BOOTSTRAP}" \
      --repo "${REPO}" \
      --ref "${BRANCH}"
    sleep 3
    RUN_ID=$(gh run list --repo "${REPO}" \
      --workflow "${WORKFLOW_BOOTSTRAP}" \
      --limit 1 \
      --json databaseId \
      --jq '.[0].databaseId')
    echo "Run ID: ${RUN_ID}"
    echo "Watching... (Ctrl+C to stop watching without cancelling)"
    gh run watch "${RUN_ID}" --repo "${REPO}"
    ;;

  watch)
    RUN_ID="${1:-}"
    if [[ -z "${RUN_ID}" ]]; then
      RUN_ID=$(gh run list --repo "${REPO}" \
        --workflow "${WORKFLOW_BOOTSTRAP}" \
        --limit 1 \
        --json databaseId \
        --jq '.[0].databaseId')
    fi
    echo "Watching run ${RUN_ID}..."
    gh run watch "${RUN_ID}" --repo "${REPO}"
    ;;

  package)
    PKG_PATH="${1:?Usage: watch-pipeline.sh package <path>}"
    echo "Triggering incremental build for ${PKG_PATH}..."
    gh workflow run "${WORKFLOW_PACKAGE}" \
      --repo "${REPO}" \
      --ref "${BRANCH}" \
      --field "package_path=${PKG_PATH}"
    sleep 3
    RUN_ID=$(gh run list --repo "${REPO}" \
      --workflow "${WORKFLOW_PACKAGE}" \
      --limit 1 \
      --json databaseId \
      --jq '.[0].databaseId')
    echo "Run ID: ${RUN_ID}"
    gh run watch "${RUN_ID}" --repo "${REPO}"
    ;;

  status)
    echo "=== Recent GNOME 49 Pipeline Runs ==="
    echo ""
    echo "--- Bootstrap (Full Build) ---"
    gh run list --repo "${REPO}" \
      --workflow "${WORKFLOW_BOOTSTRAP}" \
      --limit 5 \
      --json databaseId,status,conclusion,createdAt,displayTitle \
      --template '{{range .}}{{.databaseId}} {{.status}} {{.conclusion}} {{.createdAt}} {{.displayTitle}}{{"\n"}}{{end}}'
    echo ""
    echo "--- Incremental (Package) Builds ---"
    gh run list --repo "${REPO}" \
      --workflow "${WORKFLOW_PACKAGE}" \
      --limit 5 \
      --json databaseId,status,conclusion,createdAt,displayTitle \
      --template '{{range .}}{{.databaseId}} {{.status}} {{.conclusion}} {{.createdAt}} {{.displayTitle}}{{"\n"}}{{end}}'
    ;;

  *)
    echo "Unknown command: ${cmd}"
    echo "Usage: watch-pipeline.sh [run|watch [id]|package <path>|status]"
    exit 1
    ;;
esac
