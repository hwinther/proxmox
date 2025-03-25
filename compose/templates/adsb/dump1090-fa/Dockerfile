ARG DOCKER_REGISTRY=ghcr.io/hwinther/proxmox/
FROM ${DOCKER_REGISTRY}sdr-base-wsh:bullseye AS runtime
FROM ${DOCKER_REGISTRY}sdr-build-wsh:bullseye AS build

FROM build AS build-dump1090-fa
WORKDIR /src
RUN git clone https://github.com/edgeofspace/dump1090-fa.git
WORKDIR /src/dump1090-fa
RUN ./prepare-build.sh bullseye
WORKDIR /src/dump1090-fa/package-bullseye
RUN dpkg-buildpackage -b --no-sign
RUN mkdir -p /opt/packages
RUN cp -f /src/dump1090-fa/*.deb /opt/packages

FROM runtime AS install
COPY --from=build-dump1090-fa /opt/packages /opt/packages
RUN apt -y install /opt/packages/*.deb && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
COPY --from=build-dump1090-fa /usr/local/bin/ /usr/local/bin/
COPY --from=build-dump1090-fa /usr/local/include/ /usr/local/include/
COPY --from=build-dump1090-fa /usr/local/lib/ /usr/local/lib/

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