# Initial Concept
A consultant-grade RPM build and hosting system using GitHub Actions and Cloudflare R2.

# Product Definition

## Vision
A consultant-grade RPM build and hosting system that leverages GitHub Actions for automated building and signing, with Cloudflare R2 providing high-performance, cost-effective repository storage and distribution.

## Target Audience
- System administrators and developers who need a private or public RPM repository.
- Projects requiring multi-distribution and multi-architecture RPM builds (Fedora, AlmaLinux, CentOS Stream).
- Teams looking for a lightweight alternative to full-scale Copr instances.

## Core Features
- **Automated RPM Building**: Isolated chroot builds using Mock within GitHub Actions.
- **Multi-Distribution Support**: Support for modern Fedora and Enterprise Linux variants.
- **Multi-Architecture**: Support for x86_64 and aarch64.
- **GPG Signing**: Automatic package signing with a dedicated GPG key.
- **Cloudflare R2 Integration**: Seamless upload and hosting with zero egress fees.
- **Repository Proxy**: A Cloudflare Worker to proxy dnf/yum requests and manage metadata access.

## Success Criteria
- Successful end-to-end build, sign, and upload pipeline.
- Functional dnf/yum repository accessible via the Cloudflare Worker proxy.
- Secure GPG signing verified by package managers.
