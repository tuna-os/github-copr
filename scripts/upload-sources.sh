#!/usr/bin/env bash
#
# Upload sources to R2 lookaside cache
#
# Usage:
#   ./scripts/upload-sources.sh <spec-file> <source-url>

set -euo pipefail

BUCKET="${R2_BUCKET:-bluefin}"
R2_ENDPOINT="${R2_ENDPOINT:-https://r2.cloudflarestorage.com}"

usage() {
    echo "Usage: $0 <spec-file> <source-url>"
    echo ""
    echo "Example:"
    echo "  $0 glib2.spec https://download.gnome.org/sources/glib/2.80/glib-2.80.0.tar.xz"
}

upload_source() {
    local spec="$1"
    local url="$2"
    local name version
    
    name=$(rpm -qp --queryformat '%{NAME}' "$spec")
    version=$(rpm -qp --queryformat '%{VERSION}' "$spec")
    
    echo "Uploading sources for $name-$version"
    
    local tmpdir
    tmpdir=$(mktemp -d)
    trap 'rm -rf "$tmpdir"' EXIT
    
    local filename
    filename=$(basename "$url")
    
    echo "Downloading: $url"
    curl -SL "$url" -o "$tmpdir/$filename"
    
    local checksum
    checksum=$(sha256sum "$tmpdir/$filename" | cut -d' ' -f1)
    
    echo "SHA256: $checksum"
    echo "Uploading to R2..."
    
    aws s3 cp "$tmpdir/$filename" "s3://$BUCKET/sources/$name/$filename"
    
    echo "Sources uploaded successfully!"
    echo ""
    echo "Add to your spec file:"
    echo "Source0: https://$BUCKET.s3.amazonaws.com/sources/$name/$filename"
}

main() {
    if [ -z "${1:-}" ] || [ -z "${2:-}" ]; then
        usage
        exit 1
    fi
    
    upload_source "$1" "$2"
}

main "$@"
