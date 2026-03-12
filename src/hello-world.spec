Name:           hello-world
Version:        1.0.0
Release:        1%{?dist}
Summary:        A simple hello world program
License:        MIT
URL:            https://example.com
Source0:        hello-world-1.0.0.tar.gz

BuildRequires:  gcc, make

%description
A simple hello world program for testing the build pipeline.

%prep
%setup -q

%build
make %{?_smp_mflags}

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/usr/bin
install -m 0755 hello %{buildroot}/usr/bin/hello-world

%files
/usr/bin/hello-world

%changelog
* Thu Mar 12 2026 Tuna OS <info@tunaos.org> - 1.0.0-1
- Initial package
