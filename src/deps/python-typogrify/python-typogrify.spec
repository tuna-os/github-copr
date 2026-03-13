Name:           python-typogrify
Version:        2.0.7
Release:        1%{?dist}
Summary:        Filters to enhance web typography
License:        BSD-3-Clause
URL:            https://github.com/mintcha/typogrify
Source0:        https://files.pythonhosted.org/packages/source/t/typogrify/typogrify-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3-setuptools

Requires:       python-smartypants

%description
Typogrify provides a set of custom filters that help you to enhance web
typography. It is a port of the original Typogrify for Django.

%prep
%autosetup -n typogrify-%{version}

%build
%py3_build

%install
%py3_install

%files
%{python3_sitelib}/typogrify/
%{python3_sitelib}/typogrify-%{version}-py%{python3_version}.egg-info/

%changelog
* Thu Mar 12 2026 Conductor <james@conductor.local> - 2.0.7-1
- Switch to source tarball and standard build
