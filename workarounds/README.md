# EL10 + GNOME 50 Runtime Workarounds

These are the manual fixes applied to the test VM to get GNOME 50 running on
CentOS Stream 10. Each section describes the workaround file, the root cause,
and the proper RPM-level fix.

---

## 1. SELinux Policy (`selinux/`)

**Files:** `gdm-gnome50.te`, `gdm-userdb-connect.te`

**Problem:** EL10's stock `xdm_t` policy predates GDM 50's dynamic userdb Varlink
architecture. GDM 50 registers a socket at `/run/systemd/userdb/org.gnome.DisplayManager`
(inside the `systemd_userdbd_runtime_t`-labeled directory). EL10 policy forbids this.
`systemd-userdbd` and `unix_chkpwd` also need to connect to that socket to resolve
dynamic greeter users (`gdm-greeter-N`).

**Applied on VM:**
```bash
checkmodule -M -m -o gdm-gnome50.mod gdm-gnome50.te
semodule_package -o gdm-gnome50.pp -m gdm-gnome50.mod
semodule -X 300 -i gdm-gnome50.pp
# same for gdm-userdb-connect
```

**Proper fix — Build Rawhide `selinux-policy`:**

Rawhide's `xserver.te` already has the exact rule we need:
```
systemd_userdbd_named_runtime_filetrans(xdm_t, xdm_var_run_t, sock_file, "org.gnome.DisplayManager")
```
This allows GDM to create the userdb socket with the right label, and `systemd.te`
already has the `manage_sock_files_pattern` rules for `systemd_userdbd_t`.

Since we're bumping many GNOME 50 packages (gnome-shell, mutter, gdm, gnome-session),
each may need updated policy. Shipping Rawhide `selinux-policy` is the clean solution
— it covers all of them without per-package policy addon maintenance.

The `.te` files in `workarounds/selinux/` remain as a reference for what rules are
needed, and can serve as a fallback gdm-selinux sub-package if building the full
Rawhide selinux-policy proves problematic.

---

## 2. PAM: `systemd-user` service (`pam-systemd-user.conf`)

**Problem:** The `systemd-user` PAM service (`/usr/lib/pam.d/systemd-user`, owned by
`systemd` RPM) uses `pam_unix.so` for the account phase, which calls `unix_chkpwd`.
`unix_chkpwd` cannot resolve GDM 50's dynamic greeter users (`gdm-greeter-N`) served
via systemd userdb Varlink. It returns `PAM_AUTHINFO_UNAVAIL` (not `PAM_USER_UNKNOWN`),
so `[user_unknown=ignore]` does not help. `user@UID.service` fails; gnome-session
cannot launch.

**Applied on VM:** `/etc/pam.d/systemd-user` override with `account required pam_permit.so`

**Root cause — EL10 downstream patch, not upstream systemd:**

Upstream systemd's `src/login/systemd-user.in` template contains:
```
account  required  pam_permit.so   ← upstream default, would work fine
```

CentOS Stream 10 applies `Patch0254: 0254-fedora-use-system-auth-in-pam-systemd-user.patch`
(marked `rhel-only: feature`, Related: RHEL-40924) which replaces `pam_permit.so` with
`account include system-auth`. This triggers `pam_unix.so` → `unix_chkpwd` which
cannot resolve dynamic userdb users.

Additionally, the account stack tries `-account sufficient pam_systemd_home.so` first
(the `-` prefix means skip if not installed), but EL10 does **not** ship
`pam_systemd_home.so` (only `pam_systemd.so` and `pam_systemd_loadkey.so`). If
`pam_systemd_home.so` were available it would handle dynamic users correctly.

**This is not a bug to file upstream** — upstream's default is already correct.
It is an EL10-specific regression introduced by Patch0254 without `pam_systemd_home.so`
being available. It should be documented as a known incompatibility for anyone running
GDM 50 on EL10 before systemd is updated.

**Proper fix — `gnome50-el10-compat` RPM:**
We ship a standalone compat package (`src/deps/gnome50-el10-compat/`) that owns
`/etc/pam.d/systemd-user` (as `%config(noreplace)`) and restores the upstream
`pam_permit.so` behavior. This package serves as a temporary bridge until
systemd is updated in EL10.

---

## 3. GLib Schema Compilation

**Problem:** `gnome-session-service` aborts with
`Settings schema 'org.gnome.SessionManager' is not installed` because
`glib-compile-schemas` was not triggered after GNOME 50 packages were installed.

**Applied on VM:** `glib-compile-schemas /usr/share/glib-2.0/schemas/` (manual)

**Root cause:** Our `glib2.spec` is missing the `%transfiletriggerin` scriptlets that
Rawhide's `glib2.spec` uses:

```spec
%transfiletriggerin -- %{_datadir}/glib-2.0/schemas
glib-compile-schemas %{_datadir}/glib-2.0/schemas &> /dev/null || :

%transfiletriggerpostun -- %{_datadir}/glib-2.0/schemas
glib-compile-schemas %{_datadir}/glib-2.0/schemas &> /dev/null || :
```

**Proper fix:** Add these four triggers to our `glib2.spec` (and similarly the
`gio-querymodules` triggers for `%{_libdir}/gio/modules`). This is a straightforward
spec change with no risk — it makes schema compilation automatic on install/remove
of any package that drops files into `/usr/share/glib-2.0/schemas/`.

**Action:** Edit `src/gnome-50/glib2/glib2.spec` to add the triggers.

---

## 4. GDM Wayland (`gdm-custom.conf`)

**Problem:** If GDM is configured with `WaylandEnable=false`, it fails to start
because EL10 has no Xorg installed.

**Status:** Non-issue. GDM 50's compiled-in default is `WaylandEnable=true`. The
upstream `custom.conf` template (`data/gdm.conf-custom.in` in the tarball) has no
`WaylandEnable` key at all. Our `gdm.spec` does not override this default.
The manual `WaylandEnable=true` on the test VM was redundant.

**Action:** No spec change needed. Verify the installed `custom.conf` on a clean
install matches the upstream template (no `WaylandEnable=false`).
