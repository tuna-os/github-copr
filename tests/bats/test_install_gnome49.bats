#!/usr/bin/env bats
# BATS tests for contrib/install-gnome49.sh — GNOME 49 repo installer

REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
INSTALL_SCRIPT="${REPO_ROOT}/contrib/install-gnome49.sh"

@test "install-gnome49.sh: exists" {
  run test -f "${INSTALL_SCRIPT}"
  [ "$status" -eq 0 ]
}

@test "install-gnome49.sh: has bash shebang" {
  run head -1 "${INSTALL_SCRIPT}"
  [[ "$output" =~ ^#!/.*bash ]]
}

@test "install-gnome49.sh: has set -euo pipefail" {
  run grep 'set -euo pipefail' "${INSTALL_SCRIPT}"
  [ "$status" -eq 0 ]
}

@test "install-gnome49.sh: defines install_gpg_key function" {
  run grep 'install_gpg_key()' "${INSTALL_SCRIPT}"
  [ "$status" -eq 0 ]
}

@test "install-gnome49.sh: references GNOME 49 repo URL" {
  run grep 'gnome49' "${INSTALL_SCRIPT}"
  [ "$status" -eq 0 ]
}

@test "install-gnome49.sh: passes shellcheck" {
  if command -v shellcheck &>/dev/null; then
    run shellcheck "${INSTALL_SCRIPT}"
    [ "$status" -eq 0 ]
  else
    skip "shellcheck not installed"
  fi
}
