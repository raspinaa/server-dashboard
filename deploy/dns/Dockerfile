FROM debian:trixie-slim@sha256:a29215f6a35e51e22adffa17f89e9d2ef06214e64a2bad10d765c46aea49f11f
# apt keeps archive-signature verification; optional enterprise CA supports proxy builds.
RUN --mount=type=secret,id=enterprise_ca,target=/usr/local/share/ca-certificates/enterprise-ca.crt \
    apt-get update && apt-get install -y --no-install-recommends ca-certificates && \
    update-ca-certificates --fresh && \
    sed -i s,http://deb.debian.org,https://deb.debian.org,g /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends dnsmasq-base && \
    rm -rf /var/lib/apt/lists/*
EXPOSE 53/tcp 53/udp
ENTRYPOINT ["dnsmasq","--keep-in-foreground","--conf-file=/etc/dnsmasq.conf"]
