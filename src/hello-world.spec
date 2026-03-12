Name:           hello-world
Version:        1.0.0
Release:        1%{?dist}
Summary:        A simple hello world program
License:        MIT
URL:            https://example.com
Source0:        %{name}-%{version}.tar.gz

%description
A simple hello world program for testing the build pipeline.

%prep
%autosetup

%build
make %{?_smp_mflags}

%install
mkdir -p %{buildroot}%{_bindir}
install -m 0755 hello %{buildroot}%{_bindir}/%{name}

%files
%{_bindir}/%{name}

%changelog
* Thu Mar 12 2026 James Reilly <james@example.com> - 1.0.0-1
- Initial package
