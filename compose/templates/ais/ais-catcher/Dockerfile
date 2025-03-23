FROM ghcr.io/jvde-github/ais-catcher:v0.61 AS base
RUN apt-get update && \
    apt-get install -y curl nano wget && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
COPY --chmod=755 start-ais-catcher.sh /srv/start-ais-catcher.sh
COPY ais-catcher-plugins /usr/share/aiscatcher/my-plugins
ARG TARGETPLATFORM
ARG TARGETARCH
ARG TARGETVARIANT
RUN printf "I'm building for TARGETPLATFORM=${TARGETPLATFORM}" >/srv/target \
    && printf ", TARGETARCH=${TARGETARCH}" >>/srv/target \
    && printf ", TARGETVARIANT=${TARGETVARIANT} \n" >>/srv/target \
    && printf "With uname -s : ">>/srv/target && uname -s >>/srv/target \
    && printf "and  uname -m : ">>/srv/target && uname -m >>/srv/target
RUN echo ${TARGETPLATFORM} > /srv/targetplatform

ENV AIS_CATCHER_PORT="8100"
ENV STATION_NAME="AIS-Catcher"
ENV STATION_URL="https://google.com"
ENV DEVICE_INDEX=00000001
ENV BIASTEE=off

HEALTHCHECK --start-period=5s --interval=30s --timeout=5s --retries=3 CMD ["bash", "-c", "cat < /dev/null > /dev/tcp/localhost/$AIS_CATCHER_PORT"]
ENTRYPOINT [ "/srv/start-ais-catcher.sh" ]
