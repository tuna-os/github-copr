FROM fedora:45

RUN dnf -y install \
    dnf-plugins-core \
    mock \
    createrepo_c \
    rpm-sign \
    rpm-build \
    git \
    wget \
    curl \
    python3 \
    python3-pip \
    meson \
    ninja \
    gobject-introspection-devel \
    gtk-doc \
    && dnf clean all

RUN useradd -m -s /bin/bash builder && \
    usermod -a -G mock builder

USER builder
WORKDIR /home/builder

CMD ["/bin/bash"]
