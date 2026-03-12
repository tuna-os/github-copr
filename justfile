set dotenv-load := true

default:
    @just --list

# Build RPM for a single target
build target:
    #!/usr/bin/env bash
    set -euo pipefail
    
    if [ -z "{{target}}" ]; then
        echo "Error: target is required"
        exit 1
    fi
    
    mock -r {{target}} --init
    mock -r {{target}} --build src/*.src.rpm
    mock -r {{target}} --resultdir=./output/{{target}} clean

# Build and sign RPM for a single target
build-and-sign target:
    #!/usr/bin/env bash
    set -euo pipefail
    
    just build {{target}}
    rpmsign --addsign ./output/{{target}}/*.rpm

# Update repository metadata
update-metadata target:
    #!/usr/bin/env bash
    set -euo pipefail
    createrepo_c --update ./output/{{target}}/

# Build all x86_64 targets
build-x86_64: build-fedora-43-x86_64 build-almalinux-10-x86_64 build-centos-stream-10-x86_64

# Build all ARM64 targets
build-aarch64: build-fedora-43-aarch64 build-almalinux-10-aarch64 build-centos-stream-10-aarch64

# Build all targets
build-all: build-fedora-43-x86_64 build-almalinux-10-x86_64 build-almalinux-10-x86_64_v2 build-centos-stream-10-x86_64

build-fedora-43-x86_64:
    @just build fedora-43-x86_64

build-fedora-43-aarch64:
    @just build fedora-43-aarch64

build-almalinux-10-x86_64:
    @just build almalinux-10-x86_64

build-almalinux-10-x86_64_v2:
    @just build almalinux-10-x86_64_v2

build-almalinux-10-aarch64:
    @just build almalinux-10-aarch64

build-centos-stream-10-x86_64:
    @just build centos-stream-10-x86_64

build-centos-stream-10-aarch64:
    @just build centos-stream-10-aarch64

# Sign all RPMs in output directory
sign-all:
    #!/usr/bin/env bash
    set -euo pipefail
    find ./output -name "*.rpm" -exec rpmsign --addsign {} \;

# Sync to R2 bucket
sync-to-r2 target:
    #!/usr/bin/env bash
    set -euo pipefail
    aws s3 sync ./output/{{target}}/ "s3://${R2_BUCKET}/repo/{{target}}/" --delete
    aws s3 sync "s3://${R2_BUCKET}/repo/{{target}}/" ./repodata/{{target}}/
    createrepo_c --update ./repodata/{{target}}/
    aws s3 sync ./repodata/{{target}}/ "s3://${R2_BUCKET}/repo/{{target}}/" --delete

# Full build and publish pipeline
publish target:
    @just build-and-sign {{target}}
    @just update-metadata {{target}}
    @just sync-to-r2 {{target}}

# Publish all targets
publish-all: 
    @just publish fedora-43-x86_64
    @just publish almalinux-10-x86_64
    @just publish almalinux-10-x86_64_v2
    @just publish centos-stream-10-x86_64

# Clean build artifacts
clean:
    rm -rf output/ repodata/ build/

# Verify GPG setup
verify-gpg:
    #!/usr/bin/env bash
    set -euo pipefail
    if ! gpg --list-secret-keys | grep -q "RPM Signing"; then
        echo "Error: No GPG key found for RPM signing"
        exit 1
    fi
    echo "GPG key found:"
    gpg --list-secret-keys "RPM Signing"
