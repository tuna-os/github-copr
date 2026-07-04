Name: xfce4-terminal
Version: 1.2.0
Release: 1%{?dist}
Summary: Terminal emulator for the Xfce desktop environment
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/apps/xfce4-terminal
Source0: https://archive.xfce.org/src/apps/xfce4-terminal/1.2/xfce4-terminal-%{version}.tar.xz

BuildRequires: gcc
BuildRequires: gtk3-devel
BuildRequires: libxfce4ui-devel
BuildRequires: libxfce4util-devel
BuildRequires: vte291-devel
BuildRequires: gtk-layer-shell-devel
BuildRequires: libxslt
# xsltproc runs with --nonet; needs the docbook manpages stylesheet
# available locally via an XML catalog rewrite (same fix thunar needed).
BuildRequires: docbook-style-xsl
BuildRequires: libutempter-devel
BuildRequires: intltool
BuildRequires: gettext
BuildRequires: meson
BuildRequires: ninja-build

Requires: gtk-layer-shell

%description
Terminal emulator for the Xfce desktop environment with Wayland support
via gtk-layer-shell.

%prep
%autosetup -n xfce4-terminal-%{version}

%build
%meson -Dwayland=enabled
%meson_build

%install
%meson_install
%find_lang %{name}

%files -f %{name}.lang
%license COPYING
%{_bindir}/xfce4-terminal
%{_datadir}/applications/*.desktop
%{_datadir}/xfce4/terminal/colorschemes/
%{_datadir}/man/man1/*
%{_datadir}/icons/hicolor/*/apps/org.xfce.terminal*

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 1.2.0-1
- Initial XFCE Wayland package for TunaOS EL10
