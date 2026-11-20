# syntax=docker/dockerfile:1
#
# Prometheus exporter for the Mosquitto broker, built from the vendored copy of
# github.com/sapcc/mosquitto-exporter in this directory (see README.md). Runs as a sidecar next to
# the broker in clusters/production/apps/mosquitto-production/.
#
# Updates: Dependabot bumps the golang and distroless digests and the Go modules in go.mod;
# .github/workflows/build-mosquitto-exporter.yml builds and scans the PR, and a
# mosquitto-exporter-v* tag publishes the image.

# Static Go build. Cross-compiles on the build platform, so a multi-arch build needs no QEMU.
FROM --platform=$BUILDPLATFORM golang:1.27.3-alpine3.24@sha256:fa3d596898d9f126af7c01d14ee7597bab3f39cccf392ef36b69fe77cd681f18 AS build
ARG TARGETOS
ARG TARGETARCH
# Passed by the reusable docker workflows: the release version and the commit.
ARG APP_VERSION=develop
ARG GIT_SHA=HEAD
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY *.go ./
RUN CGO_ENABLED=0 GOOS=$TARGETOS GOARCH=$TARGETARCH go build -trimpath \
    -ldflags="-s -w -X main.Version=${APP_VERSION} -X main.GITCOMMIT=${GIT_SHA}" \
    -o /out/mosquitto_exporter .

# Distroless static: CA certificates and a minimal /etc/passwd, no shell or package manager. Runs as
# 65532 (nonroot) unless the pod sets runAsUser.
FROM gcr.io/distroless/static-debian13:nonroot@sha256:aafe993665bf6200db38a02c11a9351e782a84b6a45e7f33b6695638c88e3931 AS final
COPY --from=build /out/mosquitto_exporter /mosquitto_exporter
EXPOSE 9234
ENTRYPOINT ["/mosquitto_exporter"]
