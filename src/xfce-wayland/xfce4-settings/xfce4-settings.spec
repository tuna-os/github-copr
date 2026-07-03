%global commit 8e9f1a16f189a27b6d36c444d86a8b220ee90062
%global shortcommit %(c=%{commit}; echo ${c:0:7})
Name:           xfce4-settings
Version:        4.21.0
Release:        1%{?dist}
Summary:        Settings manager for the Xfce desktop environment

License:        GPL-2.0-or-later
URL:            https://gitlab.xfce.org/xfce/xfce4-settings
Source0:        https://gitlab.xfce.org/xfce/xfce4-settings/-/archive/xfce4-settings-4.21.0/xfce4-settings-4.21.0.tar.gz

BuildRequires:  gtk3-devel
BuildRequires:  libxfce4ui-devel
BuildRequires:  libxfce4util-devel
BuildRequires:  xfconf-devel
BuildRequires:  colord-devel
BuildRequires:  upower-devel
BuildRequires:  intltool
BuildRequires:  gettext
BuildRequires:  meson
BuildRequires:  ninja-build

Requires:       xfconf

%description
Xfce4-settings provides the graphical settings manager for the Xfce desktop
environment. It includes dialogs for configuring accessibility, appearance,
display, keyboard, mouse, MIME types, and more. The settings daemon
xfsettingsd applies preferences at session startup.

%prep
%autosetup -n xfce4-settings-%{commit}

%build
%meson
%meson_build

%install
%meson_install

%files
%license COPYING
%{_bindir}/xfce4-settings-manager
%{_bindir}/xfce4-settings-editor
%{_bindir}/xfce4-accessibility-settings
%{_bindir}/xfce4-appearance-settings
%{_bindir}/xfce4-display-settings
%{_bindir}/xfce4-keyboard-settings
%{_bindir}/xfce4-mime-settings
%{_bindir}/xfce4-mouse-settings
%{_libexecdir}/xfce4/xfsettingsd
%{_datadir}/applications/*.desktop

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 4.21.0-1
- Initial XFCE Wayland package for TunaOS EL10
