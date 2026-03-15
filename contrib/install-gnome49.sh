#!/usr/bin/env bash
#
# TunaOS GNOME 49 RPM Repository
#
# Usage:
#   curl -sSL https://repo.tunaos.org/gnome49/install.sh | sudo bash
#
set -euo pipefail

REPO_URL="https://repo.tunaos.org/gnome49/10-stream-x86_64"
REPO_NAME="tunaos-gnome49"
GPG_KEY_URL="https://repo.tunaos.org/public.gpg"
GPG_KEY_PATH="/etc/pki/rpm-gpg/RPM-GPG-KEY-tunaos"

install_gpg_key() {
    echo "Installing GPG key..."
    curl -sSLo "${GPG_KEY_PATH}" "${GPG_KEY_URL}"
    rpm --import "${GPG_KEY_PATH}" 2>/dev/null || true
}

install_repo_file() {
    cat > "/etc/yum.repos.d/${REPO_NAME}.repo" << EOF
[${REPO_NAME}]
name=TunaOS GNOME 49 for CentOS Stream 10
baseurl=${REPO_URL}/
enabled=1
gpgcheck=1
gpgkey=${GPG_KEY_URL}
repo_gpgcheck=0
metadata_expire=3600
priority=10
EOF
    echo "Repository file installed: /etc/yum.repos.d/${REPO_NAME}.repo"
}

verify() {
    echo "Verifying repository..."
    dnf repolist "${REPO_NAME}" 2>/dev/null || true
    echo "Testing package availability..."
    dnf info gdm 2>/dev/null | grep -E "Version|Repo" || echo "gdm not yet available (repo may be empty)"
}

main() {
    echo "Installing TunaOS GNOME 49 repository..."
    install_gpg_key
    install_repo_file
    verify
    echo ""
    echo "Done! Install GNOME 49 with:"
    echo "  dnf install gnome-shell mutter gdm gnome-session gnome49-el10-compat"
}

main "$@"
