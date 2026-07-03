Name:           gtk-layer-shell
Version:        0.9.0
Release:        1%{?dist}
Summary:        GTK3 Wayland layer shell library for desktop components

License:        MIT
URL:            https://github.com/wmww/gtk-layer-shell
Source0:        https://github.com/wmww/gtk-layer-shell/archive/v0.9.0/gtk-layer-shell-0.9.0.tar.gz

BuildRequires: gcc
BuildRequires:  gtk3-devel
BuildRequires:  wayland-devel
BuildRequires:  wayland-protocols-devel
BuildRequires:  gobject-introspection-devel
BuildRequires:  vala
BuildRequires:  meson
BuildRequires:  ninja-build

%description
A library to write GTK applications that use the Wayland layer shell protocol.
Layer shell is a Wayland protocol for desktop components such as panels and
notification daemons. It allows windows to be anchored to the edges or corners
of the screen and placed above or below other windows.

%package devel
Summary: Development files for %{name}
Requires: %{name}%{?_isa} = %{version}-%{release}
Requires: gtk3-devel%{?_isa}

%description devel
Headers, GObject-Introspection typelib, and Vala bindings for building
against gtk-layer-shell.

%prep
%autosetup -n gtk-layer-shell-%{version}

%build
%meson
%meson_build

%install
%meson_install

%post -p /sbin/ldconfig
%postun -p /sbin/ldconfig

%files
%license LICENSE_GPL.txt LICENSE_LGPL.txt LICENSE_MIT.txt
%{_libdir}/libgtk-layer-shell.so.*

%files devel
%{_includedir}/gtk-layer-shell/gtk-layer-shell.h
%{_libdir}/libgtk-layer-shell.so
%{_libdir}/pkgconfig/gtk-layer-shell-0.pc
%{_libdir}/girepository-1.0/GtkLayerShell-0.1.typelib
%{_datadir}/gir-1.0/GtkLayerShell-0.1.gir
%{_datadir}/vala/vapi/gtk-layer-shell-0.deps
%{_datadir}/vala/vapi/gtk-layer-shell-0.vapi

%changelog
* Thu Jul 03 2026 TunaOS Bot <bot@tunaos.org> - 0.9.0-1
- Initial XFCE Wayland package for TunaOS EL10
