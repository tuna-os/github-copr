# input-remapper for EL10 (#122, #126).
#
# Key/button remapping GUI and daemon.  Present on Fedora, absent from EL10
# (not in BaseOS, AppStream, CRB or EPEL 10) and AUR-only on Arch.
#
# USES ITS OWN INSTALLER, DELIBERATELY NOT pip:
#   Upstream's install/__main__.py documents why pip is wrong for this package:
#   pip fails to install data files to their system paths (udev rules, polkit
#   action, systemd unit, D-Bus policy) and puts them inside the Python module
#   tree instead.  The bundled installer places them correctly per distro.
#
#   install/module.py additionally resolves site-packages vs dist-packages per
#   distribution, which is what makes one spec work for EL10.

Name:           input-remapper
Version:        2.2.1
Release:        4%{?dist}
Summary:        Change the mapping of input device buttons

License:        GPL-3.0-or-later
URL:            https://github.com/sezanzeb/input-remapper
Source0:        https://github.com/sezanzeb/input-remapper/archive/refs/tags/%{version}.tar.gz#/input-remapper-%{version}.tar.gz

BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  gettext
# %%{_unitdir} and %%{_udevrulesdir} come from systemd-rpm-macros, which is
# not in the CentOS Stream 10 mock buildroot by default. Without it the
# macros expand to nothing and rpmbuild dies at %%files with 'File must
# begin with "/": %%{_unitdir}/input-remapper.service' -- the one failure
# in the 2026-08-30 weekly gnome50 chain (run 33303057118, 57 of 58 built).
BuildRequires:  systemd-rpm-macros
# The bundled installer shells out to pip and imports gi, even though this
# spec deliberately avoids pip as the INSTALL METHOD (see above).
# install/module.py's build_input_remapper_module() runs
#   python3 -m pip install . --target <buildroot>/.../site-packages --no-deps
# to place the Python package, and install/__main__.py imports gi while
# checking dependencies. Neither is in the mock buildroot by default, so
# %%install died at 'No module named pip' after logging 'Missing Python
# module: No module named gi' (gnome50-el10-x86_64, run 32418295773 — one of
# that chain's five failed packages).
#
# Requiring pip here is not a reversal of the no-pip decision above: pip is
# an implementation detail of upstream's installer, which is still what
# places the udev rules, polkit action, systemd unit and D-Bus policy.
BuildRequires:  python3-pip
BuildRequires:  python3-gobject
# For %%install's PIP_NO_BUILD_ISOLATION -- see the note there. With build
# isolation off, pip uses the PEP 517 backend from the buildroot instead of
# fetching one, so the backend has to BE in the buildroot. setuptools is
# already required above; wheel is the other half of what a setuptools
# backend expects to find.
BuildRequires:  python3-wheel

# python3-evdev is built alongside this package in this repository.
# All other runtime names were verified against CentOS Stream 10 repository
# metadata with EPEL enabled:
#   python3-dasbus, python3-gobject, python3-cairo, python3-psutil, gtk3 → AppStream
#   python3-packaging → BaseOS
#   python3-pydantic, gtksourceview4 → EPEL 10
Requires:       python3
Requires:       python3-evdev
Requires:       python3-dasbus
Requires:       python3-gobject
Requires:       python3-cairo
Requires:       python3-pydantic
Requires:       python3-packaging
Requires:       python3-psutil
Requires:       gtk3
Requires:       gtksourceview4

%description
GUI and daemon for remapping keyboard, mouse and gamepad buttons, including
the input-remapper service and its udev rules.

%prep
%autosetup -n input-remapper-%{version}

# install/module.py bakes the build's commit into installation_info.py via
# `subprocess.check_output(["git", "rev-parse", "HEAD"])`.  A release tarball
# is not a git checkout, so this fails.  Substitute the commit the 2.2.1 tag
# points at so the recorded value matches what a git build would produce.
sed -i 's|subprocess.check_output(.*rev-parse.*)|b"e9a87d13480c3b1dee654b296578a8f4e2cd31d6"|' install/module.py
grep -q 'git_call = b"e9a87d13480c3b1dee654b296578a8f4e2cd31d6"' install/module.py

%build
# Nothing to compile here.  Upstream's installer compiles translations itself
# (install.language.make_lang), so there is no separate build phase.
true

%install
# Deliberately NOT pip — see the comment at the top of this spec.
# install/module.py resolves site-packages vs dist-packages per distribution,
# places udev rules / polkit action / systemd unit / D-Bus policy correctly,
# and compiles translations.
#
# THE TWO PIP VARIABLES ARE LOAD-BEARING, AND --no-deps IS NOT ENOUGH.
#
# install/module.py runs `pip install . --target ... --no-deps`. `--no-deps`
# suppresses RUNTIME dependency resolution; it says nothing about PEP 517
# BUILD dependencies. By default pip builds the sdist in an ISOLATED
# environment that it populates from PyPI, so it goes to the network before
# it has looked at anything local. mock has no network in %%install, and the
# result is five connection retries and then:
#
#   ERROR: Could not find a version that satisfies the requirement
#          setuptools>=40.8.0 (from versions: none)
#   ERROR: No matching distribution found for setuptools>=40.8.0
#   ...
#   error: Bad exit status from /var/tmp/rpm-tmp.eJf98H (%%install)
#
# (gnome50-el10 x86_64 and aarch64, run 32674169357 — the only failed package
# in that chain, and the failure left after the changelog-macro fix.)
#
# PIP_NO_BUILD_ISOLATION makes pip use the setuptools already in the
# buildroot, which is what BuildRequires is for. PIP_NO_INDEX is the belt to
# that braces: with no index configured, anything still reaching for the
# network fails immediately and says what it wanted, instead of timing out
# five times and blaming the connection. A buildroot that needs the network
# is a buildroot with an undeclared BuildRequires, and this makes it say so.
#
# Environment rather than flags because the pip invocation is upstream's, in
# install/module.py, not ours to pass arguments to. pip reads PIP_* for every
# invocation including a subprocess, so this reaches it without patching
# their installer.
# 'false', not '1': pip parses env values for NEGATIVE options (--no-*)
# through an inversion (pypa/pip#5735), so PIP_NO_BUILD_ISOLATION=1 turned
# isolation back ON under the buildroot's current pip -- the gate run showed
# 'Installing build dependencies' with PIP_NO_INDEX correctly starving it
# ('from versions: none'), the exact asymmetry of that wart.
export PIP_NO_BUILD_ISOLATION=false
export PIP_NO_INDEX=1
python3 -m install --root %{buildroot}

%files
%{_bindir}/input-remapper-gtk
%{_bindir}/input-remapper-service
%{_bindir}/input-remapper-control
%{_bindir}/input-remapper-reader-service
%{_datadir}/input-remapper/
%{_datadir}/applications/input-remapper-gtk.desktop
%{_datadir}/metainfo/io.github.sezanzeb.input_remapper.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/input-remapper.svg
%{_datadir}/polkit-1/actions/input-remapper.policy
%{_unitdir}/input-remapper.service
%{_datadir}/dbus-1/system.d/inputremapper.Control.conf
%{_sysconfdir}/xdg/autostart/input-remapper-autoload.desktop
%{_udevrulesdir}/69-input-remapper-forwarded.rules
%{_udevrulesdir}/99-input-remapper.rules
# install/module.py picks the interpreter's own site-packages, so the path
# contains the Python minor version.  Globbing prevents a break on rebase.
%{python3_sitelib}/inputremapper/
# install/module.py runs `pip install . --target <site-packages> --no-deps`
# for the python module, which also writes a metadata directory next to it
# (INSTALLER, METADATA, WHEEL, RECORD, licenses/LICENSE, ...).
# The name is pip's normalised distribution name (underscore), not the module
# name.  The brace matches whichever metadata flavour upstream produces.
%{python3_sitelib}/input_remapper-*.dist-info/

%changelog
* Thu Sep 03 2026 TunaOS Bot <bot@tunaos.org> - 2.2.1-4
- BuildRequires systemd-rpm-macros: %%{_unitdir} and %%{_udevrulesdir} were
  undefined in the mock buildroot, so %%files failed with 'File must begin
  with "/"' (weekly chain run 33303057118).

* Sun Aug 23 2026 TunaOS Bot <bot@tunaos.org> - 2.2.1-3
- Build the bundled installer's pip step offline: PIP_NO_BUILD_ISOLATION
  so it uses the buildroot's setuptools instead of fetching one from
  PyPI, PIP_NO_INDEX so any remaining reach for the network fails
  locally and by name. --no-deps only covers runtime dependencies, not
  PEP 517 build dependencies, so mock's lack of network in %%install
  broke the build after five connection retries. Adds python3-wheel,
  which an un-isolated setuptools backend expects to find.

* Fri Aug 21 2026 TunaOS Bot <bot@tunaos.org> - 2.2.1-2
- Add python3-pip and python3-gobject BuildRequires: upstream's bundled
  installer shells out to pip and imports gi, so %%install failed in mock

* Tue Aug 12 2025 TunaOS Bot <bot@tunaos.org> - 2.2.1-1
- Initial package: input-remapper for EL10 (#122, #126)
