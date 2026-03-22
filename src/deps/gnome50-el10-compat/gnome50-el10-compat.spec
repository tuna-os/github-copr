Name:           gnome50-el10-compat
Version:        1.2.0
Release:        1%{?dist}
Summary:        GNOME 50 Compatibility workarounds for EL10

License:        MIT
Source0:        systemd-user.pam
Source1:        gdm-gnome50.te
Source2:        gdm-userdb-connect.te
Source3:        orca-autostart.desktop
Source4:        orca.service

BuildArch:      noarch
BuildRequires:  checkpolicy
BuildRequires:  policycoreutils

Requires:       selinux-policy >= 43.1
Requires(post): policycoreutils
Requires(preun): policycoreutils

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
  GNOME 50 expects Orca to be managed via systemd (orca.service).
- An orca.service systemd user unit (from upstream GNOME) so gsd-a11y-settings
  can enable/disable Orca correctly on EL10 where orca doesn't ship this unit.

%prep
cp %{SOURCE1} gdm-gnome50.te
cp %{SOURCE2} gdm-userdb-connect.te

%build
checkmodule -M -m -o gdm-gnome50.mod gdm-gnome50.te
semodule_package -o gdm-gnome50.pp -m gdm-gnome50.mod

checkmodule -M -m -o gdm-userdb-connect.mod gdm-userdb-connect.te
semodule_package -o gdm-userdb-connect.pp -m gdm-userdb-connect.mod

%install
mkdir -p %{buildroot}%{_sysconfdir}/pam.d
cp %{SOURCE0} %{buildroot}%{_sysconfdir}/pam.d/systemd-user

install -d %{buildroot}%{_datadir}/selinux/packages
install -m 644 gdm-gnome50.pp %{buildroot}%{_datadir}/selinux/packages/
install -m 644 gdm-userdb-connect.pp %{buildroot}%{_datadir}/selinux/packages/

# Suppress unconditional Orca autostart (GNOME 50 dropped AutostartCondition evaluation)
install -d %{buildroot}%{_sysconfdir}/xdg/autostart
install -m 644 %{SOURCE3} %{buildroot}%{_sysconfdir}/xdg/autostart/orca-autostart.desktop

# Ship orca.service so gsd-a11y-settings can enable/disable Orca via systemd
install -d %{buildroot}%{_userunitdir}
install -m 644 %{SOURCE4} %{buildroot}%{_userunitdir}/orca.service

%post
if [ $1 -ge 1 ]; then
    %{_sbindir}/semodule -X 300 -i \
        %{_datadir}/selinux/packages/gdm-gnome50.pp \
        %{_datadir}/selinux/packages/gdm-userdb-connect.pp 2>/dev/null || :
fi

%preun
if [ $1 -eq 0 ]; then
    %{_sbindir}/semodule -X 300 -r gdm-gnome50 gdm-userdb-connect 2>/dev/null || :
fi

%files
%config(noreplace) %{_sysconfdir}/pam.d/systemd-user
%{_datadir}/selinux/packages/gdm-gnome50.pp
%{_datadir}/selinux/packages/gdm-userdb-connect.pp
%{_sysconfdir}/xdg/autostart/orca-autostart.desktop
%{_userunitdir}/orca.service

%changelog
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
