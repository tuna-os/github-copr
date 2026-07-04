%global commit 1c491868ca45092b6816ea5a9272f2ae6d2d788a
%global shortcommit %(c=%{commit}; echo ${c:0:7})
Name:           xfdesktop
Version:        4.21.0
Release:        1%{?dist}
Summary:        Desktop manager for the Xfce desktop environment (Wayland)

License:        GPL-2.0-or-later
URL:            https://gitlab.xfce.org/xfce/xfdesktop
Source0: https://gitlab.xfce.org/xfce/xfdesktop/-/archive/%{commit}/xfdesktop-%{commit}.tar.gz

BuildRequires: gcc
BuildRequires:  gtk3-devel
BuildRequires:  libxfce4ui-devel
BuildRequires:  libxfce4util-devel
BuildRequires:  libxfce4windowing-devel
BuildRequires:  garcon-devel
BuildRequires:  xfconf-devel
BuildRequires:  thunar-devel
BuildRequires:  intltool
BuildRequires:  gettext
BuildRequires:  meson
BuildRequires:  ninja-build
BuildRequires:  libnotify-devel
BuildRequires:  libyaml-devel
BuildRequires:  gtk-layer-shell-devel

Requires:       libxfce4windowing

%description
Xfdesktop is the desktop manager for the Xfce desktop environment.
It handles drawing the desktop background, managing desktop icons,
and providing a right-click application menu. This build targets
Wayland compositors for use in TunaOS EL10.

%prep
%autosetup -n xfdesktop-%{commit}

%build
# Wayland-only build (matches this stack's convention elsewhere).
# video-backdrop is a plain boolean defaulting true (not gated by
# --auto-features=enabled) and needs gstreamer; disable it rather than
# add that whole dependency chain for an animated-wallpaper nice-to-have.
%meson -Dx11=disabled -Dvideo-backdrop=false
%meson_build

%install
%meson_install
%find_lang %{name}

%files -f %{name}.lang
%license COPYING
%{_bindir}/xfdesktop
%{_bindir}/xfdesktop-settings
%{_datadir}/applications/*.desktop
%{_datadir}/backgrounds/xfce/
%{_datadir}/icons/hicolor/*/apps/org.xfce.xfdesktop.*
%{_datadir}/pixmaps/xfce4_xicon*.png
%{_datadir}/pixmaps/xfdesktop/

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 4.21.0-1
- Initial XFCE Wayland package for TunaOS EL10
