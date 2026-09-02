#!/usr/bin/env bats
# tunaos-packages#392: the useradd wrapper (src/deps/gnome50-el10-compat,
# installed via alternatives(8) to work around EL10 shadow-utils 4.15's
# E_HOMEDIR failure on a pre-existing home dir -- see #17) had zero test
# coverage. That gap hid a real bug: the `-m` + existing-home-dir branch
# used `local add_M=true` at the top level of the script, not inside a
# function. Under `set -euo pipefail`, bash's "local: can only be used in
# a function" error exits the wrapper with status 1 *before it ever calls
# the real useradd* -- silently breaking every `useradd -m` call that hits
# the exact scenario the wrapper exists to handle. These tests exercise
# the wrapper as a real subprocess (not sourced), the same way alternatives
# invokes it, so a regression like that fails loudly here instead of only
# in a live gnome-initial-setup run.

REPO_ROOT="$(cd "${BATS_TEST_DIRNAME}/../.." && pwd)"
WRAPPER="${REPO_ROOT}/src/deps/gnome50-el10-compat/useradd-wrapper"

setup() {
  TEST_DIR="$(mktemp -d)"
  FAKE_BIN="${TEST_DIR}/fakebin"
  mkdir -p "${FAKE_BIN}"
  REAL_USERADD_LOG="${TEST_DIR}/real-useradd.log"
  cat > "${FAKE_BIN}/useradd.shadow-utils" <<EOF
#!/usr/bin/env bash
echo "\$*" >> "${REAL_USERADD_LOG}"
exit 0
EOF
  chmod +x "${FAKE_BIN}/useradd.shadow-utils"
  export REAL_USERADD="${FAKE_BIN}/useradd.shadow-utils"
}

teardown() {
  rm -rf "${TEST_DIR}"
}

@test "useradd-wrapper passes shellcheck" {
  run shellcheck "${WRAPPER}"
  [ "$status" -eq 0 ]
}

@test "wrapper exits 0 and strips -m when the home directory already exists" {
  mkdir -p "${TEST_DIR}/home/existinguser"
  run bash "${WRAPPER}" -m -d "${TEST_DIR}/home/existinguser" existinguser
  [ "$status" -eq 0 ]
  run cat "${REAL_USERADD_LOG}"
  [[ "$output" != *"-m"* ]]
  [[ "$output" == *"-M"* ]]
  [[ "$output" == *"existinguser"* ]]
}

@test "wrapper leaves -m untouched when the home directory does not exist" {
  run bash "${WRAPPER}" -m -d "${TEST_DIR}/home/newuser" newuser
  [ "$status" -eq 0 ]
  run cat "${REAL_USERADD_LOG}"
  [[ "$output" == *"-m"* ]]
  [[ "$output" != *"-M"* ]]
}

@test "wrapper passes calls without -m straight through unmodified" {
  run bash "${WRAPPER}" -r systemduser
  [ "$status" -eq 0 ]
  run cat "${REAL_USERADD_LOG}"
  [ "$output" = "-r systemduser" ]
}

@test "wrapper preserves an explicit -M alongside other args when home exists" {
  mkdir -p "${TEST_DIR}/home/explicituser"
  run bash "${WRAPPER}" -M -d "${TEST_DIR}/home/explicituser" explicituser
  [ "$status" -eq 0 ]
  run cat "${REAL_USERADD_LOG}"
  [[ "$output" == *"-M"* ]]
  # -M must appear exactly once, not doubled by the wrapper's own add_M logic
  [ "$(grep -o -- '-M' <<<"$output" | wc -l)" -eq 1 ]
}
