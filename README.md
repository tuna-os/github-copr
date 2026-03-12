# GitHub Copr-like RPM Repository

A consultant-grade RPM build and hosting system using GitHub Actions and Cloudflare R2.

## Features

- **Multi-distribution builds**: Fedora, AlmaLinux, CentOS Stream
- **Multi-architecture**: x86_64, x86_64_v2, aarch64
- **GPG signing**: Dedicated signing key for RPMs
- **Cloudflare R2**: Zero egress fees storage
- **Automatic retention**: Keeps only latest 3 versions

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   GitHub Actions│────▶│  Mock Container  │────▶│  Cloudflare R2  │
│   (Builds RPMs) │     │  (Isolated chroot)    │  (Host repo)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                │                         │
                                ▼                         ▼
                         ┌──────────────────┐     ┌─────────────────┐
                         │  GPG Signing     │     │  Cloudflare     │
                         │  (RPMs signed)   │     │  Worker (dnf)   │
                         └──────────────────┘     └─────────────────┘
```

## Prerequisites

- GitHub repository
- Cloudflare account with R2
- GPG key for signing

## Step 1: Cloudflare R2 Setup

1. **Create R2 Bucket**
   - Go to Cloudflare Dashboard → R2
   - Create bucket: `repo-james-rc` (or your preferred name)
   - Enable "Public Access" or use Worker for access

2. **Create API Token**
   - R2 → Manage API Tokens
   - Create token with:
     - `Read` and `Write` permissions for the bucket
   - Note the Access Key ID and Secret Key

3. **Get Account ID**
   - Found in Cloudflare Dashboard URL: `https://dash.cloudflare.com/<ACCOUNT_ID>/...`

## Step 2: GPG Key Setup

Generate a dedicated signing key (NOT your personal key):

```bash
# Generate key
gpg --full-generate-key
# RSA 4096, name: "RPM Signing", email: rpm-signing@yourdomain.com

# Create subkey for signing
gpg --edit-key <KEYID>
gpg> addkey
# RSA 4096, sign only
gpg> save

# Export keys
gpg --armor --export-secret-keys <KEYID> > private.key
gpg --armor --export <KEYID> > public.gpg
```

## Step 3: GitHub Secrets

Add these in Repository → Settings → Secrets and variables → Actions:

| Secret | Value |
|--------|-------|
| `R2_ACCESS_KEY_ID` | R2 Access Key ID |
| `R2_SECRET_ACCESS_KEY` | R2 Secret Key |
| `CLOUDFLARE_ACCOUNT_ID` | Cloudflare Account ID |
| `GPG_PRIVATE_KEY` | Contents of `private.key` |
| `GPG_PASSPHRASE` | GPG key passphrase (if any) |

## Step 4: GitHub Actions Settings

Enable ARM64 runners:
1. Go to Settings → Actions → General
2. Enable "Allow all actions and reusable workflows"
3. For ARM64: no additional setup needed (free on public repos)

## Step 5: Configure Repository

Edit `justfile` and `.github/workflows/build.yml` to set your bucket name:

```yaml
# .github/workflows/build.yml
env:
  R2_BUCKET: your-bucket-name
```

## Build Targets

| Target | Architecture | Distribution |
|--------|---------------|---------------|
| `fedora-43-x86_64` | x86_64 | Fedora 43 |
| `fedora-43-aarch64` | ARM64 | Fedora 43 |
| `almalinux-10-x86_64` | x86_64 | AlmaLinux 10 |
| `almalinux-10-x86_64_v2` | x86_64 (SSE4.2+) | AlmaLinux 10 |
| `almalinux-10-aarch64` | ARM64 | AlmaLinux 10 |
| `centos-stream-10-x86_64` | x86_64 | CentOS Stream 10 |
| `centos-stream-10-aarch64` | ARM64 | CentOS Stream 10 |

## Adding Packages

1. Create spec file in `src/` directory:
   ```
   src/
   ├── hello-world.spec
   └── hello-world-1.0.0/
       ├── hello.c
       └── Makefile
   ```

2. Build locally:
   ```bash
   ./scripts/build-local.sh hello-world fedora-43-x86_64
   ```

3. Or push to trigger CI:
   ```bash
   git add .
   git commit -m "Add hello-world package"
   git push
   ```

## Installing from Your Repository

### Option 1: Manual repo file

Create `/etc/yum.repos.d/james-rc.repo`:

```ini
[james-rc]
name=James Reilly Consulting - $releasever
baseurl=https://your-domain.com/repo/$releasever/$basearch/
enabled=1
gpgcheck=1
gpgkey=https://your-domain.com/public.gpg
repo_gpgcheck=0
```

### Option 2: Auto-install script

```bash
curl -sSL https://your-domain.com/install.sh | sudo bash
```

## Cloudflare Worker (Optional)

For custom domain and extra security:

1. Install Wrangler: `npm install -g wrangler`
2. Configure `wrangler.toml` with your domain
3. Deploy: `wrangler deploy`

The worker handles:
- dnf/yum metadata requests
- Security headers
- Request logging
- Path rewriting

## Local Development

```bash
# Install dependencies
dnf install -y mock createrepo_c rpm-sign

# Build package
just build fedora-43-x86_64

# Build all targets
just build-all

# Publish to R2
just publish fedora-43-x86_64
```

## Troubleshooting

### Mock fails with permission errors
Ensure you're running with appropriate permissions or use the container approach.

### R2 upload fails
Check that your AWS CLI credentials are correct and R2 endpoint is set properly.

### GPG signing fails
Ensure GPG_AGENT_INFO is set and key is imported in the workflow.

## File Structure

```
.
├── .github/workflows/build.yml   # CI/CD pipeline
├── Dockerfile                    # Mock builder container
├── justfile                     # Local build commands
├── scripts/
│   ├── build-local.sh          # Container-based build
│   ├── upload-sources.sh      # Upload sources to R2
│   └── cleanup.py              # Retention policy
├── workers/repo-proxy.ts       # Cloudflare Worker
├── contrib/
│   ├── james-rc.repo          # Repo file template
│   └── install.sh             # Auto-install script
└── src/                       # Package sources and specs
```

## License

MIT
