Name: mousepad
Version: 0.7.0
Release: 1%{?dist}
Summary: Simple text editor for the Xfce desktop environment
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/apps/mousepad
Source0: https://archive.xfce.org/src/apps/mousepad/0.7/mousepad-%{version}.tar.xz

# The el10 buildroot packages mousepad's shared lib and binary; keep the
# debug source file out of the buildroot so %files stays closed (the el10
# mock chain does not run find-debuginfo for meson .so builds here).
%global _enable_debug_packages 0

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
%{_libdir}/libmousepad.so*
%{_datadir}/applications/*.desktop
%{_datadir}/metainfo/*.xml
%{_datadir}/icons/hicolor/*/apps/org.xfce.mousepad*
%{_datadir}/glib-2.0/schemas/*.xml
%{_datadir}/polkit-1/actions/org.xfce.mousepad.policy

%changelog
* Sun Jul 26 2026 TunaOS Bot <bot@tunaos.org> - 0.7.0-1
- Initial XFCE Wayland package for TunaOS EL10
