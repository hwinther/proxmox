FROM debian:buster AS base
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
    autoconf-archive \
    build-essential \
    cmake \
    debhelper \
    devscripts \
    dh-exec \
    dh-systemd \
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
    pkg-config && \
    apt-get clean

FROM install-build-deps AS build-opensky
WORKDIR /src
RUN git clone https://github.com/openskynetwork/opensky-sensor.git
WORKDIR /src/opensky-sensor
RUN dpkg-buildpackage -b --no-sign && \
    mkdir -p /opt/packages && \
    cp -f /src/opensky-feeder_*.deb /opt/packages && \
    cp -f /src/libopensky-c++1_*.deb /opt/packages
RUN ar vx /src/opensky-feeder_*.deb && \
    tar -C /tmp -Jxpf data.tar.xz && \
    mkdir -p /opt/bin && \
    cp -f /tmp/usr/bin/openskyd-dump1090 /opt/bin/openskyd-dump1090

FROM runtime AS install
# COPY --from=build-opensky /opt/packages /opt/packages
# RUN dpkg -i /opt/packages/*.deb && \
#     apt-get -y -f install && \
#     apt-get clean && \
#     rm -rf /var/lib/apt/lists/*
COPY --from=build-opensky /opt/bin/openskyd-dump1090 /usr/bin/openskyd-dump1090

# RUN apt-get -y install gnupg2 && \
#     wget -q  -O - https://opensky-network.org/files/firmware/opensky.gpg.pub | apt-key add - && \
#     echo deb https://opensky-network.org/repos/debian opensky custom > /etc/apt/sources.list.d/opensky.list && \
#     apt-get update -y && \
#     apt-get -y install opensky-sensor && \
#     apt-get clean && \
#     rm -rf /var/lib/apt/lists/*

FROM install AS final
COPY --chmod=755 start-opensky.sh /srv/start-opensky.sh

ENV RECEIVER_HOST="dump1090-fa"
ENV RECEIVER_PORT="30005"
ENV OPENSKY_DEVICE_TYPE="default"

#HEALTHCHECK --start-period=5s --interval=30s --timeout=5s --retries=3 CMD ["bash", "-c", "cat < /dev/null > /dev/tcp/localhost/30005"]
ENTRYPOINT [ "/init" ]
CMD [ "/srv/start-opensky.sh" ]