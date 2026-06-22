#!/usr/bin/env bats
# BATS tests for scripts/upload-sources.sh — R2 lookaside cache uploader

REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
UPLOAD_SOURCES="${REPO_ROOT}/scripts/upload-sources.sh"

@test "upload-sources.sh: exists" {
  run test -f "${UPLOAD_SOURCES}"
  [ "$status" -eq 0 ]
}

@test "upload-sources.sh: has bash shebang" {
  run head -1 "${UPLOAD_SOURCES}"
  [[ "$output" =~ ^#!/.*bash ]]
}

@test "upload-sources.sh: has set -euo pipefail" {
  run grep 'set -euo pipefail' "${UPLOAD_SOURCES}"
  [ "$status" -eq 0 ]
}

@test "upload-sources.sh: prints usage when called with no arguments" {
  run bash "${UPLOAD_SOURCES}"
  [ "$status" -ne 0 ]
  [[ "$output" =~ Usage ]]
}

@test "upload-sources.sh: prints usage when called with one argument" {
  run bash "${UPLOAD_SOURCES}" /tmp/test.spec
  [ "$status" -ne 0 ]
  [[ "$output" =~ Usage ]]
}

@test "upload-sources.sh: defines upload_source function" {
  run grep 'upload_source()' "${UPLOAD_SOURCES}"
  [ "$status" -eq 0 ]
}

@test "upload-sources.sh: references R2_BUCKET" {
  run grep 'R2_BUCKET' "${UPLOAD_SOURCES}"
  [ "$status" -eq 0 ]
}

@test "upload-sources.sh: passes shellcheck" {
  if command -v shellcheck &>/dev/null; then
    run shellcheck "${UPLOAD_SOURCES}"
    [ "$status" -eq 0 ]
  else
    skip "shellcheck not installed"
  fi
}
