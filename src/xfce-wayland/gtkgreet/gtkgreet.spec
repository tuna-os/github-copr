Name:           gtkgreet
Version:        0.8
Release:        1%{?dist}
Summary:        GTK-based graphical greeter for greetd

License:        GPL-3.0-only
URL:            https://git.sr.ht/~kennylevinsen/gtkgreet
Source0:        https://git.sr.ht/~kennylevinsen/gtkgreet/archive/%{version}.tar.gz#/%{name}-%{version}.tar.gz

BuildRequires:  gcc
BuildRequires:  gtk3-devel
BuildRequires:  json-c-devel
BuildRequires:  gtk-layer-shell-devel
BuildRequires:  gettext
BuildRequires:  scdoc
BuildRequires:  meson
BuildRequires:  ninja-build

# gtkgreet is only a greetd greeter — it is useless without the daemon.
Requires:       greetd
# gtkgreet draws no background and cannot own a VT; it must be hosted by a
# kiosk compositor. cage is the upstream-recommended host and is in EL10.
Requires:       cage

%description
gtkgreet is a GTK3 graphical greeter for the greetd login daemon. It presents
a themable login window and lets the user pick which session to start, reading
the available sessions from the standard wayland-sessions/xsessions desktop
files.

Because gtkgreet is a plain Wayland client it must be run inside a compositor;
the usual invocation is "cage -s -- gtkgreet". Being GTK3, it honours the same
GTK theme, icon theme, cursor theme and font settings as a GTK3 desktop such
as XFCE, which is why TunaOS uses it as the XFCE greeter — the login screen
and the session it launches share one look.

%prep
%autosetup -n %{name}-%{version}

%build
# Upstream sets werror=true in default_options; EL10's GCC emits warnings
# upstream's CI toolchain does not, which would turn a benign warning into a
# build failure. Build the released tarball with warnings non-fatal.
%meson -Dwerror=false -Dlayershell=enabled -Dman-pages=enabled
%meson_build

%install
%meson_install
%find_lang %{name}

%files -f %{name}.lang
%license LICENSE
%doc README.md
%{_bindir}/gtkgreet
%{_mandir}/man1/gtkgreet.1*

%changelog
* Sun Jul 19 2026 TunaOS Bot <bot@tunaos.org> - 0.8-1
- Initial package: greetd greeter for the XFCE Wayland session
