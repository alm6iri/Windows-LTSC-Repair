# Windows-LTSC-Repair v2.3.1

**Release date:** 2026-11-05 · **Tag:** `v2.3.1` · **Tests:** 75/75 passed (4 platform-specific skips)

The first tagged stable release of the Windows LTSC Repair Toolkit. This release consolidates the 2.3.x hardening cycle and ships the first official binary build.

## ✨ Highlights

### Windows 11 25H2 Support
- Detection and repair logic extended to Windows 11 25H2 builds, with a dead-import invariant guarding against registry/API drift.

### Headless & Agent-Friendly Operation
- Full headless execution path (no GUI windows, no blocking prompts) for CI and automation.
- New **MCP Server** (`mcp_server.py`) exposing network, time, system, update, and disk repair operations as structured tools callable by AI agents (Claude, Cline, Cursor).

### Bilingual UI (EN / AR)
- Complete RTL/LTR mirroring and template-structure invariants for the Arabic interface.

## 🛠 Fixes (2.3.0 → 2.3.1)

- **v2.3.1** — Repaired two broken runtime guards; fixed a real file-descriptor leak in the headless path.
- **v2.2.3** — Completed RTL/LTR mirroring and template-structure invariants.
- **v2.2.2** — Fixed operation ordering, error visibility, and manifest/code consistency.
- Service-time re-registration ordering hardened (`start` type written after re-registration).
- Privileged service accounts are no longer added to `Administrators` (security hardening).
- AppX re-registration scoped strictly to Shell Experience — no blanket re-registration.
- Valid NTP hostnames enforced for time synchronization.

## 🧪 Quality

- Mutation-validated test suite: 75 unit tests covering the UAC/elevation boot path, six-scenario E2E pipeline, thread-safety and data-integrity guards, reverse-coverage invariants (dead keys, structure symmetry, class shadowing), and cross-platform green on Windows hosts.
- Platform detection and service-state fallback tests hardened for real Windows hosts.

## 📦 Assets

| File | Description |
|---|---|
| `Windows-LTSC-Repair.exe` | Standalone executable (PyInstaller, ~13.9 MB). Run as Administrator for full repair capability. |

## ⚠️ Requirements

- Windows 10/11 (LTSC and Consumer SKUs supported, up to 25H2)
- Administrator (UAC elevation) privileges for repair operations
- SmartScreen may warn on first run for unsigned binaries — verify the SHA-256 checksum published with the release.

---

**Full changelog:** https://github.com/alm6iri/Windows-LTSC-Repair/commits/v2.3.1
