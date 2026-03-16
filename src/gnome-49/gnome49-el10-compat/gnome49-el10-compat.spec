Name:           gnome49-el10-compat
Version:        1.0.1
Release:        1%{?dist}
Summary:        GNOME 49 Compatibility workarounds for EL10

License:        MIT
Source0:        systemd-user.pam

BuildArch:      noarch
# SELinux policy backport for GDM userdb architecture support
Requires:       selinux-policy >= 43.1
# Conflicts with systemd versions that have the Patch0254 regression.
Conflicts:      systemd < 256.5-1.el10

%description
This package provides configuration overrides to restore upstream behavior
for components that regress when using GNOME 49 on CentOS Stream 10.
Currently, it fixes the systemd-user PAM service to support dynamic GDM
greeter users and ensures the necessary SELinux policy is present.

%prep
# No prep needed for just a config file.

%build
# No build needed.

%install
mkdir -p %{buildroot}%{_sysconfdir}/pam.d
cp %{SOURCE0} %{buildroot}%{_sysconfdir}/pam.d/systemd-user

%files
%config(noreplace) %{_sysconfdir}/pam.d/systemd-user

%changelog
* Mon Mar 16 2026 James <james@example.com> - 1.0.1-1
- Add dependency on selinux-policy >= 43.1 for GDM userdb support.

* Sat Mar 14 2026 James <james@example.com> - 1.0.0-1
- Initial release with systemd-user PAM workaround for GNOME 49.
