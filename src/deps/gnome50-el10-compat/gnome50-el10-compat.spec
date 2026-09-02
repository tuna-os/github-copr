Name:           gnome50-el10-compat
Version:        1.2.9
Release:        1%{?dist}
Summary:        GNOME 50 Compatibility workarounds for EL10

License:        MIT
Source0:        systemd-user.pam
Source1:        gdm-gnome50.te
Source2:        gdm-userdb-connect.te
Source3:        orca-autostart.desktop
Source4:        tuned-ppd-logging.te
Source5:        apply-gi-glib-compat.py
Source6:        useradd-wrapper

BuildArch:      noarch
BuildRequires:  checkpolicy
BuildRequires:  policycoreutils

Requires:       selinux-policy >= 43.1
Requires(post): policycoreutils
Requires(preun): policycoreutils
Requires(post): shadow-utils

%description
This package provides configuration overrides to restore upstream behavior
for components that regress when using GNOME 50 on CentOS Stream 10.

It provides:
- A systemd-user PAM service override to support GDM 50's dynamically-allocated
  greeter users (gdm-greeter-N), which EL10's pam_unix cannot resolve via
  unix_chkpwd.
- SELinux policy modules allowing GDM 50 to register as a systemd-userdb
  Varlink provider, which EL10's base xdm_t policy does not permit.
- An orca-autostart.desktop override (Hidden=true) to suppress unconditional
  Orca autostart. GNOME 50 removed AutostartCondition=GSettings evaluation from
  gnome-session; EL10's orca package relies on it to respect screen-reader-enabled.
  GNOME 50 expects Orca to be managed via systemd (orca.service), which is
  now shipped by orca >= 50.0.9 directly.
- A PyGObject GLib compatibility shim: GLib 2.87+ moved g_unix_signal_add to
  the GLibUnix-2.0 GI namespace. EL10's python3-gobject 3.46 does not know
  this mapping, breaking GLib.unix_signal_add consumers (firewalld, etc.).
  This patches gi/overrides/GLib.py to shim GLib.unix_signal_add from GLibUnix.

%prep
cp %{SOURCE1} gdm-gnome50.te
cp %{SOURCE2} gdm-userdb-connect.te
cp %{SOURCE4} tuned-ppd-logging.te
cp %{SOURCE5} apply-gi-glib-compat.py

%build
checkmodule -M -m -o gdm-gnome50.mod gdm-gnome50.te
semodule_package -o gdm-gnome50.pp -m gdm-gnome50.mod

checkmodule -M -m -o gdm-userdb-connect.mod gdm-userdb-connect.te
semodule_package -o gdm-userdb-connect.pp -m gdm-userdb-connect.mod

checkmodule -M -m -o tuned-ppd-logging.mod tuned-ppd-logging.te
semodule_package -o tuned-ppd-logging.pp -m tuned-ppd-logging.mod

%install
mkdir -p %{buildroot}%{_sysconfdir}/pam.d
cp %{SOURCE0} %{buildroot}%{_sysconfdir}/pam.d/systemd-user

install -d %{buildroot}%{_datadir}/selinux/packages
install -m 644 gdm-gnome50.pp %{buildroot}%{_datadir}/selinux/packages/
install -m 644 gdm-userdb-connect.pp %{buildroot}%{_datadir}/selinux/packages/
install -m 644 tuned-ppd-logging.pp %{buildroot}%{_datadir}/selinux/packages/

install -d %{buildroot}%{_datadir}/gnome50-el10-compat
install -m 755 apply-gi-glib-compat.py %{buildroot}%{_datadir}/gnome50-el10-compat/
install -d %{buildroot}%{_libexecdir}/%{name}
install -m 755 %{SOURCE6} %{buildroot}%{_libexecdir}/%{name}/useradd

# Suppress unconditional Orca autostart (GNOME 50 dropped AutostartCondition evaluation)
# Written via %post/%filetriggerin to avoid file conflict with orca package.

# Preserve real useradd binary before alternatives symlinks it.
%pre
if [ -f /usr/sbin/useradd ] && [ ! -L /usr/sbin/useradd ]; then
    cp -a /usr/sbin/useradd /usr/sbin/useradd.shadow-utils
fi

%post
# Install useradd wrapper alternative (#17: handle EEXIST on existing home dir).
if [ $1 -ge 1 ]; then
    alternatives --install /usr/sbin/useradd useradd %{_libexecdir}/%{name}/useradd 50
fi

if [ $1 -ge 1 ]; then
    %{_sbindir}/semodule -X 300 -i \
        %{_datadir}/selinux/packages/gdm-gnome50.pp \
        %{_datadir}/selinux/packages/gdm-userdb-connect.pp \
        %{_datadir}/selinux/packages/tuned-ppd-logging.pp 2>/dev/null || :
fi
# Override orca autostart: GNOME 50 dropped AutostartCondition evaluation,
# so orca launches unconditionally. Write Hidden=true without owning the file
# (orca package owns it; we overwrite after install to avoid RPM conflict).
mkdir -p %{_sysconfdir}/xdg/autostart
cat > %{_sysconfdir}/xdg/autostart/orca-autostart.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=Orca Screen Reader
Exec=orca
Hidden=true
X-GNOME-Autostart-enabled=false
EOF
# Apply PyGObject GLib→GLibUnix shim (see Source5 for rationale)
python3 %{_datadir}/gnome50-el10-compat/apply-gi-glib-compat.py 2>/dev/null || :

# Re-apply PyGObject shim whenever python3-gobject updates GLib.py.
%filetriggerin -- /usr/lib/python3.12/site-packages/gi/overrides/GLib.py
python3 %{_datadir}/gnome50-el10-compat/apply-gi-glib-compat.py 2>/dev/null || :

# Fire whenever orca installs or updates its autostart file (handles orca
# installing AFTER this package in a later transaction, e.g. in image builds).
%filetriggerin -- /etc/xdg/autostart/orca-autostart.desktop
cat > /etc/xdg/autostart/orca-autostart.desktop << 'EOF'
[Desktop Entry]
Type=Application
Name=Orca Screen Reader
Exec=orca
Hidden=true
X-GNOME-Autostart-enabled=false
EOF

%preun
if [ $1 -eq 0 ]; then
    alternatives --remove useradd %{_libexecdir}/%{name}/useradd 2>/dev/null || :
    %{_sbindir}/semodule -X 300 -r gdm-gnome50 gdm-userdb-connect tuned-ppd-logging 2>/dev/null || :
fi

%postun
if [ $1 -eq 0 ]; then
    if [ -f /usr/sbin/useradd.shadow-utils ] && \
       { [ ! -e /usr/sbin/useradd ] || [ -L /usr/sbin/useradd ]; }; then
        mv /usr/sbin/useradd.shadow-utils /usr/sbin/useradd
    fi
fi

%files
%config(noreplace) %{_sysconfdir}/pam.d/systemd-user
%{_datadir}/selinux/packages/gdm-gnome50.pp
%{_datadir}/selinux/packages/gdm-userdb-connect.pp
%{_datadir}/selinux/packages/tuned-ppd-logging.pp
%dir %{_datadir}/gnome50-el10-compat
%{_datadir}/gnome50-el10-compat/apply-gi-glib-compat.py
%{_libexecdir}/%{name}/useradd

%changelog
* Fri Aug 14 2026 James Reilly <jreilly1821@gmail.com> - 1.2.9-1
- useradd-wrapper: fix `local: can only be used in a function` crash.
  The -m/existing-home-dir branch used `local add_M=true` at the
  script's top level (not inside a function); under `set -euo
  pipefail` that error exits the wrapper with status 1 before it ever
  calls the real useradd, silently breaking every `useradd -m` call
  that hits the exact scenario the wrapper exists to handle (#17).
  Also fixed an SC2015 `A && B || C` pattern shellcheck flagged in the
  same function. Added tests/bats/test_gnome50_el10_compat_useradd_wrapper.bats
  (tunaos-packages#392) so a regression like this fails in CI instead
  of only in a live gnome-initial-setup run.

* Thu Jul 24 2026 James Reilly <jreilly1821@gmail.com> - 1.2.8-1
- gdm-gnome50.te: add unix_stream_socket bind+listen permissions for xdm_t.
  GDM 50 registers a systemd-userdb Varlink socket and calls bind()/listen()
  on its own socket; sock_file:create alone is insufficient — SELinux also
  requires unix_stream_socket:{bind listen} on self. Without this, GDM fails
  with "Failed to listen on userdb socket: Permission denied" on EL10 COPR
  CI runners with SELinux enforcing. Fixes #70.

* Thu Apr 02 2026 James Reilly <jreilly1821@gmail.com> - 1.2.7-3
- Add useradd wrapper via alternatives(8) to handle existing home
  directory gracefully. EL10 shadow-utils 4.15 treats mkdir()→EEXIST
  as fatal (exit 12, E_HOMEDIR); the wrapper strips -m/--create-home
  when the target directory already exists and chowns it instead.
  Fixes gnome-initial-setup failure on preserved /var/home (#17).

* Thu Apr 02 2026 James Reilly <jreilly1821@gmail.com> - 1.2.7-2
- %%post: drop ineffective restorecon -RF /var/home (see #22). The
  compose-time %%post cannot fix preserved-/var scenarios on deployed
  systems; the actual fix for useradd exit 12 belongs at the runtime
  or shadow-utils level (#17).

* Thu Apr 02 2026 James Reilly <jreilly1821@gmail.com> - 1.2.7-1
- %%post: add restorecon -RF /var/home to fix default_t/unlabeled_t labeling
  in reinstall/upgrade scenarios where /var is not wiped. Fixes useradd
  exit 12 (E_HOMEDIR) during gnome-initial-setup (issues #16, #17).

* Mon Mar 30 2026 James Reilly <jreilly1821@gmail.com> - 1.2.6-1
- gdm-gnome50.te: allow xdm_t status on systemd_unit_file_t:service so
  gnome-session-init-worker can query unit status during greeter startup (issue #15)

* Sat Mar 28 2026 James Reilly <jreilly1821@gmail.com> - 1.2.5-2
- Fix duplicate %%post section that prevented SRPM creation; merge PyGObject
  shim invocation into the single %%post block

* Sat Mar 28 2026 James Reilly <jreilly1821@gmail.com> - 1.2.5-1
- Add PyGObject GLib→GLibUnix compat shim: GLib 2.87+ moved g_unix_signal_add
  to the GLibUnix-2.0 GI namespace; EL10's python3-gobject 3.46 does not know
  this mapping. Patch gi/overrides/GLib.py via %%post and %filetriggerin so
  GLib.unix_signal_add works again, fixing firewalld startup crash and any
  other Python GI consumer using GLib.unix_signal_add or unix_signal_add_full.

* Tue Mar 25 2026 James <james@example.com> - 1.2.4-1
- Add tuned-ppd-logging SELinux module: EL10 base policy does not grant
  tuned_ppd_t access to var_log_t; this allows tuned-ppd to write its
  log to /var/log/tuned/tuned-ppd.log without AVC denials.

* Mon Mar 23 2026 James <james@example.com> - 1.2.3-1
- Drop orca.service: now shipped natively by orca >= 50.0.9, which is
  available in c10s-gnome-50 COPR. Avoids file conflict on upgrade.

* Mon Mar 23 2026 James <james@example.com> - 1.2.2-1
- Add %filetriggerin on orca-autostart.desktop to reliably write Hidden=true
  regardless of package install order. Fixes race in image builds where orca
  installs in a later transaction after our %%post already ran.

* Sun Mar 23 2026 James <james@example.com> - 1.2.1-1
- Fix orca-autostart.desktop file conflict with orca package: write the
  Hidden=true override via %%post scriptlet instead of shipping the file,
  since orca owns /etc/xdg/autostart/orca-autostart.desktop.

* Sun Mar 22 2026 James <james@example.com> - 1.2.0-1
- Add orca-autostart.desktop override (Hidden=true): GNOME 50 removed
  AutostartCondition=GSettings evaluation from gnome-session, causing Orca
  to autostart unconditionally on EL10. Fixes issues #10 and #11.
- Add orca.service systemd user unit so gsd-a11y-settings can enable/disable
  Orca correctly when screen-reader-enabled is toggled. Fixes the
  "Spawning fallback Orca" gsd-a11y-settings error.

* Sat Mar 21 2026 James <james@example.com> - 1.1.0-1
- Bundle SELinux policy modules into the RPM.
  The .te sources existed in workarounds/selinux/ but were never compiled
  or installed by the package. This caused GDM 50 startup failures under
  SELinux enforcing mode on EL10 even when gnome50-el10-compat was installed.
  Modules are loaded at semodule priority 300 via %%post/%%preun scriptlets.
  Add BuildRequires: checkpolicy, policycoreutils for compilation.

* Mon Mar 20 2026 James <james@example.com> - 1.0.1-1
- Add Requires: selinux-policy >= 43.1 for GDM 50 userdb socket policy.

* Sat Mar 14 2026 James <james@example.com> - 1.0.0-1
- Initial release with systemd-user PAM workaround for dynamic GDM users.
