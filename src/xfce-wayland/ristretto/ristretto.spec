Name: ristretto
Version: 0.14.0
Release: 1%{?dist}
Summary: Image viewer for the Xfce desktop environment
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/apps/ristretto
Source0: https://archive.xfce.org/src/apps/ristretto/0.14/ristretto-%{version}.tar.xz

BuildRequires: gcc
BuildRequires: gtk3-devel
BuildRequires: cairo-devel
BuildRequires: libexif-devel
BuildRequires: libxfce4ui-devel
BuildRequires: libxfce4util-devel
BuildRequires: xfconf-devel
BuildRequires: intltool
BuildRequires: gettext
BuildRequires: meson
BuildRequires: ninja-build

%description
Image viewer for the Xfce desktop environment with Wayland support.

%prep
%autosetup -n ristretto-%{version}

%build
%meson
%meson_build

%install
%meson_install
%find_lang %{name}

%files -f %{name}.lang
%license COPYING
%{_bindir}/ristretto
%{_datadir}/applications/*.desktop
%{_datadir}/metainfo/*.xml
%{_datadir}/icons/hicolor/*/apps/org.xfce.ristretto*

%changelog
* Sat Jul 26 2026 TunaOS Bot <bot@tunaos.org> - 0.14.0-1
- Initial XFCE Wayland package for TunaOS EL10
