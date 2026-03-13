Name:           python-smartypants
Version:        2.0.2
Release:        1%{?dist}
Summary:        Python with the SmartyPants Web publishing tool
License:        BSD-3-Clause
URL:            https://github.com/leo-hemsted/smartypants.py
Source0:        https://files.pythonhosted.org/packages/source/s/smartypants/smartypants-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3-setuptools

%description
SmartyPants is a free-software code-to-HTML translation tool for web writers.
It allows you to use your favorite text editor to write, and then translates
plain ASCII punctuation characters into smart HTML entities.

%prep
%autosetup -n smartypants-%{version}

%build
%py3_build

%install
%py3_install

%files
%{python3_sitelib}/smartypants.py
%{python3_sitelib}/__pycache__/smartypants.*
%{python3_sitelib}/smartypants-%{version}-py%{python3_version}.egg-info/
%{_bindir}/smartypants

%changelog
* Thu Mar 12 2026 Conductor <james@conductor.local> - 2.0.1-1
- Switch to source tarball and standard build
