Name: xfce4-cpugraph-plugin
Version: 1.2.11
Release: 1%{?dist}
Summary: CPU frequency monitor plugin for the Xfce panel
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/panel-plugins/xfce4-cpugraph-plugin
Source0: https://archive.xfce.org/src/panel-plugins/xfce4-cpugraph-plugin/1.2/xfce4-cpugraph-plugin-1.2.11.tar.bz2
BuildRequires: gtk3-devel, libxfce4ui-devel, libxfce4util-devel, xfce4-panel-devel, intltool, gettext, autoconf, automake, libtool
Requires: xfce4-panel
%description
CPU frequency monitor plugin for the Xfce panel. Provides a graphical
display of CPU usage over time.
%prep
%autosetup -n xfce4-cpugraph-plugin-%{version}
%build
NOCONFIGURE=1 ./autogen.sh
%configure --disable-gtk-doc
%make_build
%install
%make_install
%files
%license COPYING
%{_libdir}/xfce4/panel/plugins/libcpugraph.so
%{_datadir}/xfce4/panel/plugins/*.desktop
%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 1.2.10-1
- Initial XFCE Wayland package for TunaOS EL10
