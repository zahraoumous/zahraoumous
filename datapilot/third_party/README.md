# MinIO release provenance

Version: RELEASE.2025-09-07T16-13-09Z
Source: https://github.com/minio/minio/tree/07c3a429bfed433e49018cb0f78a52145d4bedeb
License: AGPL-3.0, copied unchanged from the source release.

The Dockerfile downloads official Linux amd64/arm64 release binaries and verifies the upstream SHA-256 values, retrieved from the corresponding `.sha256sum` release assets over verified HTTPS. Only amd64 was executed in this environment; arm64 is configured but untested.

The image is built locally because the published `minio/minio` image could not be pulled. Review upstream license/source availability requirements before redistribution or deployment.
