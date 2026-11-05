# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.3.x   | :white_check_mark: |
| < 2.3   | :x:                |

## Reporting a Vulnerability

This tool runs with **administrator privileges** and modifies Windows system
state (services, registry, Update cache, event logs). Vulnerabilities in this
project are treated as high severity by default.

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, report them privately:

1. Open a **private security advisory** via the repository's
   *Security → Advisories → New draft security advisory* page, or
2. Email the maintainer at **alm6iri@users.noreply.github.com** with the
   subject prefix `[security]`.

Include as much of the following as possible:

- The affected version/commit
- Step-by-step reproduction
- Impact assessment (what system state can be modified or disclosed)
- Any suggested fix

You will receive an acknowledgment within **72 hours**. Fixes are coordinated
via a private branch, credited in the release notes, and disclosed publicly
after a patched version ships.

## Security Design Invariants

Contributors must preserve these invariants (enforced by tests in
`tests/test_core.py`):

1. **No privilege escalation.** The tool must never add service accounts
   (NetworkService, LocalService, etc.) to the `Administrators` group.
2. **Valid configuration only.** NTP hosts must be valid DNS hostnames;
   `Start` registry values must only be written after service re-registration
   completes.
3. **Scoped destructive operations.** Cache deletion is restricted to
   verified, allow-listed paths via `commonpath` validation.
4. **No shell-string command construction.** External commands use explicit
   argument lists with bounded timeouts.
