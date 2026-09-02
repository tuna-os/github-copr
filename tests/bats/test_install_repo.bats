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

# tunaos-packages#394: install.sh wrote gpgcheck=0/repo_gpgcheck=0 into the
# repo file it installs on every user's system, so RPMs from repo.tunaos.org
# installed with zero authenticity check even though the key-import step
# right above it made it look like they were verified. Every publish
# pipeline signs its RPMs (rpmsign --addsign), so gpgcheck=1 is real
# protection; repo_gpgcheck stays 0 because repomd.xml isn't detached-signed
# yet (no repomd.xml.asc published) and =1 would hard-fail every dnf
# transaction instead of adding a check.
@test "install.sh: enables gpgcheck for the installed repo" {
  run grep 'gpgcheck=1' "${INSTALL_SCRIPT}"
  [ "$status" -eq 0 ]
  run grep -c '^gpgcheck=0$' "${INSTALL_SCRIPT}"
  [ "$output" -eq 0 ]
}

@test "install.sh: imports the GPG key under the name the repo config actually references" {
  # RPM-GPG-KEY-james-rc (the old filename) never matched anything the repo
  # file pointed at -- the key import was pure theater. Assert both halves
  # agree, and specifically that the stale name is gone.
  run grep -oE '/etc/pki/rpm-gpg/[A-Za-z0-9_-]+' "${INSTALL_SCRIPT}"
  [ "$status" -eq 0 ]
  local names
  names="$(printf '%s\n' "$output" | sort -u)"
  [ "$(printf '%s\n' "$names" | wc -l)" -eq 1 ]
  ! grep -q 'RPM-GPG-KEY-james-rc' "${INSTALL_SCRIPT}"
}
