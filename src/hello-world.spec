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
tar -xzf %{SOURCE0}

%build
cd hello-world-1.0.0
make

%install
rm -rf %{buildroot}
mkdir -p %{buildroot}/usr/bin
cd hello-world-1.0.0
make DESTDIR=%{buildroot} install

%files
/usr/bin/hello-world

%changelog
* Thu Mar 12 2026 Tuna OS <info@tunaos.org> - 1.0.0-1
- Initial package
