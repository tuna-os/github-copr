# Tideforge action cache

A package build is a content-addressed action, not an opaque CI run. Its key
hashes the complete recipe directory, selected target contract, architecture,
immutable build-image digest, renderer scripts, and dependency action keys.
Changing one target cannot reuse another target's output.

An ActionResult lives at `actions/sha256/<key>.json` in R2 and records every
artifact name, size, and SHA-256. A hit is usable only after restoring artifacts
and verifying that manifest. Pull requests never publish an R2 ActionResult;
trusted default-branch builds do so after package lint and clean-install tests.

The GitHub cache action is an acceleration layer, not authority. It may restore
bytes for the same action key; result hashes decide whether those bytes are
accepted. R2 promotion, signatures, SBOMs and provenance attach to that same
ActionResult without changing the identity.

This follows Bazel's action-cache/CAS split, Homebrew's bottle JSON plus
checksum validation, and Chainguard's digest/provenance verification.
