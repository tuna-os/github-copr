Name: xfce4-genmon-plugin
Version: 4.2.1
Release: 1%{?dist}
Summary: Generic monitor panel plugin for the Xfce panel
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/panel-plugins/xfce4-genmon-plugin
Source0: https://archive.xfce.org/src/panel-plugins/xfce4-genmon-plugin/4.2/xfce4-genmon-plugin-4.2.1.tar.bz2
BuildRequires: autoconf automake libtool gettext-devel
BuildRequires: gtk3-devel, libxfce4ui-devel, libxfce4util-devel, xfce4-panel-devel, intltool, gettext, autoconf, automake, libtool
Requires: xfce4-panel
%description
Generic monitor panel plugin for the Xfce panel. Executes a user-defined
command periodically and displays its output in the panel.
%prep
%autosetup -n xfce4-genmon-plugin-%{version}
# The dist tarball bundles a configure script generated against an
# older libtool than EL10 ships; its nm-output parsing predates current
# binutils and mis-detects (breaks with a bogus command in the symbol
# pipe). Regenerating against the system libtool fixes it.
%build
autoreconf -fi
%configure --disable-gtk-doc
%make_build
%install
%make_install
%files
%license COPYING
%{_libdir}/xfce4/panel/plugins/libgenmon.so
%{_datadir}/xfce4/panel/plugins/*.desktop
%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 4.2.0-1
- Initial XFCE Wayland package for TunaOS EL10
