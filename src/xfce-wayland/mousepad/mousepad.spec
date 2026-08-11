Name: mousepad
Version: 0.7.0
Release: 1%{?dist}
Summary: Simple text editor for the Xfce desktop environment
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/apps/mousepad
Source0: https://archive.xfce.org/src/apps/mousepad/0.7/mousepad-%{version}.tar.xz

BuildRequires: gcc
BuildRequires: gtk3-devel
BuildRequires: gtksourceview4-devel
BuildRequires: polkit-devel
BuildRequires: gspell-devel
BuildRequires: libxfce4ui-devel
BuildRequires: libxfce4util-devel
BuildRequires: intltool
BuildRequires: gettext
BuildRequires: meson
BuildRequires: ninja-build

%description
Simple text editor for the Xfce desktop environment with Wayland support.

%prep
%autosetup -n mousepad-%{version}

%build
%meson
%meson_build

%install
%meson_install
%find_lang %{name}

%files -f %{name}.lang
%license COPYING
%{_bindir}/mousepad
%{_libdir}/mousepad/plugins/
%{_datadir}/applications/*.desktop
%{_datadir}/metainfo/*.xml
%{_datadir}/icons/hicolor/*/apps/org.xfce.mousepad*

%changelog
* Sat Jul 26 2026 TunaOS Bot <bot@tunaos.org> - 0.7.0-1
- Initial XFCE Wayland package for TunaOS EL10
