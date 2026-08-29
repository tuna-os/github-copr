%global gettext_version 0.22
%global glib2_version 2.78.3
%global gtk4_version 4.15.2
%global libadwaita_version 1.6~beta
%global libsoup_version 3.0

Name:		gnome-online-accounts
Version:	3.58.1
# Explicit numeric Release, not Rawhide's %%autorelease: this package's
# Release convention was deliberately reset to N%%{?dist} in #521's GNOME 51
# mass-bump (same as most of src/gnome-51/*), and staying consistent with
# that sibling convention beats matching Rawhide on this one axis. Bumped to
# 2 here: this rebase folds in #580's %%files fix, which never got its own
# Release bump.
Release:	2%{?dist}
Summary:	Single sign-on framework for GNOME

# Sources are LGPL-2.0-or-later, icons are CC-BY-SA-4.0.
License:	LGPL-2.0-or-later AND CC-BY-SA-4.0
URL:		https://wiki.gnome.org/Projects/GnomeOnlineAccounts
Source0:	https://download.gnome.org/sources/%{name}/%{gnome_major_minor_version}/%{name}-%{version}.tar.xz

# gcc: not in Rawhide's BuildRequires list, kept here for a real EL10/
# hummingbird buildroot gap (see changelog, 2026-03-15) -- redundant at
# worst on a Fedora-Rawhide-based chroot, zero-cost safety margin.
BuildRequires:	gcc
BuildRequires:	pkgconfig(dbus-1)
BuildRequires:	pkgconfig(gcr-4)
BuildRequires:	pkgconfig(gio-2.0) >= %{glib2_version}
BuildRequires:	pkgconfig(glib-2.0) >= %{glib2_version}
BuildRequires:	pkgconfig(gobject-2.0) >= %{glib2_version}
BuildRequires:	pkgconfig(gobject-introspection-1.0)
BuildRequires:	pkgconfig(krb5)
BuildRequires:	pkgconfig(libadwaita-1) >= %{libadwaita_version}
BuildRequires:	pkgconfig(libkeyutils)
BuildRequires:	docbook-style-xsl
BuildRequires:	gettext >= %{gettext_version}
BuildRequires:	meson
BuildRequires:	vala
BuildRequires:	/usr/bin/desktop-file-validate
%if !0%{?flatpak}
BuildRequires:	/usr/bin/gi-docgen
BuildRequires:	/usr/bin/xsltproc
BuildRequires:	pkgconfig(gtk4) >= %{gtk4_version}
BuildRequires:	pkgconfig(json-glib-1.0)
BuildRequires:	pkgconfig(libsecret-1)
BuildRequires:	pkgconfig(libsoup-3.0) >= %{libsoup_version}
BuildRequires:	pkgconfig(rest-1.0)
BuildRequires:	pkgconfig(libxml-2.0)
%endif

Requires:	%{name}-libs%{?_isa} = %{version}-%{release}
%if !0%{?flatpak}
Requires:	gvfs-goa
Recommends:	evolution-ews-core
%endif

%description
GNOME Online Accounts provides interfaces so that applications and libraries
in GNOME can access the user's online accounts. It has providers for Google,
Nextcloud, Flickr, Foursquare, Microsoft Account, Microsoft Exchange, Fedora,
IMAP/SMTP and Kerberos.

%package libs
Summary:	Libraries for %{name}

Requires:	glib2%{?_isa} >= %{glib2_version}
%if !0%{?flatpak}
Requires:	gtk4%{?_isa} >= %{gtk4_version}
Requires:	libadwaita%{?_isa} >= %{libadwaita_version}
Requires:	libsoup3%{?_isa} >= %{libsoup_version}
%endif

%description libs
This package contains the libraries for GNOME Online Accounts. It is separated
from the main package to avoid build-time dependency loops.

%package devel
Summary:	Development files for %{name}
Requires:	%{name}-libs%{?_isa} = %{version}-%{release}

%description devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%prep
%autosetup -p1

%build
%meson \
%if 0%{?flatpak}
  -Dgoabackend=false \
  -Ddocumentation=false \
  -Dman=false \
%else
  -Dfedora=true \
%endif
  %{nil}

%meson_build

%install
%meson_install

%find_lang %{name}

%check
%if !0%{?flatpak}
desktop-file-validate %{buildroot}/%{_datadir}/applications/org.gnome.OnlineAccounts.OAuth2.desktop
%endif

%files -f %{name}.lang
%license COPYING
%doc NEWS README.md
%if !0%{?flatpak}
%{_mandir}/man8/goa-daemon.8*
%{_prefix}/libexec/goa-daemon
%{_prefix}/libexec/goa-identity-service
%{_prefix}/libexec/goa-oauth2-handler
%{_datadir}/applications/org.gnome.OnlineAccounts.OAuth2.desktop
%{_datadir}/dbus-1/services/org.gnome.OnlineAccounts.service
%{_datadir}/dbus-1/services/org.gnome.Identity.service
#%%{_datadir}/glib-2.0/schemas/org.gnome.online-accounts.gschema.xml
%{_datadir}/icons/hicolor/*/apps/goa-*.svg
%endif
# #580: data/meson.build and data/icons/meson.build install this desktop
# file and symbolic icon with no surrounding `if enable_goabackend` at all
# (only the goa-account-* icon variants are gated), so they exist even in a
# flatpak build with goabackend disabled -- hence unconditional here, same
# as Rawhide's current spec, rather than nested inside the block above like
# our original #580 fix had them.
%{_datadir}/applications/org.gnome.goa-daemon.desktop
%{_datadir}/icons/hicolor/*/apps/org.gnome.goa-daemon-symbolic.svg

%files libs
%dir %{_libdir}/girepository-1.0
%{_libdir}/girepository-1.0/Goa-1.0.typelib
%{_libdir}/libgoa-1.0.so.0
%{_libdir}/libgoa-1.0.so.0.0.0
%if !0%{?flatpak}
%{_libdir}/libgoa-backend-1.0.so.2
%{_libdir}/libgoa-backend-1.0.so.2.0.0
%dir %{_libdir}/goa-1.0
%endif

%files devel
%{_includedir}/goa-1.0/
%{_libdir}/libgoa-1.0.so
%dir %{_datadir}/gir-1.0
%{_datadir}/gir-1.0/Goa-1.0.gir
%{_libdir}/pkgconfig/goa-1.0.pc
%if !0%{?flatpak}
%{_libdir}/libgoa-backend-1.0.so
%{_libdir}/pkgconfig/goa-backend-1.0.pc
%{_pkgdocdir}/Goa-1.0/
%endif
%{_libdir}/goa-1.0/include
%{_datadir}/vala/

%changelog
* Fri Aug 28 2026 James Reilly <jreilly1821@gmail.com> - 3.58.1-2
- Re-fork against Fedora Rawhide's current spec: Source0 now uses
  %%{gnome_major_minor_version} instead of a hardcoded "3.58" path segment,
  %%prep switched to %%autosetup -p1, and the flatpak %%build variant picks
  up Rawhide's -Ddocumentation=false -Dman=false (not exercised by this
  pipeline, kept for parity).
- Moved #580's desktop-file/symbolic-icon %%files fix out of the
  non-flatpak-only block to match Rawhide's now-unconditional placement --
  Rawhide independently hit and fixed the same "Installed (but unpackaged)
  file(s)" gap, and its fix is strictly broader (also correct for a
  goabackend=false flatpak build, which ours was not).
- Release bumped to -2: #580's %%files fix landed without ever bumping
  Release off of -1.

* Tue Aug 25 2026 James Reilly <jreilly1821@gmail.com> - 3.58.1-1
- Update to 3.58.1 (GNOME 51 beta cycle)

* Sun Mar 15 2026 Conductor <james@conductor.local> - 3.56.4-1
- Add gcc BuildRequires for EL10 buildroot compatibility
