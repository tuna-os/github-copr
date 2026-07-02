Name: xfce4-netload-plugin
Version: 1.4.2
Release: 1%{?dist}
Summary: Network load monitor plugin for the Xfce panel
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/panel-plugins/xfce4-netload-plugin
Source0: https://gitlab.xfce.org/panel-plugins/xfce4-netload-plugin/-/archive/xfce4-netload-plugin-1.4.2/xfce4-netload-plugin-1.4.2.tar.gz
BuildRequires: gtk3-devel, libxfce4ui-devel, libxfce4util-devel, xfce4-panel-devel, intltool, gettext, autoconf, automake, libtool
Requires: xfce4-panel
%description
Network load monitor plugin for the Xfce panel. Displays real-time
network traffic statistics for configured network interfaces.
%prep
%autosetup -n xfce4-netload-plugin-%{version}
%build
NOCONFIGURE=1 ./autogen.sh
%configure --disable-gtk-doc
%make_build
%install
%make_install
%files
%license COPYING
%{_libdir}/xfce4/panel/plugins/libnetload.so
%{_datadir}/xfce4/panel/plugins/*.desktop
%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 1.4.2-1
- Initial XFCE Wayland package for TunaOS EL10
