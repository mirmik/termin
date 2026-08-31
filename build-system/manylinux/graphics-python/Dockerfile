FROM quay.io/pypa/manylinux_2_28_x86_64@sha256:0bf9db09181f36be8cf0628332abb5d31855b7d0f372faa776f492ccd9d3100d AS lavapipe-builder

COPY lavapipe-python-requirements.txt /tmp/lavapipe-python-requirements.txt

RUN dnf install -y \
        elfutils-libelf-devel-0.190-2.el8.alma.1 \
        flex-2.6.1-9.el8 \
        libzstd-devel-1.4.4-1.el8 \
        llvm-compat-devel-17.0.6-3.module_el8.10.0+4172+b6b13d75 \
        ninja-build-1.8.2-1.el8 \
        systemd-devel-239-82.el8_10.17 \
    && /opt/python/cp311-cp311/bin/python -m pip install \
        --disable-pip-version-check \
        --no-cache-dir \
        --require-hashes \
        --requirement /tmp/lavapipe-python-requirements.txt \
    && curl --fail --location \
        https://archive.mesa3d.org/mesa-24.3.4.tar.xz \
        --output /tmp/mesa.tar.xz \
    && printf '%s  %s\n' \
        e641ae27191d387599219694560d221b7feaa91c900bcec46bf444218ed66025 \
        /tmp/mesa.tar.xz \
        | sha256sum --check --strict - \
    && curl --fail --location \
        https://xcb.freedesktop.org/dist/libxcb-1.13.1.tar.bz2 \
        --output /tmp/libxcb.tar.bz2 \
    && printf '%s  %s\n' \
        a89fb7af7a11f43d2ce84a844a4b38df688c092bf4b67683aef179cdf2a647c4 \
        /tmp/libxcb.tar.bz2 \
        | sha256sum --check --strict - \
    && curl --fail --location \
        https://www.x.org/releases/individual/lib/libXau-1.0.9.tar.bz2 \
        --output /tmp/libXau.tar.bz2 \
    && printf '%s  %s\n' \
        ccf8cbf0dbf676faa2ea0a6d64bcc3b6746064722b606c8c52917ed00dcb73ec \
        /tmp/libXau.tar.bz2 \
        | sha256sum --check --strict - \
    && curl --fail --location \
        https://github.com/NVIDIA/libglvnd/archive/refs/tags/v1.3.4.tar.gz \
        --output /tmp/libglvnd.tar.gz \
    && printf '%s  %s\n' \
        8f4218d7cdaf89d5b7eced818e810ccbc76f4bb9cba36d66eddac5a7ca892bab \
        /tmp/libglvnd.tar.gz \
        | sha256sum --check --strict - \
    && mkdir -p \
        /opt/termin-release-licenses/libxcb \
        /opt/termin-release-licenses/libXau \
        /opt/termin-release-licenses/libglvnd \
    && tar --directory /opt/termin-release-licenses/libxcb \
        --extract --file /tmp/libxcb.tar.bz2 --strip-components=1 \
        libxcb-1.13.1/COPYING \
    && tar --directory /opt/termin-release-licenses/libXau \
        --extract --file /tmp/libXau.tar.bz2 --strip-components=1 \
        libXau-1.0.9/COPYING \
    && tar --directory /opt/termin-release-licenses/libglvnd \
        --extract --file /tmp/libglvnd.tar.gz --strip-components=1 \
        libglvnd-1.3.4/README.md \
    && tar --directory /tmp --extract --file /tmp/mesa.tar.xz \
    && PATH=/usr/lib64/llvm17/bin:/opt/python/cp311-cp311/bin:${PATH} \
        meson setup /tmp/mesa-build /tmp/mesa-24.3.4 \
        --prefix=/opt/termin-lavapipe \
        --libdir=lib \
        -Dbuild-tests=false \
        -Degl=disabled \
        -Dgallium-drivers=softpipe,llvmpipe \
        -Dgbm=disabled \
        -Dgles1=disabled \
        -Dgles2=disabled \
        -Dglx=disabled \
        -Dllvm=enabled \
        -Dopengl=false \
        -Dosmesa=false \
        -Dplatforms=[] \
        -Dshared-glapi=disabled \
        -Dshared-llvm=enabled \
        -Dvalgrind=disabled \
        -Dvulkan-drivers=swrast \
    && ninja -C /tmp/mesa-build install

FROM quay.io/pypa/manylinux_2_28_x86_64@sha256:0bf9db09181f36be8cf0628332abb5d31855b7d0f372faa776f492ccd9d3100d

COPY --from=lavapipe-builder /opt/termin-lavapipe /opt/termin-lavapipe
COPY --from=lavapipe-builder /opt/termin-release-licenses /opt/termin-release-licenses

RUN dnf install -y \
        mesa-dri-drivers-23.1.4-4.el8_10.alma.1 \
        rsync-3.1.3-27.el8_10 \
        vulkan-headers-1.3.283.0-1.el8_10 \
        vulkan-loader-devel-1.3.283.0-1.el8_10 \
    && dnf clean all \
    && rm -rf /var/cache/dnf

ENV VK_ICD_FILENAMES=/opt/termin-lavapipe/share/vulkan/icd.d/lvp_icd.x86_64.json
