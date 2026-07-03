Name: xfce4-pulseaudio-plugin
Version: 0.4.10
Release: 1%{?dist}
Summary: PulseAudio panel plugin for the Xfce desktop (Wayland)
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/panel-plugins/xfce4-pulseaudio-plugin
Source0: https://gitlab.xfce.org/panel-plugins/xfce4-pulseaudio-plugin/-/archive/xfce4-pulseaudio-plugin-0.4.10/xfce4-pulseaudio-plugin-0.4.10.tar.gz

BuildRequires: gtk3-devel
BuildRequires: libxfce4ui-devel
BuildRequires: libxfce4util-devel
BuildRequires: xfce4-panel-devel
BuildRequires: libxfce4windowing-devel
BuildRequires: pulseaudio-libs-devel
BuildRequires: libnotify-devel
BuildRequires: intltool
BuildRequires: gettext
BuildRequires: meson
BuildRequires: ninja-build

Requires: xfce4-panel
Requires: pulseaudio

%description
PulseAudio volume control panel plugin for the Xfce desktop environment
with Wayland support.

%prep
%autosetup -n xfce4-pulseaudio-plugin-%{version}

%build
%meson
%meson_build

%install
%meson_install

%files
%license COPYING
%{_libdir}/xfce4/panel/plugins/libpulseaudio.so
%{_datadir}/xfce4/panel/plugins/*.desktop

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 0.4.10-1
- Initial XFCE Wayland package for TunaOS EL10
