# BATS Tests for tuna-os/github-copr

This directory contains BATS (Bash Automated Testing System) tests for
the github-copr build and CI scripts.

## Running

```bash
# Install BATS
sudo apt-get install bats

# Run all tests
bats tests/bats/*.bats

# Run a single test file
bats tests/bats/test_build_chain.bats
```

## Test files

| File | Script tested |
|------|--------------|
| test_build_chain.bats | scripts/build-chain.sh |
| test_build_local.bats | scripts/build-local.sh |
| test_upload_sources.bats | scripts/upload-sources.sh |
| test_watch_pipeline.bats | scripts/watch-pipeline.sh |
