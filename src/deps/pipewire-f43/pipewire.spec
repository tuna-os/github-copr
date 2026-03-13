%global majorversion 1
%global minorversion 6
%global microversion 1

%global apiversion   0.3
%global spaversion   0.2
%global soversion    0
%global libversion   %{soversion}.%(bash -c '((intversion = (%{minorversion} * 100) + %{microversion})); echo ${intversion}').0
%global ms_version   0.4.2

# For rpmdev-bumpspec and releng automation
%global baserelease 2

#global snapdate   20210107
#global gitcommit  b17db2cebc1a5ab2c01851d29c05f79cd2f262bb
#global shortcommit %(c=%{gitcommit}; echo ${c:0:7})

# https://bugzilla.redhat.com/983606
%global _hardened_build 1

# where/how to apply multilib hacks
%global multilib_archs x86_64 %{ix86} ppc64 ppc s390x s390 sparc64 sparcv9 ppc64le

# Build conditions for various features
%bcond_without alsa
%bcond_without vulkan

# Features disabled for RHEL 8
%if 0%{?rhel} && 0%{?rhel} < 9
%bcond_with pulse
%bcond_with jack
%else
%bcond_without pulse
%bcond_without jack
%endif

# Features disabled for RHEL
%if 0%{?rhel}
%bcond_with jackserver_plugin
%bcond_with libmysofa
%bcond_with lv2
%bcond_with roc
%bcond_with ffado
%bcond_with onnx
%else
%bcond_without jackserver_plugin
%bcond_without libmysofa
%bcond_without lv2
%bcond_without roc
%ifarch s390x
%bcond_with ffado
%bcond_with onnx
%elifarch %{ix86}
%bcond_without ffado
%bcond_with onnx
%else
%bcond_without ffado
%bcond_without onnx
%endif
%endif

# Disabled for RHEL < 11 and Fedora < 36
%if (0%{?rhel} && 0%{?rhel} < 11) || (0%{?fedora} && 0%{?fedora} < 36) || ("%{_arch}" == "s390x") || ("%{_arch}" == "ppc64le")
%bcond_with libcamera_plugin
%else
%bcond_without libcamera_plugin
%endif

%bcond_without v4l2

Name:           pipewire
Summary:        Media Sharing Server
Version:        %{majorversion}.%{minorversion}.%{microversion}
Release:        %{baserelease}%{?snapdate:.%{snapdate}git%{shortcommit}}%{?dist}
# PipeWire is generally MIT but includes plugins using libraries under other licenses.
# See the module specific License for details.
License:        MIT
URL:            https://pipewire.org/
%if 0%{?snapdate}
Source0:        https://gitlab.freedesktop.org/pipewire/pipewire/-/archive/%{gitcommit}/pipewire-%{shortcommit}.tar.gz
%else
Source0:        https://gitlab.freedesktop.org/pipewire/pipewire/-/archive/%{version}/pipewire-%{version}.tar.gz
%endif
Source1:        pipewire.sysusers

## upstream patches
Patch0001:	0001-impl-link-fix-shared-mem-test.patch

## upstreamable patches

## fedora patches

BuildRequires:  gettext
BuildRequires:  meson >= 0.59.0
BuildRequires:  gcc
BuildRequires:  g++
BuildRequires:  pkgconfig
BuildRequires:  pkgconfig(libudev)
BuildRequires:  pkgconfig(dbus-1)
BuildRequires:  pkgconfig(glib-2.0) >= 2.32
BuildRequires:  pkgconfig(gio-unix-2.0) >= 2.32
BuildRequires:  pkgconfig(gstreamer-1.0) >= 1.10.0
BuildRequires:  pkgconfig(gstreamer-base-1.0) >= 1.10.0
BuildRequires:  pkgconfig(gstreamer-plugins-base-1.0) >= 1.10.0
BuildRequires:  pkgconfig(gstreamer-net-1.0) >= 1.10.0
BuildRequires:  pkgconfig(gstreamer-allocators-1.0) >= 1.10.0
# libldac is not built on x390x, see rhbz#1677491
%ifnarch s390x


%endif
BuildRequires:  pkgconfig(fdk-aac)
BuildRequires:  pkgconfig(bluez)
BuildRequires:  systemd
BuildRequires:  systemd-devel
BuildRequires:  alsa-lib-devel
BuildRequires:  libv4l-devel
BuildRequires:  doxygen
BuildRequires:  python-docutils
BuildRequires:  graphviz
BuildRequires:  sbc-devel
BuildRequires:  liblc3-devel
BuildRequires:  libsndfile-devel
BuildRequires:  ncurses-devel
BuildRequires:  pulseaudio-libs-devel
BuildRequires:  avahi-devel
%if (0%{?fedora} && 0%{?fedora} < 44) || (0%{?rhel} && 0%{?rhel} < 11)
BuildRequires:  pkgconfig(webrtc-audio-processing-1)
%else
BuildRequires:  pkgconfig(webrtc-audio-processing-2)
%endif
BuildRequires:  libusb1-devel
BuildRequires:  readline-devel
BuildRequires:  openssl-devel
BuildRequires:  libcanberra-devel
BuildRequires:  libuv-devel
BuildRequires:  speexdsp-devel
BuildRequires:  systemd-rpm-macros

BuildRequires:  fftw-devel


Requires:       %{name}-libs%{?_isa} = %{version}-%{release}
Requires:       systemd
Requires:       rtkit
# A virtual Provides so we can swap session managers
Requires:       pipewire-session-manager
# Prefer WirePlumber for session manager
Suggests:       wireplumber
# Bring in libcamera plugin for MIPI / complex camera support
Recommends:     pipewire-plugin-libcamera

%description
PipeWire is a multimedia server for Linux and other Unix like operating
systems.

%package libs
Summary:        Libraries for PipeWire clients
# fftw is GPL-2.0-or later, ladpsa is LGPL-2.0-or-later and used in filter-graph.
License:        MIT AND GPL-2.0-or-later AND BSD-2-Clause AND LGPL-2.0-or-later
Recommends:     %{name}%{?_isa} = %{version}-%{release}
Obsoletes:      %{name}-libpulse < %{version}-%{release}

%description libs
This package contains the runtime libraries for any application that wishes
to interface with a PipeWire media server.

%package gstreamer
Summary:        GStreamer elements for PipeWire
License:        MIT
Recommends:     %{name}%{?_isa} = %{version}-%{release}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}

%description gstreamer
This package contains GStreamer elements to interface with a
PipeWire media server.

%package devel
Summary:        Headers and libraries for PipeWire client development
License:        MIT
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}
%description devel
Headers and libraries for developing applications that can communicate with
a PipeWire media server.

%package doc
Summary:        PipeWire media server documentation
License:        MIT

%description doc
This package contains documentation for the PipeWire media server.

%package utils
Summary:        PipeWire media server utilities
License:        MIT
Requires:       %{name}%{?_isa} = %{version}-%{release}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}

%description utils
This package contains command line utilities for the PipeWire media server.

%if %{with alsa}
%package alsa
Summary:        PipeWire media server ALSA support
License:        MIT
Recommends:     %{name}%{?_isa} = %{version}-%{release}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}
%if ! (0%{?fedora} && 0%{?fedora} < 34)
# Ensure this is provided by default to route all audio
Supplements:    %{name} = %{version}-%{release}
# Replace PulseAudio and JACK ALSA plugins with PipeWire
## N.B.: If alsa-plugins gets updated in F33, this will need to be bumped
Obsoletes:      alsa-plugins-jack < 1.2.2-5
Obsoletes:      alsa-plugins-pulseaudio < 1.2.2-5
%endif

%description alsa
This package contains an ALSA plugin for the PipeWire media server.
%endif

%if %{with jack}
%package jack-audio-connection-kit-libs
Summary:        PipeWire JACK implementation libraries
License:        MIT
Recommends:     %{name}%{?_isa} = %{version}-%{release}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}
Requires:       %{name}-jack-audio-connection-kit%{?_isa} = %{version}-%{release}
# Fixed jack subpackages
Conflicts:      %{name}-libjack < 0.3.13-6
Conflicts:      %{name}-jack-audio-connection-kit < 0.3.13-6
# Replaces libjack subpackage
Obsoletes:      %{name}-libjack < 0.3.19-2
Provides:       %{name}-libjack = %{version}-%{release}
Provides:       %{name}-libjack%{?_isa} = %{version}-%{release}

%description jack-audio-connection-kit-libs
This package provides a JACK implementation libraries based on PipeWire

%package jack-audio-connection-kit
Summary:        PipeWire JACK implementation
License:        MIT
Recommends:     %{name}%{?_isa} = %{version}-%{release}
Requires:       %{name}-jack-audio-connection-kit-libs%{?_isa} = %{version}-%{release}
# Replaces libjack subpackage
%if ! (0%{?fedora} && 0%{?fedora} < 34)
# Ensure this is provided by default to route all audio
Supplements:    %{name} = %{version}-%{release}
# Replace JACK with PipeWire-JACK
## N.B.: If jack gets updated in F33, this will need to be bumped
Obsoletes:      jack-audio-connection-kit < 1.9.16-2
# Fix upgrade path to f38, see #2203789
Obsoletes:      jack-audio-connection-kit-example-clients < 1.9.22
%endif

%description jack-audio-connection-kit
This package provides a JACK implementation based on PipeWire

%package jack-audio-connection-kit-devel
Summary:        Development files for %{name}-jack-audio-connection-kit
License:        MIT
Requires:       %{name}-jack-audio-connection-kit-libs%{?_isa} = %{version}-%{release}
Conflicts:      jack-audio-connection-kit-devel
Enhances:       %{name}-jack-audio-connection-kit-libs

%description jack-audio-connection-kit-devel
This package provides development files for building JACK applications
using PipeWire's JACK library.
%endif

%if %{with jackserver_plugin}
%package plugin-jack
Summary:        PipeWire media server JACK support
License:        MIT
BuildRequires:  jack-audio-connection-kit-devel
Recommends:     %{name}%{?_isa} = %{version}-%{release}
Requires:       %{name}-jack-audio-connection-kit-libs = %{version}-%{release}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}
Requires:       jack-audio-connection-kit

%description plugin-jack
This package contains the PipeWire spa plugin to connect to a JACK server.
%endif

%if %{with libcamera_plugin}
%package plugin-libcamera
Summary:        PipeWire media server libcamera support
License:        MIT
BuildRequires:  libcamera-devel
BuildRequires:  libdrm-devel
Recommends:     %{name}%{?_isa} = %{version}-%{release}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}
Requires:       libcamera
Requires:       libdrm

%description plugin-libcamera
This package contains the PipeWire spa plugin to access cameras through libcamera.
%endif

%if %{with vulkan}
%package plugin-vulkan
Summary:        PipeWire media server vulkan support
License:        MIT
BuildRequires:  pkgconfig(vulkan)
Recommends:     %{name}%{?_isa} = %{version}-%{release}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}

%description plugin-vulkan
This package contains the PipeWire spa plugin for vulkan.
%endif

%if %{with pulse}
%package pulseaudio
Summary:        PipeWire PulseAudio implementation
License:        MIT
Recommends:     %{name}%{?_isa} = %{version}-%{release}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}
Conflicts:      pulseaudio
# Fixed pulseaudio subpackages
Conflicts:      %{name}-libpulse < 0.3.13-6
Conflicts:      %{name}-pulseaudio < 0.3.13-6
%if ! (0%{?fedora} && 0%{?fedora} < 34)
# Ensure this is provided by default to route all audio
Supplements:    %{name} = %{version}-%{release}
# Replace PulseAudio with PipeWire-PulseAudio
## N.B.: If pulseaudio gets updated in F33, this will need to be bumped
Obsoletes:      pulseaudio < 14.2-3
Obsoletes:      pulseaudio-esound-compat < 14.2-3
Obsoletes:      pulseaudio-module-bluetooth < 14.2-3
Obsoletes:      pulseaudio-module-gconf < 14.2-3
Obsoletes:      pulseaudio-module-gsettings < 14.2-3
Obsoletes:      pulseaudio-module-jack < 14.2-3
Obsoletes:      pulseaudio-module-lirc < 14.2-3
Obsoletes:      pulseaudio-module-x11 < 14.2-3
Obsoletes:      pulseaudio-module-zeroconf < 14.2-3
Obsoletes:      pulseaudio-qpaeq < 14.2-3
%endif

# Virtual Provides to support swapping between PipeWire-PA and PA
Provides:       pulseaudio-daemon
Conflicts:      pulseaudio-daemon
Provides:       pulseaudio-module-bluetooth
Provides:       pulseaudio-module-jack

%description pulseaudio
This package provides a PulseAudio implementation based on PipeWire
%endif

%if %{with v4l2}
%package v4l2
Summary:        PipeWire media server v4l2 LD_PRELOAD support
License:        MIT
Recommends:     %{name}%{?_isa} = %{version}-%{release}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}

%description v4l2
This package contains an LD_PRELOAD library that redirects v4l2 applications to
PipeWire.
%endif

%package module-x11
Summary:        PipeWire media server x11 support
License:        MIT
Recommends:     %{name}%{?_isa} = %{version}-%{release}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}

%description module-x11
This package contains X11 bell support for PipeWire.

%if %{with ffado}
%package module-ffado
Summary:        PipeWire media server ffado support
License:        MIT AND GPL-2.0-only OR GPL-3.0-only
BuildRequires:  libffado-devel
Recommends:     %{name}%{?_isa} = %{version}-%{release}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}

%description module-ffado
This package contains the FFADO support for PipeWire.
%endif

%if %{with roc}
%package module-roc
Summary:        PipeWire media server ROC support
License:        MIT AND MPL-2.0 AND LGPL-2.1-or-later AND CECILL-C
BuildRequires:  roc-toolkit-devel
BuildRequires:  libunwind-devel
BuildRequires:  openfec-devel
BuildRequires:  sox-devel
Recommends:     %{name}%{?_isa} = %{version}-%{release}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}

%description module-roc
This package contains the ROC support for PipeWire.
%endif

%if %{with libmysofa}
%package module-filter-chain-sofa
Summary:        PipeWire media server sofa filter-chain support
License:        MIT AND BSD-3-Clause
BuildRequires:  libmysofa-devel
Recommends:     %{name}%{?_isa} = %{version}-%{release}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}

%description module-filter-chain-sofa
This package contains the mysofa support for PipeWire filter-chain.
%endif

%if %{with lv2}
%package module-filter-chain-lv2
Summary:        PipeWire media server lv2 filter-chain support
License:        MIT
BuildRequires:  lilv-devel
Recommends:     %{name}%{?_isa} = %{version}-%{release}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}

%description module-filter-chain-lv2
This package contains the mysofa support for PipeWire filter-chain.
%endif

%if %{with onnx}
%package module-filter-chain-onnx
Summary:        PipeWire media server ONNX filter-chain support
License:        MIT AND Apache-2.0 AND BSL-1.0 AND BSD-3-Clause
BuildRequires:  onnxruntime-devel
Recommends:     %{name}%{?_isa} = %{version}-%{release}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}

%description module-filter-chain-onnx
This package contains the ONNX support for PipeWire filter-chain.
%endif

%package config-rates
Summary:        PipeWire media server multirate configuration
License:        MIT
Recommends:     %{name}%{?_isa} = %{version}-%{release}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}

%description config-rates
This package contains the configuration files to support multiple
sample rates.

%package config-upmix
Summary:        PipeWire media server upmixing configuration
License:        MIT
Recommends:     %{name}%{?_isa} = %{version}-%{release}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}

%description config-upmix
This package contains the configuration files to support upmixing.

%package config-raop
Summary:        PipeWire configuration enabling the raop module
License:        MIT
Recommends:     %{name}%{?_isa} = %{version}-%{release}
Requires:       %{name}-libs%{?_isa} = %{version}-%{release}

%description config-raop
This package contains the configuration file to enable the RAOP module.

%prep
%autosetup -p1 %{?snapdate:-n %{name}-%{gitcommit}}


%if %{with media-session}
mkdir subprojects/packagefiles
cp %{SOURCE1} subprojects/packagefiles/
%endif

%build
meson setup --prefix=/usr --libdir=/usr/lib64 --buildtype=plain build -Dbluez5-codec-ldac=disabled -Dlv2=disabled -Debur128=disabled -Dbluez5-plc-spandsp=disabled -Dsession-managers=[] -Ddocs=disabled -Dman=disabled -Dsdl2=disabled -Daudiotestsrc=disabled -Dvideotestsrc=disabled -Dvolume=disabled -Dbluez5-codec-aptx=disabled -Dbluez5-codec-lc3plus=disabled -Dbluez5-codec-ldac-dec=disabled -Drtprio-server=60 -Drtprio-client=55 -Drlimits-rtprio=70 -Dsnap=disabled -Djack=disabled -Dlibcamera=disabled -Djack-devel=true -Dvulkan=disabled -Dlibmysofa=disabled -Donnxruntime=disabled -Droc=disabled -Dlibffado=disabled \
    -D docs=enabled -D man=enabled -D gstreamer=enabled -D libsystemd=enabled	\
    -D systemd-user-service=enabled 						\
    -D sdl2=disabled 								\
    -D audiotestsrc=disabled -D videotestsrc=disabled				\
    -D volume=disabled -D bluez5-codec-aptx=disabled 		  		\
    -D bluez5-codec-lc3plus=disabled -D bluez5-codec-lc3=enabled		\
    -D bluez5-codec-ldac-dec=disabled 						\
%ifarch s390x
    -D bluez5-codec-ldac=disabled						\
%endif
    -D session-managers=[] 							\
    -D rtprio-server=60 -D rtprio-client=55 -D rlimits-rtprio=70		\
    -D snap=disabled								\
    %{!?with_jack:-D pipewire-jack=disabled} 					\
    %{!?with_jackserver_plugin:-D jack=disabled} 				\
    %{!?with_libcamera_plugin:-D libcamera=disabled} 				\
    %{?with_jack:-D jack-devel=true} 						\
    %{!?with_alsa:-D pipewire-alsa=disabled}					\
    %{?with_vulkan:-D vulkan=enabled}						\
    %{!?with_libmysofa:-D libmysofa=disabled}					\
    %{!?with_lv2:-D lv2=disabled}						\
    %{!?with_onnx:-D onnxruntime=disabled}					\
    %{!?with_roc:-D roc=disabled}						\
    %{!?with_ffado:-D libffado=disabled}					\
    %{nil}
meson compile -C build

%install
install -p -D -m 0644 %{SOURCE1} %{buildroot}%{_sysusersdir}/pipewire.conf
DESTDIR=%{buildroot} meson install -C build

# Own this directory so add-ons can use it
install -d -m 0755 %{buildroot}%{_datadir}/pipewire/pipewire.conf.d/
install -d -m 0755 %{buildroot}%{_datadir}/pipewire/client.conf.d/

%if %{with jack}
mkdir -p %{buildroot}%{_sysconfdir}/ld.so.conf.d/
echo %{_libdir}/pipewire-%{apiversion}/jack/ > %{buildroot}%{_sysconfdir}/ld.so.conf.d/pipewire-jack-%{_arch}.conf
%else
rm %{buildroot}%{_datadir}/pipewire/jack.conf

%endif

%if %{with alsa}
mkdir -p %{buildroot}%{_sysconfdir}/alsa/conf.d/
cp %{buildroot}%{_datadir}/alsa/alsa.conf.d/50-pipewire.conf \
        %{buildroot}%{_sysconfdir}/alsa/conf.d/50-pipewire.conf
cp %{buildroot}%{_datadir}/alsa/alsa.conf.d/99-pipewire-default.conf \
        %{buildroot}%{_sysconfdir}/alsa/conf.d/99-pipewire-default.conf

%endif

%if ! %{with pulse}
# If the PulseAudio replacement isn't being offered, delete the files
rm %{buildroot}%{_bindir}/pipewire-pulse
rm %{buildroot}%{_userunitdir}/pipewire-pulse.*
rm %{buildroot}%{_datadir}/pipewire/pipewire-pulse.conf

%endif

%if %{with pulse}
# Own this directory so add-ons can use it
install -d -m 0755 %{buildroot}%{_datadir}/pipewire/pipewire-pulse.conf.d/

ln -s ../pipewire-pulse.conf.avail/20-upmix.conf \
		%{buildroot}%{_datadir}/pipewire/pipewire-pulse.conf.d/20-upmix.conf
%endif

# rates config
ln -s ../pipewire.conf.avail/10-rates.conf \
		%{buildroot}%{_datadir}/pipewire/pipewire.conf.d/10-rates.conf

# upmix config
ln -s ../pipewire.conf.avail/20-upmix.conf \
		%{buildroot}%{_datadir}/pipewire/pipewire.conf.d/20-upmix.conf
ln -s ../client.conf.avail/20-upmix.conf \
		%{buildroot}%{_datadir}/pipewire/client.conf.d/20-upmix.conf

# raop config
ln -s ../pipewire.conf.avail/50-raop.conf \
		%{buildroot}%{_datadir}/pipewire/pipewire.conf.d/50-raop.conf

%find_lang %{name}

