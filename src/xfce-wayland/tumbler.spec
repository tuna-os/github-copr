Name: tumbler
Version: 4.21.1
Release: 1%{?dist}
Summary: D-Bus thumbnailing service for Xfce
License: GPL-2.0-or-later AND LGPL-2.1-or-later
URL: https://gitlab.xfce.org/xfce/tumbler
Source0: https://gitlab.xfce.org/xfce/tumbler/-/archive/tumbler-4.21.1/tumbler-4.21.1.tar.gz
BuildRequires: gtk3-devel, glib2-devel, dbus-devel, freetype-devel, libjpeg-turbo-devel, libpng-devel, libgsf-devel, intltool, gettext, meson, ninja-build
%description
D-Bus thumbnailing service for the Xfce desktop environment. Provides
thumbnail generation for various file types used by file managers.
%prep
%autosetup -n tumbler-%{version}
%build
%meson
%meson_build
%install
%meson_install
%files
%license COPYING
%{_bindir}/tumblerd
%{_libdir}/tumbler-1/
%{_datadir}/dbus-1/services/*.service
%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 4.21.1-1
- Initial XFCE Wayland package for TunaOS EL10
