FROM debian:bookworm AS base
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

FROM runtime AS install-dump1090-fa
COPY tar1090-build-data /run/dump1090-fa
RUN apt-get -y install nginx && \
    bash -c "$(wget -nv -O - https://github.com/wiedehopf/tar1090/raw/master/install.sh)" && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

FROM install-dump1090-fa AS final
RUN /bin/echo -e "server {\n    listen 80 default_server;\n" > /etc/nginx/sites-enabled/default && \
    cat /usr/local/share/tar1090/nginx-tar1090.conf >> /etc/nginx/sites-enabled/default && \
    /bin/echo -e "\n\n}\n" >> /etc/nginx/sites-enabled/default && \
    mkdir -p /run/tar1090
COPY --chmod=755 start-tar1090.sh /srv/start-tar1090.sh

#region nginx
COPY <<EOF /etc/s6-overlay/s6-rc.d/nginx/type
longrun
EOF
COPY --chmod=700 <<EOF /etc/s6-overlay/s6-rc.d/nginx/run
#!/command/execlineb -P
nginx -g "daemon off;"
EOF
RUN touch /etc/s6-overlay/s6-rc.d/user/contents.d/nginx
#endregion nginx

ENV HISTORY_SIZE=450
ENV INTERVAL=8
ENV CHUNK_SIZE=60
ENV PTRACKS=8
ENV GZIP_LVL=1
ENV ENABLE_978=no
ENV URL_978=""

# nginx http port
EXPOSE 8080

HEALTHCHECK --start-period=5s --interval=30s --timeout=5s --retries=3 CMD ["bash", "-c", "cat < /dev/null > /dev/tcp/localhost/80"]
ENTRYPOINT [ "/init" ]
CMD [ "/srv/start-tar1090.sh" ]