Name:           zimg
Version:        3.0.6
Release:        4%{?dist}
Summary:        Scaling, color space conversion, and dithering library
License:        WTFPL
URL:            https://github.com/sekrit-twc/zimg

Source0:        %{url}/archive/release-%{version}/%{name}-%{version}.tar.gz
# Fix build with GCC 15.  Applies cleanly to the 3.0.6 tarball and is still
# needed: Rawhide is on GCC 16.
Patch0:         https://github.com/sekrit-twc/zimg/commit/b013c7b006e6bee05b7964162f3a00402168e77f.patch

# Rawhide's spec also carries upstream 0e56801 ("colorspace: fix AVX2 check"),
# and that patch CANNOT apply to the 3.0.6 tarball it ships beside.  It rewrites
#
#     if (!ret && caps.avx)          ->    if (!ret && caps.avx2)
#             ret = create_matrix_operation_avx2(m);
#
# but create_matrix_operation_avx2 does not exist anywhere in release-3.0.6 --
# checked across the whole source tree, its only occurrence there is inside the
# .rej file the failed patch leaves behind.  It was added to upstream master
# after the release; in 3.0.6 the dispatcher guards an AVX call with caps.avx,
# which is correct as written.  So the patch fixes a bug this version does not
# have, and dropping it is the fix rather than a workaround.
#
# Reproduced against Fedora's own pinned tarball (SHA512 verified against
# dist-git sources), with rpm's exact flags: Patch0 applies, this one fails
# "Hunk #1 FAILED at 16".  That is what failed src/hummingbird/zimg in run
# 31294475023 and, before it, the kde-00 tier.
#
# Restore it when zimg releases a version that contains the AVX2 dispatcher.

BuildRequires:  autoconf
BuildRequires:  automake
BuildRequires:  gcc-c++
BuildRequires:  libtool
BuildRequires:  make

%description
The "z" library implements the commonly required image processing basics of
scaling, color space conversion, and depth conversion. A simple API enables
conversion between any supported formats to operate with minimal knowledge from
the programmer. All library routines were designed from the ground-up with
correctness, flexibility, and thread-safety as first priorities. Allocation,
buffering, and I/O are cleanly separated from processing, allowing the
programmer to adapt "z" to many scenarios.

%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.

%prep
%autosetup -p1 -n zimg-release-%{version}

%build
autoreconf -vif
%configure \
    --disable-static \
    --enable-testapp
%make_build V=1

%install
%make_install
install -m 755 -p -D testapp %{buildroot}%{_bindir}/testapp

find %{buildroot} -name '*.la' -delete

# Pick up docs in the files section
rm -fr %{buildroot}%{_docdir}/%{name}

%files
%license COPYING
%doc README.md ChangeLog
%{_libdir}/lib%{name}.so.2.0.0
%{_libdir}/lib%{name}.so.2

%files devel
%{_bindir}/testapp
%{_includedir}/*
%{_libdir}/lib%{name}.so
%{_libdir}/pkgconfig/%{name}.pc

%changelog
* Sun Aug 09 2026 TunaOS <packages@tuna-os.org> - 3.0.6-4
- Vendor Fedora's packaging without the AVX2 patch, which cannot apply to 3.0.6

