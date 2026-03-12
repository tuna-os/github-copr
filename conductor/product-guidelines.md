# Product Guidelines

## Prose Style
- **Technical and Direct**: Use clear, concise language suitable for a system administrator or DevOps engineer.
- **Documentation-Focused**: Prioritize actionable instructions and clear architectural explanations.
- **Consistent Terminology**: Use standard Linux, RPM, and Cloudflare terminology consistently throughout the codebase and documentation.

## User Experience (CLI & Backend)
- **Informative Feedback**: Scripts and GitHub Actions should provide clear logs and exit codes.
- **Fail Fast**: The build and upload process should halt immediately on errors with descriptive messages.
- **Minimal Complexity**: The system should be easy to set up with clear prerequisites and a streamlined build-to-host pipeline.

## Security and Integrity
- **GPG Verification**: All packages must be signed, and public keys must be easily accessible for verification.
- **Secure Secret Handling**: Use GitHub repository secrets for sensitive data like Cloudflare API tokens and GPG private keys.
- **Isolation**: Use Mock containers to ensure clean, isolated build environments that do not pollute the host or previous builds.
