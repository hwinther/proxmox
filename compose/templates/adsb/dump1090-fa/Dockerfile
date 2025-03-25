FROM debian:bullseye AS base
LABEL maintainer="Hans Christian Winther-Sørensen <docker@wsh.no>"
ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-x", "-o", "pipefail", "-c"]
RUN apt-get update && \
    apt-get -y full-upgrade

FROM base AS runtime
RUN apt-get -y install curl gettext-base nano net-tools procps socat wget xz-utils && \
    apt-get clean
ENV S6_OVERLAY_VERSION="3.2.0.2"
ARG ARCH="x86_64"
ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz /tmp
ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${ARCH}.tar.xz /tmp
RUN tar -C / -Jxpf /tmp/s6-overlay-noarch.tar.xz && \
    tar -C / -Jxpf /tmp/s6-overlay-${ARCH}.tar.xz && \
    rm -f /tmp/*.tar.xz

FROM runtime AS install-build-deps
RUN apt-get -y install \
    autoconf \
    build-essential \
    cmake \
    debhelper \
    devscripts \
    fakeroot \
    git \
    libbladerf-dev \
    libboost-filesystem-dev \
    libboost-program-options-dev \
    libboost-regex-dev \
    libboost-system-dev \
    libhackrf-dev \
    liblimesuite-dev \
    libncurses5-dev \
    librtlsdr-dev \
    libusb-dev \
    libz-dev \
    openssl \
    patchelf \
    pkg-config \
    python3-build \
    python3-dev \
    python3-pip \
    python3-setuptools \
    python3-venv \
    python3-wheel \
    tcl8.6-dev && \
    apt-get clean

FROM install-build-deps AS build-dump1090-fa
WORKDIR /src
RUN git clone https://github.com/edgeofspace/dump1090-fa.git
WORKDIR /src/dump1090-fa
RUN ./prepare-build.sh bullseye
WORKDIR /src/dump1090-fa/package-bullseye
RUN dpkg-buildpackage -b --no-sign
RUN mkdir -p /opt/packages
RUN cp -f /src/dump1090-fa/*.deb /opt/packages

FROM install-build-deps AS build-rtl-sdr
WORKDIR /src
RUN git clone https://github.com/osmocom/rtl-sdr.git
WORKDIR /src/rtl-sdr
RUN mkdir build && \
    cd build && \
    cmake ../ && \
    make && \
    make install && \
    ldconfig

FROM runtime AS install
COPY --from=build-dump1090-fa /opt/packages /opt/packages
RUN apt -y install /opt/packages/*.deb && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
COPY --from=build-rtl-sdr /usr/local/bin/ /usr/local/bin/
COPY --from=build-rtl-sdr /usr/local/include/ /usr/local/include/
COPY --from=build-rtl-sdr /usr/local/lib/ /usr/local/lib/

FROM install AS optimize
RUN mkdir -p /opt/dump1090-fa
##RUN /usr/share/dump1090-fa/generate-wisdom && cp -f /tmp/*/wisdom.local /opt/dump1090-fa/wisdom.local
## OR
COPY --from=build-dump1090-fa /src/dump1090-fa/wisdom.generic wisdom.generic
RUN cp -f wisdom.generic /opt/dump1090-fa/wisdom.local

FROM install AS final
RUN mkdir -p /etc/dump1090-fa && mkdir -p /run/dump1090-fa
COPY --from=optimize /opt/dump1090-fa/wisdom.local /etc/dump1090-fa/wisdom.local
COPY --chmod=755 start-dump1090-fa.sh /srv/start-dump1090-fa.sh

#region lighttpd
COPY <<EOF /etc/s6-overlay/s6-rc.d/lighttpd/type
longrun
EOF
COPY --chmod=700 <<EOF /etc/s6-overlay/s6-rc.d/lighttpd/run
#!/command/execlineb -P
/usr/sbin/lighttpd -f /etc/lighttpd/lighttpd.conf -D
EOF
RUN touch /etc/s6-overlay/s6-rc.d/user/contents.d/lighttpd
#endregion lighttpd

# TCP raw output listen port
EXPOSE 30002
# TCP BaseStation output listen port
EXPOSE 30003
# TCP Beast input listen ports
EXPOSE 30004
EXPOSE 30104
# TCP Beast output listen port
EXPOSE 30005
# Lighttpd HTTP server
EXPOSE 80

HEALTHCHECK --start-period=5s --interval=30s --timeout=5s --retries=3 CMD ["bash", "-c", "cat < /dev/null > /dev/tcp/localhost/30005"]
ENTRYPOINT [ "/init" ]
CMD [ "/srv/start-dump1090-fa.sh" ]