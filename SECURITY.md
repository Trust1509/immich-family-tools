# Security Policy

## Supported versions

Security fixes are provided for the latest release. Version 1.2.0 is the first
release with the hardened shared-token authentication flow.

## Reporting a vulnerability

Use GitHub's private vulnerability reporting for this repository. Do not open a
public issue containing API keys, tokens, private URLs, faces, logs, or account
data. Include affected version, reproduction steps, impact, and suggested
mitigation when available.

## Deployment boundary

Immich Family Tools is designed for a trusted private network. Internet exposure
requires HTTPS and an authenticated reverse proxy. Never publish the application
port directly to the internet.
