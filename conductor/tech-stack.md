# Tech Stack

## Programming Languages
- **TypeScript**: Used for the Cloudflare Worker repository proxy (`workers/repo-proxy.ts`).
- **Bash/Python**: Used for build and maintenance scripts (`scripts/`).
- **C/C++**: The example RPM source language (`src/`).

## Frameworks, Platforms, and Tooling
- **Cloudflare Workers**: High-performance repository proxy.
- **GitHub Actions**: Automated CI/CD pipeline for builds, signing, and uploads.
- **fedpkg**: Used for interacting with Fedora Dist-Git to fetch specifications from Rawhide.

## Storage and Infrastructure
- **Cloudflare R2**: Object storage for RPMs and repository metadata.
- **Mock**: Used for creating isolated chroot build environments per target distribution.

## Security
- **GPG (GNU Privacy Guard)**: Used for signing RPM packages and repository metadata.
- **GitHub Secrets**: Secure storage for API tokens and private keys.
