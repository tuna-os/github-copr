#!/usr/bin/env bats
# BATS tests for contrib/install.sh — TunaOS RPM repository installer

REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
INSTALL_SCRIPT="${REPO_ROOT}/contrib/install.sh"

@test "install.sh: exists" {
  run test -f "${INSTALL_SCRIPT}"
  [ "$status" -eq 0 ]
}

@test "install.sh: has bash shebang" {
  run head -1 "${INSTALL_SCRIPT}"
  [[ "$output" =~ ^#!/.*bash ]]
}

@test "install.sh: has set -euo pipefail" {
  run grep 'set -euo pipefail' "${INSTALL_SCRIPT}"
  [ "$status" -eq 0 ]
}

@test "install.sh: defines install_gpg_key function" {
  run grep 'install_gpg_key()' "${INSTALL_SCRIPT}"
  [ "$status" -eq 0 ]
}

@test "install.sh: references repo URL" {
  run grep 'REPO_URL=' "${INSTALL_SCRIPT}"
  [ "$status" -eq 0 ]
}

@test "install.sh: passes shellcheck" {
  if command -v shellcheck &>/dev/null; then
    run shellcheck "${INSTALL_SCRIPT}"
    [ "$status" -eq 0 ]
  else
    skip "shellcheck not installed"
  fi
}
