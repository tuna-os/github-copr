Name:           libnotify
Version:        0.8.7
Release:        1%{?dist}
Summary:        Desktop notification library

# Built here because EL10 tops out below what GNOME 50 requires.
#
# gnome-settings-daemon 50.0's meson.build asks for libnotify >= 0.8.7 and
# fails hard when it is not there:
#
#   meson.build:107:16: ERROR: Dependency lookup for libnotify with method
#   'pkgconfig' failed: Invalid version, need 'libnotify' ['>= 0.8.7']
#   found '0.8.6'.
#
# Measured across every repository the el10 buildroot can reach, on BOTH
# arches (#480):
#
#   CS10 AppStream          0.8.3-5.el10
#   CS10 koji c10s-build    0.8.6-1.el10   <- what the build actually found
#   EPEL 10                 absent
#
# So the constraint is unsatisfiable from upstream and gnome-settings-daemon,
# gnome-control-center and gnome-initial-setup all fail without this.
#
# repo.tunaos.org/repo/10-x86_64 already serves a libnotify-0.8.7-1.el10, but
# it had no spec and no build-order entry anywhere in this repository — an
# artifact the factory could not reproduce, and one that reached neither
# buildroot. This recipe replaces that orphan with something rebuildable, and
# on both architectures rather than one.
#
# 0.8.7 rather than the newer 0.8.8 deliberately: it is the minimum that
# satisfies the requirement and it matches the version already published, so
# nothing installed churns.
License:        LGPL-2.1-or-later
URL:            https://gitlab.gnome.org/GNOME/libnotify
Source0:        https://download.gnome.org/sources/%{name}/0.8/%{name}-%{version}.tar.xz

BuildRequires:  meson
BuildRequires:  gcc
BuildRequires:  pkgconfig(gdk-pixbuf-2.0)
BuildRequires:  pkgconfig(glib-2.0)
BuildRequires:  pkgconfig(gio-2.0)
BuildRequires:  pkgconfig(gio-unix-2.0)
BuildRequires:  gobject-introspection-devel
# xsltproc plus the DocBook stylesheets, for the notify-send man page.
#
# docbook5-style-xsl, NOT docbook-style-xsl. meson.build:78 probes the
# NAMESPACED stylesheet through the local XML catalog:
#
#   run_command(xsltproc, '--nonet',
#     'http://docbook.sourceforge.net/release/xsl-ns/current/manpages/docbook.xsl')
#
# --nonet means that URI has to resolve offline, so the buildroot needs a
# package whose %%post registers a rewrite rule for it. On EL10:
#
#   docbook-style-xsl    xsl-stylesheets-1.79.2      non-namespaced, no xsl-ns rule
#   docbook5-style-xsl   xsl-ns-stylesheets-1.79.2   registers rewriteURI for
#                                                    .../release/xsl-ns/current
#
# EL10 has no docbook-style-xsl-ns (the Fedora name) and no docbook-xsl-ns
# (the Debian name the error message suggests) at all; docbook5-style-xsl is
# the namespaced set under a different name. Building with docbook-style-xsl
# fails at configure time with:
#
#   meson.build:78:4: ERROR: Problem encountered: DocBook stylesheet for
#   generating man pages not found, you need to install docbook-xsl-ns or
#   similar package.
BuildRequires:  libxslt
BuildRequires:  docbook5-style-xsl

%description
libnotify sends desktop notifications to a notification daemon, as defined in
the Desktop Notifications spec. These notifications inform the user of an
event or display some form of information without disturbing the user.

%package devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description devel
This package contains the pkg-config file, development headers and
introspection data for %{name}.

%prep
%autosetup -n %{name}-%{version}

%build
# -Dtests=false is load-bearing, not tidiness. libnotify's meson.build makes
# its gtk4 dependency conditional on the tests option:
#
#   gtk_dep = dependency('gtk4', version: '>= 4.0', required: get_option('tests'))
#
# gtk4 is built by THIS chain, three tiers after this one (tier 10 vs tier 13
# for gnome-settings-daemon, with gtk-core at 10). Leaving tests enabled would
# make a tier-10 package build-depend on a tier-10 sibling, which the tier
# model cannot express and which would either deadlock the order or resolve
# against whatever stale gtk4 happened to be installed.
meson setup _build \
    --buildtype=plain \
    --prefix=%{_prefix} \
    --libdir=%{_libdir} \
    --libexecdir=%{_libexecdir} \
    --includedir=%{_includedir} \
    --datadir=%{_datadir} \
    --mandir=%{_mandir} \
    --wrap-mode=nodownload \
    -Dtests=false \
    -Dintrospection=enabled \
    -Dman=true
ninja -C _build -j%{_smp_build_ncpus}

%install
DESTDIR=%{buildroot} ninja -C _build install

%files
%license COPYING
%doc AUTHORS NEWS README.md
%{_bindir}/notify-send
%{_libdir}/libnotify.so.4
%{_libdir}/libnotify.so.4.*
%{_libdir}/girepository-1.0/Notify-0.7.typelib
%{_mandir}/man1/notify-send.1*

%files devel
%{_includedir}/libnotify/
%{_libdir}/libnotify.so
%{_libdir}/pkgconfig/libnotify.pc
%{_datadir}/gir-1.0/Notify-0.7.gir

%changelog
* Sat Aug 22 2026 TunaOS Package Factory <packages@tunaos.org> - 0.8.7-1
- Build libnotify 0.8.7 for EL10, which ships only 0.8.6 (#480)
- Require docbook5-style-xsl; docbook-style-xsl is the non-namespaced set and
  does not register the xsl-ns catalog rewrite meson.build:78 probes for
