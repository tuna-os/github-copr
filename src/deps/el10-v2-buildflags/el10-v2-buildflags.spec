Name:           el10-v2-buildflags
Version:        2
Release:        1%{?dist}
Summary:        Override RPM optflags for x86_64_v2 buildroots on EL10
License:        MIT
BuildArch:      noarch

%description
Overrides %%optflags to use -march=x86-64-v2 instead of the EL10 default
-march=x86-64-v3. Required in COPR alma-kitten+epel-10-x86_64_v2 chroot
where build hosts only support SSE4.2 and cannot execute v3 instructions.

%install
mkdir -p %{buildroot}%{_sysconfdir}/rpm/macros.d
printf '%%%%optflags -O2 -flto=auto -ffat-lto-objects -fexceptions -g -grecord-gcc-switches -pipe -Wall -Werror=format-security -Wp,-U_FORTIFY_SOURCE,-D_FORTIFY_SOURCE=3 -Wp,-D_GLIBCXX_ASSERTIONS -specs=/usr/lib/rpm/redhat/redhat-hardened-cc1 -fstack-protector-strong -specs=/usr/lib/rpm/redhat/redhat-annobin-cc1 -m64 -march=x86-64-v2 -mtune=generic -fasynchronous-unwind-tables -fstack-clash-protection -fcf-protection\n' \
    > %{buildroot}%{_sysconfdir}/rpm/macros.d/el10-v2-buildflags

%files
%{_sysconfdir}/rpm/macros.d/el10-v2-buildflags
