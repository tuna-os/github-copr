Name: xfce4-taskmanager
Version: 1.5.8
Release: 1%{?dist}
Summary: Task manager for the Xfce desktop environment (Wayland)
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/apps/xfce4-taskmanager
Source0: https://archive.xfce.org/src/apps/xfce4-taskmanager/1.5/xfce4-taskmanager-%{version}.tar.bz2

BuildRequires: gcc
BuildRequires: make
BuildRequires: gtk3-devel
BuildRequires: libxfce4ui-devel
BuildRequires: libxfce4util-devel
BuildRequires: libXmu-devel
BuildRequires: intltool
BuildRequires: gettext

%description
Task manager for the Xfce desktop environment. This version (1.5.8) predates
the meson-based build system used elsewhere in this stack — it's autotools
(configure/make). X11 (libx11) support is optional and auto-detected by
configure, but xmu is a hard requirement regardless.

%prep
%autosetup -n xfce4-taskmanager-%{version}

%build
# The source calls xfce_textdomain() directly but only links against
# libxfce4ui-2 (whose .pc lists libxfce4util as Requires.private, so it
# doesn't propagate into --libs) — upstream's LDADD omits libxfce4util
# explicitly. Force it in rather than patch Makefile.am.
%configure LIBS=-lxfce4util
%make_build

%install
%make_install
%find_lang %{name}

%files -f %{name}.lang
%license COPYING
%{_bindir}/xfce4-taskmanager
%{_datadir}/applications/*.desktop
%{_datadir}/icons/hicolor/*/apps/org.xfce.taskmanager.*
%{_datadir}/icons/hicolor/scalable/actions/*.svg

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 1.5.8-1
- Initial XFCE Wayland package for TunaOS EL10
