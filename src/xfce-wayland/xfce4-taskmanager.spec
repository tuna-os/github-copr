Name: xfce4-taskmanager
Version: 1.5.8
Release: 1%{?dist}
Summary: Task manager for the Xfce desktop environment (Wayland)
License: GPL-2.0-or-later
URL: https://gitlab.xfce.org/apps/xfce4-taskmanager
Source0: https://gitlab.xfce.org/apps/xfce4-taskmanager/-/archive/xfce4-taskmanager-1.5.8/xfce4-taskmanager-1.5.8.tar.gz

BuildRequires: gtk3-devel
BuildRequires: libxfce4ui-devel
BuildRequires: libxfce4util-devel
BuildRequires: intltool
BuildRequires: gettext
BuildRequires: meson
BuildRequires: ninja-build

%description
Task manager for the Xfce desktop environment with Wayland-only build
(X11 disabled).

%prep
%autosetup -n xfce4-taskmanager-%{version}

%build
%meson -Dx11=disabled
%meson_build

%install
%meson_install

%files
%license COPYING
%{_bindir}/xfce4-taskmanager
%{_datadir}/applications/*.desktop

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 1.5.8-1
- Initial XFCE Wayland package for TunaOS EL10
