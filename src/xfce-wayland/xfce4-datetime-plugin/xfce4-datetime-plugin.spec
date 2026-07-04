%global commit 78c893245e8c291cd9ac3c7272933bd397432655
%global shortcommit %(c=%{commit}; echo ${c:0:7})
Name: xfce4-datetime-plugin
Version: 0.8.3
Release: 1%{?dist}
Summary: Date and time panel plugin for the Xfce panel
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/panel-plugins/xfce4-datetime-plugin
Source0: https://gitlab.xfce.org/panel-plugins/xfce4-datetime-plugin/-/archive/%{commit}/xfce4-datetime-plugin-%{commit}.tar.gz
# datetime-dialog.c includes the libxfce4panel/xfce-panel-plugin.h
# sub-header directly instead of the umbrella libxfce4panel.h — newer
# libxfce4panel enforces "only include the umbrella header" and errors out.
Patch0: 0001-fix-libxfce4panel-header-guard.patch
BuildRequires: xfce4-dev-tools
BuildRequires: autoconf automake libtool gettext-devel
BuildRequires: gtk3-devel, libxfce4ui-devel, libxfce4util-devel, xfce4-panel-devel, intltool, gettext, autoconf, automake, libtool
Requires: xfce4-panel
%description
Date and time panel plugin for the Xfce panel. Displays the current
date and time with configurable formats and a calendar popup.
%prep
%autosetup -n xfce4-datetime-plugin-%{commit} -p1
%build
NOCONFIGURE=1 ./autogen.sh
%configure --disable-gtk-doc
%make_build
%install
%make_install
%find_lang %{name}
%files -f %{name}.lang
%license COPYING
%{_libdir}/xfce4/panel/plugins/libdatetime.so
%{_datadir}/xfce4/panel/plugins/*.desktop
%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 0.8.3-1
- Initial XFCE Wayland package for TunaOS EL10
