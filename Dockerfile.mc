FROM alpine:3.21

ARG TARGETARCH
ARG MC_RELEASE=RELEASE.2025-04-16T18-13-26Z

RUN apk add --no-cache ca-certificates curl \
    && case "$TARGETARCH" in amd64|arm64) ;; *) echo "Unsupported architecture: $TARGETARCH" >&2; exit 1 ;; esac \
    && curl -fsSL "https://dl.min.io/client/mc/release/linux-${TARGETARCH}/archive/mc.${MC_RELEASE}" -o /usr/local/bin/mc \
    && chmod +x /usr/local/bin/mc

ENTRYPOINT ["/usr/local/bin/mc"]
