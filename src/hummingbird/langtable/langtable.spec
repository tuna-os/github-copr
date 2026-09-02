Name:           langtable
Version:        0.0.71
Release:        %autorelease
Summary:        Guessing reasonable defaults for locale, keyboard layout, territory, and language.
# the translations in languages.xml and territories.xml are (mostly)
# imported from CLDR and are thus under the Unicode license, the
# short name for this license is "MIT", see:
# https://fedoraproject.org/wiki/Licensing:MIT?rd=Licensing/MIT#Modern_Style_without_sublicense_.28Unicode.29
License:        GPL-3.0-or-later
URL:            https://github.com/mike-fabian/langtable
Source0:        https://github.com/mike-fabian/langtable/releases/download/%{version}/%{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  perl-interpreter
BuildRequires:  python3-devel
# xmllint: %check validates the five data files against their RelaxNG
# schemas with it.  Fedora's own spec does not name libxml2 because Koji's
# buildroot happens to carry it; Hummingbird's (Fedora 44 + Hummingbird,
# mock/hummingbird-ci.cfg) does not, and the build died on
#     /var/tmp/rpm-tmp.mQw7LM: line 72: xmllint: command not found
# on every hummingbird leg since the first (runs 33580878734, 33597624514).
# The only line that differs from Fedora rawhide's langtable.spec; the rest
# is the dist-git import scripts/import-fedora-distgit.py would have made.
BuildRequires:  libxml2

%description
langtable is used to guess reasonable defaults for locale, keyboard layout,
territory, and language, if part of that information is already known. For
example, guess the territory and the keyboard layout if the language
is known or guess the language and keyboard layout if the territory is
already known.

%package -n python3-langtable
Summary:        Python module to query the langtable-data
License:        GPL-3.0-or-later
Requires:       %{name} = %{version}-%{release}
Obsoletes:      %{name}-data < %{version}-%{release}
Provides:       %{name}-data = %{version}-%{release}

%description -n python3-langtable
This package contains a Python module to query the data
from langtable-data.

%prep
%setup -q

%generate_buildrequires
%pyproject_buildrequires

%build
perl -pi -e "s,_DATADIR = '(.*)',_DATADIR = '%{_datadir}/langtable'," langtable/langtable.py

%pyproject_wheel

%install

%pyproject_install
%pyproject_save_files langtable

%check
%pyproject_check_import

(cd $RPM_BUILD_DIR/%{name}-%{version}/langtable; %{__python3} langtable.py)
(cd $RPM_BUILD_DIR/%{name}-%{version}; %{__python3} test_cases.py)
xmllint --noout --relaxng \
        $RPM_BUILD_DIR/%{name}-%{version}/langtable/schemas/keyboards.rng \
        $RPM_BUILD_DIR/%{name}-%{version}/langtable/data/keyboards.xml.gz
xmllint --noout --relaxng \
        $RPM_BUILD_DIR/%{name}-%{version}/langtable/schemas/languages.rng \
        $RPM_BUILD_DIR/%{name}-%{version}/langtable/data/languages.xml.gz
xmllint --noout --relaxng \
        $RPM_BUILD_DIR/%{name}-%{version}/langtable/schemas/territories.rng \
        $RPM_BUILD_DIR/%{name}-%{version}/langtable/data/territories.xml.gz
xmllint --noout --relaxng \
        $RPM_BUILD_DIR/%{name}-%{version}/langtable/schemas/timezoneidparts.rng \
        $RPM_BUILD_DIR/%{name}-%{version}/langtable/data/timezoneidparts.xml.gz
xmllint --noout --relaxng \
        $RPM_BUILD_DIR/%{name}-%{version}/langtable/schemas/timezones.rng \
        $RPM_BUILD_DIR/%{name}-%{version}/langtable/data/timezones.xml.gz

%files
%license COPYING unicode-license.txt
%doc README* ChangeLog test_cases.py langtable/schemas/*.rng

%files -n python3-langtable -f %{pyproject_files}

%changelog
%autochangelog
