# GPG Key Setup for RPM Signing

This repository uses a dedicated GPG subkey for signing RPMs. Follow these steps to set up the key infrastructure.

## Generating a Dedicated GPG Key

**Do NOT use your personal GPG key for production signing.**

```bash
# Generate a new GPG key with dedicated purpose
gpg --full-generate-key

# Select:
# - RSA and RSA (default)
# - 4096 bits
# - Key does not expire (or set appropriate expiration)
# - Enter a dedicated name: "James Reilly Consulting RPM Signing"
# - Email: rpm-signing@yourdomain.com
```

## Creating a Signing Subkey

```bash
# Edit the newly created key
gpg --edit-key <key-id>

# Add a signing-only subkey
gpg> addkey
# Select: RSA (sign only), 4096 bits, expiration as desired
gpg> save
```

## Exporting Keys

```bash
# Export secret key (for GitHub Actions)
gpg --armor --export-secret-keys <key-id> > private.key

# Export public key (for repo consumers)
gpg --armor --export <key-id> > public.gpg
```

## GitHub Secrets Configuration

In your GitHub repository, go to **Settings → Secrets and variables → Actions** and add:

| Secret Name | Value |
|-------------|-------|
| `R2_ACCESS_KEY_ID` | Your Cloudflare R2 access key |
| `R2_SECRET_ACCESS_KEY` | Your Cloudflare R2 secret key |
| `CLOUDFLARE_ACCOUNT_ID` | Your Cloudflare account ID |
| `GPG_PRIVATE_KEY` | Contents of `private.key` |
| `GPG_PASSPHRASE` | Passphrase for the GPG key (if protected) |

## R2 Bucket Setup

1. Create a new R2 bucket (e.g., `repo-james-rc`)
2. Set up CORS to allow GitHub Actions:
   ```json
   [
     {
       "AllowedOrigins": ["https://github.com"],
       "AllowedMethods": ["GET", "PUT", "DELETE"],
       "AllowedHeaders": ["*"]
     }
   ]
   ```
3. Either:
   - Enable Public Access in bucket settings, OR
   - Use a Cloudflare Worker to proxy requests

## Verifying the Setup

After configuring GitHub Secrets, test with:
```bash
just verify-gpg
```
