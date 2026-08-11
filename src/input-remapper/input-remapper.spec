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
Release:        1%{?dist}
Summary:        Change the mapping of input device buttons

License:        GPL-3.0-or-later
URL:            https://github.com/sezanzeb/input-remapper
Source0:        https://github.com/sezanzeb/input-remapper/archive/refs/tags/%{version}.tar.gz#/input-remapper-%{version}.tar.gz

BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  gettext

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
* Tue Aug 12 2025 TunaOS Bot <bot@tunaos.org> - 2.2.1-1
- Initial package: input-remapper for EL10 (#122, #126)
