# Threat Model

## Assets

- Immich API keys and the shared application token
- person names, thumbnails and transient embeddings
- album membership and synchronization history

## Trust boundaries

Browser → Family Tools → configured Immich servers. The TrueNAS host and its
storage are trusted. Other LAN devices are not implicitly trusted.

## Main threats and controls

- **Unauthorised LAN access:** shared-token login and signed HttpOnly session
- **API-key disclosure:** keys never appear in browser responses or logs
- **Cross-site requests:** SameSite session cookie, Same-Origin policy and CSP
- **SSRF:** URL validation, blocked unsafe address classes and disabled redirects
- **Over-sharing:** only selected match participants receive album access
- **Concurrent mutation:** per-album locks, preflight checks and idempotency guards
- **Configuration corruption:** schema validation, atomic replacement and backup
- **Dependency compromise:** lockfiles, CI audits, Dependabot and container scans

Residual risk: local HTTP does not protect traffic from a hostile LAN observer.
Use local HTTPS when that risk matters.
