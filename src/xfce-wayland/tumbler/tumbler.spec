%global commit 821c7fe0a4c99c424f688116143e3d5757b35e5f
%global shortcommit %(c=%{commit}; echo ${c:0:7})
Name: tumbler
Version: 4.21.1
Release: 1%{?dist}
Summary: D-Bus thumbnailing service for Xfce
License: GPL-2.0-or-later AND LGPL-2.1-or-later
URL: https://gitlab.xfce.org/xfce/tumbler
Source0: https://gitlab.xfce.org/xfce/tumbler/-/archive/%{commit}/tumbler-%{commit}.tar.gz
BuildRequires: gcc, gtk3-devel, glib2-devel, dbus-devel, freetype-devel, libjpeg-turbo-devel, libpng-devel, libgsf-devel, intltool, gettext, meson, ninja-build
BuildRequires: libxfce4util-devel, poppler-glib-devel
%description
D-Bus thumbnailing service for the Xfce desktop environment. Provides
thumbnail generation for various file types used by file managers.
%prep
%autosetup -n tumbler-%{commit}
%build
# meson's --auto-features=enabled forces every "auto" thumbnailer plugin on;
# disable the ones needing heavier/niche deps we don't otherwise want in the
# base stack (video, ebook, camera-raw), keep the common image/doc formats.
%meson -Dcover-thumbnailer=disabled -Dffmpeg-thumbnailer=disabled -Dgepub-thumbnailer=disabled -Dgst-thumbnailer=disabled -Draw-thumbnailer=disabled
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
