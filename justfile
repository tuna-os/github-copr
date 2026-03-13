set dotenv-load := true

export R2_BUCKET := "bluefin"

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
    rclone --s3-no-check-bucket sync ./output/{{target}}/ "r2:${R2_BUCKET}/repo/{{target}}/"
    rclone --s3-no-check-bucket sync "r2:${R2_BUCKET}/repo/{{target}}/" ./repodata/{{target}}/
    createrepo_c --update ./repodata/{{target}}/
    rclone --s3-no-check-bucket sync ./repodata/{{target}}/ "r2:${R2_BUCKET}/repo/{{target}}/"

# Full build and publish pipeline
publish target:
    @just build-and-sign {{target}}
    @just update-metadata {{target}}
    @just sync-to-r2 {{target}}

# Deploy the Cloudflare Worker proxy
deploy-proxy:
    npx wrangler deploy

# Interactively check for required secrets and configuration
check-secrets:
    #!/usr/bin/env bash
    set -euo pipefail
    MISSING=0
    for s in R2_ACCESS_KEY_ID R2_SECRET_ACCESS_KEY CLOUDFLARE_ACCOUNT_ID GPG_PRIVATE_KEY GPG_PASSPHRASE; do
        if ! grep -q "$s" .env 2>/dev/null; then
            echo "[-] Missing secret in .env: $s"
            MISSING=$((MISSING+1))
        else
            echo "[+] Found secret in .env: $s"
        fi
    done
    if [ $MISSING -eq 0 ]; then
        echo "All secrets found in .env. You can now use 'just publish'."
    else
        echo "Please add the missing secrets to your .env file or GitHub Secrets."
    fi

# Initial setup for the project
setup:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "=== Initializing GitHub Copr-like RPM Repository ==="
    if ! command -v mock &>/dev/null; then echo "Warning: 'mock' not found. Local builds will fail."; fi
    if ! command -v createrepo_c &>/dev/null; then echo "Warning: 'createrepo_c' not found."; fi
    if ! command -v rclone &>/dev/null; then echo "Warning: 'rclone' not found. Syncing to R2 will fail."; fi
    if ! command -v wrangler &>/dev/null; then echo "Hint: install wrangler with 'npm install -g wrangler'"; fi
    
    if [ ! -f .env ]; then
        echo "Creating .env from .env.example..."
        cp .env.example .env
    fi
    
    if [ ! -f public.gpg ]; then
        echo "Warning: public.gpg not found. Follow GPG_SETUP.md to generate your signing key."
    fi
    
    echo "Setup complete. Check GPG_SETUP.md for key generation steps."

# Upload GPG public key and install script to R2 root
publish-static:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ ! -f public.gpg ]; then
        echo "Error: public.gpg not found. Run GPG export first."
        exit 1
    fi
    echo "Uploading public.gpg..."
    rclone --s3-no-check-bucket copyto public.gpg "r2:${R2_BUCKET}/public.gpg"
    echo "Uploading install.sh..."
    rclone --s3-no-check-bucket copyto contrib/install.sh "r2:${R2_BUCKET}/install.sh"

# Clean build artifacts
clean:
    rm -rf output/ repodata/ build/

# Pull all RPMs from R2, sign them, and push back
sign-r2:
    #!/usr/bin/env bash
    set -euo pipefail
    mkdir -p tmp-repo
    echo "Downloading existing repository from R2..."
    rclone --s3-no-check-bucket sync "r2:${R2_BUCKET}/repo/" ./tmp-repo/
    echo "Signing RPMs..."
    find ./tmp-repo -name "*.rpm" -exec rpmsign --addsign {} \;
    echo "Updating metadata..."
    for dir in ./tmp-repo/*; do
        if [ -d "$dir" ]; then
            createrepo_c --update "$dir"
        fi
    done
    echo "Uploading signed repository back to R2..."
    rclone --s3-no-check-bucket sync ./tmp-repo/ "r2:${R2_BUCKET}/repo/"
    rm -rf tmp-repo

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
