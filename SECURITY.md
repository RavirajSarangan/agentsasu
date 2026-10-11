# Security Policy

Sasu can control a whole Mac, so we take security reports seriously.

## Reporting a vulnerability

Please **don't open a public issue**. Use GitHub's private reporting:
<https://github.com/RavirajSarangan/agentsasu/security/advisories/new>

Include what you found, how to reproduce it, and the impact. You'll get a reply within 7 days.
Please give us a reasonable time to fix it before disclosing.

## In scope

- Commands running without the owner's voice, approval or Touch ID
- Prompt injection that gets past the untrusted-content rules, leak guard or trap files
- Reading another user's data, the voiceprint, memory or AI keys
- The local server accepting connections or commands it shouldn't
- Tampering with the activity log without detection

## Supported versions

Only the latest release on `main` gets security fixes.

## Design

The security model is described in [README.md](README.md#security) and [docs/architecture.md](docs/architecture.md).
