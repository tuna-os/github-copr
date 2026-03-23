%global userunitdir %{_prefix}/lib/systemd/user

Name:           gnome49-el10-compat
Version:        1.2.0
Release:        1%{?dist}
Summary:        GNOME 49 Compatibility workarounds for EL10

License:        MIT
Source0:        systemd-user.pam
Source1:        gdm-gnome49.te
Source2:        orca-autostart.desktop
Source3:        orca.service

BuildArch:      noarch
BuildRequires:  checkpolicy
BuildRequires:  policycoreutils
# SELinux policy backport for GDM userdb architecture support
Requires:       selinux-policy >= 43.1
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
  gnome-session 49 does not evaluate AutostartCondition=GSettings
- orca.service: allows gsd-a11y-settings to manage Orca via systemd

%prep
# No prep needed.

%build
checkmodule -M -m -o gdm-gnome49.mod %{SOURCE1}
semodule_package -o gdm-gnome49.pp -m gdm-gnome49.mod

%install
mkdir -p %{buildroot}%{_sysconfdir}/pam.d
cp %{SOURCE0} %{buildroot}%{_sysconfdir}/pam.d/systemd-user
mkdir -p %{buildroot}%{_datadir}/selinux/packages
cp gdm-gnome49.pp %{buildroot}%{_datadir}/selinux/packages/
mkdir -p %{buildroot}%{_sysconfdir}/xdg/autostart
cp %{SOURCE2} %{buildroot}%{_sysconfdir}/xdg/autostart/orca-autostart.desktop
mkdir -p %{buildroot}%{userunitdir}
cp %{SOURCE3} %{buildroot}%{userunitdir}/orca.service

%post
semodule -X 300 -i %{_datadir}/selinux/packages/gdm-gnome49.pp &>/dev/null || :

%postun
if [ $1 -eq 0 ]; then
    semodule -r gdm-gnome49 &>/dev/null || :
fi

%files
%config(noreplace) %{_sysconfdir}/pam.d/systemd-user
%{_datadir}/selinux/packages/gdm-gnome49.pp
%{_sysconfdir}/xdg/autostart/orca-autostart.desktop
%{userunitdir}/orca.service

%changelog
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
