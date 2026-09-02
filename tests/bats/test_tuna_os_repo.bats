#!/usr/bin/env bats
# BATS tests for contrib/tuna-os.repo — the yum repo file fetched at
# image-build time by tunaOS's build_scripts/desktop/xfce.sh and written to
# /etc/yum.repos.d/.

REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
REPO_FILE="${REPO_ROOT}/contrib/tuna-os.repo"

@test "tuna-os.repo: exists" {
  run test -f "${REPO_FILE}"
  [ "$status" -eq 0 ]
}

@test "tuna-os.repo: declares a gpgkey" {
  run grep '^gpgkey=' "${REPO_FILE}"
  [ "$status" -eq 0 ]
}

# tunaos-packages#394: this file shipped gpgcheck=0/repo_gpgcheck=0 even
# though it declares a gpgkey= right next to them -- the key was fetched and
# imported for nothing, since nothing ever checked package signatures
# against it. Every publish pipeline signs its RPMs (rpmsign --addsign), so
# gpgcheck=1 is real protection; repo_gpgcheck stays 0 because repomd.xml
# isn't detached-signed yet (no repomd.xml.asc published) and =1 would
# hard-fail every dnf transaction instead of adding a check.
@test "tuna-os.repo: enables gpgcheck" {
  run grep -c '^gpgcheck=1$' "${REPO_FILE}"
  [ "$output" -eq 1 ]
  run grep -c '^gpgcheck=0$' "${REPO_FILE}"
  [ "$output" -eq 0 ]
}
