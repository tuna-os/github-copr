Name:           gnome49-el10-compat
Version:        1.2.5
Release:        1%{?dist}
Summary:        GNOME 49 Compatibility workarounds for EL10

License:        MIT
Source0:        systemd-user.pam
Source1:        gdm-gnome49.te
Source2:        orca-autostart.desktop
Source3:        tuned-ppd-logging.te

BuildArch:      noarch
BuildRequires:  checkpolicy
BuildRequires:  policycoreutils
# SELinux policy backport for GDM userdb architecture support
Requires:       selinux-policy >= 43.3
Requires:       selinux-policy-targeted >= 43.3
Requires(post): policycoreutils
# Conflicts with systemd versions that have the Patch0254 regression.
Conflicts:      systemd < 256.5-1.el10

%description
This package provides configuration overrides to restore upstream behavior
for components that regress when using GNOME 49 on CentOS Stream 10.

Includes:
- systemd-user PAM override: fixes dynamic GDM greeter user authentication
- gdm-gnome49 SELinux module: allows xdm_t to create the userdb Varlink
  socket in /run/systemd/userdb/ and allows system services to connect to
  it (required for GDM 49 dynamic greeter user lookup under enforcing mode)
- orca-autostart.desktop override: suppresses unconditional Orca launch;
  gnome-session 49 does not evaluate AutostartCondition=GSettings.
  orca.service is now shipped by orca >= 49.6 directly.

%prep
# No prep needed.

%build
checkmodule -M -m -o gdm-gnome49.mod %{SOURCE1}
semodule_package -o gdm-gnome49.pp -m gdm-gnome49.mod

checkmodule -M -m -o tuned-ppd-logging.mod %{SOURCE3}
semodule_package -o tuned-ppd-logging.pp -m tuned-ppd-logging.mod

%install
mkdir -p %{buildroot}%{_sysconfdir}/pam.d
cp %{SOURCE0} %{buildroot}%{_sysconfdir}/pam.d/systemd-user
mkdir -p %{buildroot}%{_datadir}/selinux/packages
cp gdm-gnome49.pp %{buildroot}%{_datadir}/selinux/packages/
cp tuned-ppd-logging.pp %{buildroot}%{_datadir}/selinux/packages/

%post
semodule -X 300 -i \
    %{_datadir}/selinux/packages/gdm-gnome49.pp \
    %{_datadir}/selinux/packages/tuned-ppd-logging.pp &>/dev/null || :
# Relabel /var/home so useradd_t can access it. In reinstall/upgrade scenarios
# /var/home may have default_t or unlabeled_t from a previous deployment;
# file_contexts.subs_dist maps /var/home -> /home but the on-disk xattr is
# never updated unless we explicitly call restorecon here.
restorecon -RF /var/home 2>/dev/null || :
# Override orca autostart: gnome-session 49 does not evaluate AutostartCondition,
# so orca would launch unconditionally. Write Hidden=true without owning the file
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

%postun
if [ $1 -eq 0 ]; then
    semodule -r gdm-gnome49 tuned-ppd-logging &>/dev/null || :
fi

%files
%config(noreplace) %{_sysconfdir}/pam.d/systemd-user
%{_datadir}/selinux/packages/gdm-gnome49.pp
%{_datadir}/selinux/packages/tuned-ppd-logging.pp

%changelog
* Thu Apr 02 2026 James Reilly <jreilly1821@gmail.com> - 1.2.5-1
- %post: run restorecon -RF /var/home to fix default_t/unlabeled_t labeling
  in reinstall/upgrade scenarios where /var is not wiped. Fixes useradd
  exit 12 (E_HOMEDIR) during gnome-initial-setup (issues #16, #17).

* Tue Mar 25 2026 James <james@example.com> - 1.2.4-1
- Add tuned-ppd-logging SELinux module: EL10 base policy does not grant
  tuned_ppd_t access to var_log_t; this allows tuned-ppd to write its
  log to /var/log/tuned/tuned-ppd.log without AVC denials.

* Mon Mar 23 2026 James <james@example.com> - 1.2.3-1
- Drop orca.service: now shipped natively by orca >= 49.6, which is
  available in c10s-gnome-49 COPR. Avoids file conflict on upgrade.

* Mon Mar 23 2026 James <james@example.com> - 1.2.2-1
- Add %filetriggerin on orca-autostart.desktop to reliably write Hidden=true
  regardless of package install order. Fixes race in image builds where orca
  installs in a later transaction after our %post already ran.

* Sun Mar 23 2026 James <james@example.com> - 1.2.1-1
- Fix orca-autostart.desktop file conflict with orca package: write the
  Hidden=true override via %post scriptlet instead of shipping the file,
  since orca-48.9 owns /etc/xdg/autostart/orca-autostart.desktop.

* Sun Mar 23 2026 James <james@example.com> - 1.2.0-1
- Add Orca autostart suppression: gnome-session 49 does not evaluate
  AutostartCondition=GSettings, causing Orca to launch unconditionally.
  Ship Hidden=true override for orca-autostart.desktop and orca.service
  so gsd-a11y-settings can manage Orca properly.

* Fri Mar 20 2026 James <james@example.com> - 1.1.0-1
- Add gdm-gnome49 SELinux policy module for enforcing mode support.
  Allows xdm_t to create userdb socket; allows systemd_userdbd_t,
  policykit_t, auditd_t, setroubleshootd_t, systemd_user_runtimedir_t,
  init_t to connect to xdm_t userdb socket.

* Mon Mar 16 2026 James <james@example.com> - 1.0.1-1
- Add dependency on selinux-policy >= 43.1 for GDM userdb support.

* Sat Mar 14 2026 James <james@example.com> - 1.0.0-1
- Initial release with systemd-user PAM workaround for GNOME 49.
