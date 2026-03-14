# GitHub Issue: [EL10] systemd-user PAM regression: Patch0254 breaks dynamic GDM 50 greeter users

**Title:** [EL10] systemd-user PAM regression: Patch0254 breaks dynamic GDM 50 greeter users

**Description:**
The CentOS Stream 10 `systemd` package includes `Patch0254: 0254-fedora-use-system-auth-in-pam-systemd-user.patch`, which replaces the upstream `account required pam_permit.so` with `account include system-auth` in `/usr/lib/pam.d/systemd-user`.

This change causes a regression when using GDM 50 (from Rawhide/Fedora 43), which uses dynamically allocated greeter users (`gdm-greeter-N`) served via the `systemd userdb` Varlink API.

**Details:**
1. `pam_unix.so` (included via `system-auth`) calls `unix_chkpwd` for the account phase.
2. `unix_chkpwd` cannot resolve the dynamic users served by `systemd-userdbd`.
3. It returns `PAM_AUTHINFO_UNAVAIL`, which causes the account phase to fail.
4. `user@UID.service` fails to start, preventing `gnome-session` from launching for the greeter.

**Upstream Status:**
Upstream `systemd` (src/login/systemd-user.in) correctly uses `pam_permit.so`. This is an EL10-specific regression.

**Proposed Fix:**
Revert `Patch0254` or ensure `pam_systemd_home.so` is available and used correctly for dynamic users. In the meantime, we are providing a compatibility package `gnome50-el10-compat` that restores the upstream behavior by providing an override at `/etc/pam.d/systemd-user`.
