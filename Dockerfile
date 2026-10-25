FROM debian:bookworm-slim AS build
RUN apt-get update -qq && apt-get install -y --no-install-recommends build-essential libcrypt-dev > /dev/null && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY mud/ ./
RUN make clean && make -j4 && chmod 755 rom

FROM debian:bookworm-slim
RUN apt-get update -qq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends libcrypt1 netcat-openbsd tzdata > /dev/null \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /var/lib/fd/areas /var/lib/fd/player/backup /var/lib/fd/player/backup2 /var/lib/fd/deleted /var/lib/fd/log
COPY --from=build /build/rom /usr/local/bin/fd
COPY mud/license.* /usr/share/doc/forgotten-dungeon/
COPY areas/*.are areas/area.lst areas/mobprog.prg areas/olc.hlp areas/clans.dat areas/config.dat areas/deity.dat areas/races.dat areas/music.txt areas/social.txt /var/lib/fd/areas/
RUN sed -i '/^#END/i Deny test\nDeny file\nDeny srcwrite' /var/lib/fd/areas/config.dat \
    && chown -R 10001:10001 /var/lib/fd
USER 10001:10001
ENV TZ=America/Los_Angeles
WORKDIR /var/lib/fd/areas
EXPOSE 4000
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s CMD nc -w 2 127.0.0.1 4000 </dev/null | grep -q 'Select your codepage:'
ENTRYPOINT ["/usr/local/bin/fd"]
CMD ["4000"]
