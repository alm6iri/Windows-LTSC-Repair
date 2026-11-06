# Architecture and Development

## Repository map

```text
FixTool.py                  desktop UI, elevation, DPI, operation dispatch
mcp_server.py               MCP registration, structured responses, reboot gate
repair_core/
  platform_info.py          Windows edition/build/elevation detection
  runner.py                 bounded subprocess runner and service/archive helpers
  network_repair.py         Winsock/IP, adapter, and scoped AppX behavior
  update_repair.py          verified service stop, archive, rebuild flow
  time_repair.py            Windows Time registration and resync
  system_repair.py          DISM/SFC flow and output decoding
  disk_repair.py            SMART/CHKDSK flow and conditional scheduling
  eventlog.py               thread-safe event storage and file mirror
  strings.py                Arabic/English message tables
  __init__.py               engine version and package exports
tests/test_core.py          cross-platform unit and invariant tests
tests/mutation_audit.py     mutation regression harness
```

## Design invariants

- Repair modules use explicit argument lists; do not add shell-string construction.
- External commands have bounded timeouts and structured outcomes.
- One operation runs at a time in the GUI/server process.
- Platform-specific behavior is guarded so the suite runs on non-Windows CI.
- Service configuration is conditional on service availability and ordering.
- Cache maintenance archives known directories before cleanup where implemented.
- Reboot is explicit and separately gated.
- The English and Arabic string tables remain symmetric and placeholder-compatible.
- Tests assert command shape, ordering, safety boundaries, and source integrity.

## Development loop

1. Read the affected module and its tests.
2. Reproduce the issue with the narrowest test or command.
3. Add/update a focused test for changed behavior.
4. Make the smallest implementation change.
5. Run:

   ```bash
   python -m compileall -q .
   python -m unittest discover -s tests -v
   ruff check .
   ruff format --check .
   ```

6. Inspect `git diff --check` and the full diff.
7. Use a focused Conventional Commit message.

## Adding a repair action

- Define a narrow module function with the existing runner/event conventions.
- Add exact command and precondition assertions to `tests/test_core.py`.
- Add Arabic and English messages with identical placeholder arity.
- Wire the GUI only after the core behavior is testable.
- Add an MCP wrapper only if the tool has a clear structured contract.
- Document risk and post-operation verification in `wiki/Operations.md` and `README.md`.

## Release checks

CI tests Python 3.11–3.13 on Windows and Ubuntu and runs Ruff checks on Ubuntu. Build the executable on Windows only. Do not describe a build, release, checksum, or green remote workflow unless it was actually verified.

## Licensing boundary

Source notices point to the Personal and Internal Use License in the repository root. That license restricts commercial redistribution, public distribution, resale, sublicensing, and third-party service delivery unless separately authorized in writing. Dependencies remain under their own licenses. Review the full license before distributing any copy or derivative.
