#!/usr/bin/env bash
#
# Install James Reilly Consulting RPM Repository
#
# Usage:
#   curl -sSL https://repo.yourdomain.com/install.sh | sudo bash
#   # Or download and inspect first:
#   curl -sSLO https://repo.yourdomain.com/install.sh && chmod +x install.sh

set -euo pipefail

REPO_URL="${REPO_URL:-https://repo.yourdomain.com}"
REPO_NAME="${REPO_NAME:-james-rc}"

detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        case "$ID" in
            fedora)
                echo "fedora"
                ;;
            rhel|centos|alma|rocky)
                echo "el"
                ;;
            *)
                echo "unknown"
                ;;
        esac
    else
        echo "unknown"
    fi
}

detect_version() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        case "$ID" in
            fedora)
                echo "$VERSION_ID"
                ;;
            rhel|centos|alma|rocky)
                echo "$VERSION_ID"
                ;;
            *)
                echo "9"
                ;;
        esac
    else
        echo "9"
    fi
}

install_gpg_key() {
    echo "Installing GPG key..."
    curl -sSLo /etc/pki/rpm-gpg/RPM-GPG-KEY-james-rc "$REPO_URL/public.gpg"
    rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-james-rc 2>/dev/null || true
}

install_repo_file() {
    local version
    version=$(detect_version)
    
    cat > "/etc/yum.repos.d/${REPO_NAME}.repo" << EOF
[${REPO_NAME}]
name=James Reilly Consulting - \$releasever
baseurl=${REPO_URL}/repo/\$releasever/\$basearch/
enabled=1
gpgcheck=1
gpgkey=${REPO_URL}/public.gpg
repo_gpgcheck=0
metadata_expire=3600
priority=10
EOF

    echo "Repository installed for version: $version"
}

verify_installation() {
    echo "Verifying installation..."
    if dnf repolist "$REPO_NAME" >/dev/null 2>&1; then
        echo "Repository enabled successfully!"
        dnf repolist "$REPO_NAME"
    else
        echo "Warning: Repository may not be enabled. Try:"
        echo "  dnf config-manager --enable ${REPO_NAME}"
    fi
}

main() {
    echo "Installing ${REPO_NAME} repository from ${REPO_URL}..."
    
    install_gpg_key
    install_repo_file
    verify_installation
    
    echo ""
    echo "Installation complete!"
    echo "To install packages from this repository, run:"
    echo "  dnf install <package-name>"
    echo ""
    echo "To update all packages from this repository:"
    echo "  dnf update --repo=${REPO_NAME}"
}

main "$@"
