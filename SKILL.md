---
name: windows-ltsc-repair
version: 2.3.1
description: Operate the v2.3.1 Windows repair engine through evidence-led, bounded, approval-aware workflows.
entrypoint: mcp_server.py
license: Personal and Internal Use License; see LICENSE.
---

# Windows LTSC Repair: Enterprise Operations Skill

Use this skill for authorized operation, diagnosis, integration, testing, and maintenance of this repository. Treat every repair as a high-impact system action. The implementation is authoritative; this document is an operating contract, not a replacement for source inspection, legal advice, or human authorization.

## Contract authority

Verify these sources before making a claim:

- `repair_core/__init__.py`: engine version and exported modules.
- `mcp_server.py`: actual MCP tools, input schema, response keys, lock scope, platform/elevation checks, and reboot gate.
- `repair_core/platform_info.py`: Windows detection, edition/build fields, availability, and elevation-related data used by callers.
- `repair_core/runner.py`: command arguments, timeouts, service control, archive/delete behavior, and command-result semantics.
- `repair_core/*_repair.py`: exact operation sequencing and `reboot_required` values.
- `repair_core/strings.py`: English/Arabic event templates.
- `tests/test_core.py`: tested invariants and cross-platform behavior.
- `.github/workflows/ci.yml`: supported CI matrix and quality gates.
- `LICENSE`, `THIRD_PARTY_NOTICES.md`, `SECURITY.md`: legal and security boundaries.

Never copy stale examples, test counts, release claims, checksums, supported editions, or response fields from an earlier document. Re-check the current files.

## Non-negotiable boundaries

- Operate only on a machine and data set the user is authorized to administer.
- Do not request or expose credentials, tokens, private keys, or sensitive machine data in chat or logs.
- Do not invent PowerShell, CMD, registry, service, or deletion commands. System mutation goes through the implemented repair tools and tested code paths.
- Do not bypass platform, elevation, lock, or confirmation checks.
- Do not promise that a repair is risk-free, guaranteed, or complete merely because a tool returned `success`.
- Do not run multiple repair operations concurrently in one MCP server process.
- Do not request a reboot while a repair is active. The server's repair lock does not protect `reboot_system`; callers must enforce this sequencing.
- This skill and repository are governed by a Personal and Internal Use License. Commercial redistribution, resale, sublicensing, and third-party service delivery require separate written permission. Previous MIT grants and third-party licenses remain governed by their own terms.

## Mandatory operating sequence

### Phase 1: Establish intent and preconditions

1. Identify the user's exact symptom and desired outcome.
2. Confirm the target host and that the user is authorized to administer it.
3. Call `detect_platform` before any repair operation.
4. Inspect its actual response, including `status`, `details`, `target_system`, and `events` when present.
5. Stop if the host is unavailable/non-Windows or if the required elevated context is not available. Report the returned reason; do not work around it.
6. Explain disruption, expected duration, possible reboot requirement, and the post-operation verification plan.

### Phase 2: Choose one operation

Select the narrowest relevant operation:

- `run_network_repair`: Winsock/IP reset, DNS flush, adapter handling, service configuration, and scoped AppX behavior. Expect connectivity interruption and possible reboot requirement.
- `run_update_repair`: verified update-service stop/start sequence and archive-based handling of update directories. Inspect archive and service events.
- `run_time_repair`: Windows Time service registration/configuration, peer setup, resync attempts, and status output.
- `run_system_repair`: DISM component-store repair followed by SFC decoding and verdict events. Long-running and resource-intensive.
- `run_disk_repair`: SMART best-effort reporting, online `chkdsk /scan`, and conditional repair/scheduling based on the returned result. Treat disk actions as high impact.
- `reboot_system(confirm)`: separate destructive action. It is not a repair and is not protected by the repair lock. Use only after explicit, current approval and only when no repair is active.

### Phase 3: Interpret the response

The common response builder currently returns keys including:

- `tool`
- `status`
- `engine_version`
- `duration_seconds`
- `events`
- `target_system`

Some responses add `details`, `error`, `reboot_recommended`, `reboot_required`, or `note`. Do not assume every key appears in every result. Events may include timestamps, levels, translated messages, and raw output.

Interpret statuses as follows:

- `success`: the function reached its success return. Inspect all events and extras, then independently verify the original symptom.
- `busy`: the process-wide non-blocking repair lock was held. Do not parallelize or force. Wait for the active operation; retry at most once if still relevant and safe.
- `blocked`: a platform or administrator precondition failed. Stop and report the exact reason.
- `failed`: an exception was returned in structured form. Preserve the error and event trail; do not blindly replay a partially completed operation.
- `rejected`: currently used by the reboot confirmation gate when `confirm` is false. Treat it as a final refusal until the missing explicit approval is obtained.

A nonzero subprocess result inside a repair can be represented by warning events while the top-level operation still returns `success`. Therefore, `success` is not proof that every subprocess succeeded. Read the event stream.

### Phase 4: Verify and close

1. Test the user's original symptom with a low-risk, relevant check.
2. Record what the tool changed or attempted, what the events prove, what remains uncertain, and whether a reboot was actually authorized.
3. If a reboot is recommended, ask separately for explicit approval. Never silently reboot.
4. Redact secrets, personal identifiers, paths that disclose sensitive information, and raw output not needed for the diagnosis.

## Recovery and retry policy

- Retry only when the returned evidence suggests a transient cause, the operation is safe to repeat, and the user's goal still applies.
- Use a finite retry budget. Never loop on `busy`, timeout, or failure indefinitely.
- After a partial or failed operation, inspect events and current state before choosing another operation.
- Do not automatically chain network, update, time, system, and disk repairs. Each operation can alter system state and has its own risk.
- If a repair fails after a service stop or archive attempt, report the partial state and recommend authorized operator inspection instead of hiding the failure.
- If the MCP server is unavailable, enter the bounded MCP Connection Recovery procedure below before reporting a blocker. Do not substitute ad hoc repair commands, request credentials, elevate privileges, or change Windows state to restore the connection.

## MCP Connection Recovery (Autonomous, Bounded)

Connection setup and repair-tool authorization are separate concerns. The agent may autonomously diagnose and repair its own MCP client/server initialization path; this never authorizes a Windows repair operation or reboot.

Perform this sequence once per failed connection episode, inside this skill's own operational context. Do not require the operator to load another skill for these steps. Use the `hermes mcp` subcommands documented by the installed CLI; do not invent reload verbs.

1. **Classify the failure.** Capture the exact client error and determine whether failure occurred before server startup, during SDK import, during transport initialization, or during tool discovery/call. Do not infer a server defect from a caller/tool-schema mismatch.
2. **Inspect registration and test transport.** Run `hermes mcp list`, identify the configured server name, and run `hermes mcp test <server-name>`. Inspect the exact result. A successful transport test is not proof that this chat session has registered the tools; verify that `detect_platform` is actually exposed in-session.
3. **Verify the launch configuration.** Read the matching MCP configuration entry. Check the configured command, arguments, working directory, environment activation, and target file. Resolve the Python executable used by the server process; do not assume shell `python` is the same interpreter.
4. **Verify runtime and import.** With the configured interpreter, check its version, installed `mcp` version, and `from mcp.server.fastmcp import FastMCP`. This repository declares `mcp>=1.28,<2`; it uses `FastMCP`, `@mcp.tool()`, and `mcp.run()`. Do not substitute `MCPServer` or guess an API path from another SDK generation.
5. **Self-heal the isolated environment.** If the configured project environment lacks the declared dependency or has an incompatible version, run that environment's Python with `-m pip install -r <repository-root>/requirements.txt`. Do not install into system Python, alter global PATH/configuration, remove unrelated packages, use an arbitrary package source, or modify dependency constraints merely to suppress the error. If the MCP host points elsewhere, correct only that server entry to the verified interpreter and repository path when the client/configuration tools provide a supported, local edit mechanism.
6. **Run non-mutating validation.** Run an import check using the configured interpreter, then run `python mcp_server.py --dump-schemas <temporary-path>`. Confirm the schema contains all seven expected tools: `detect_platform`, the five repair tools, and `reboot_system`. Delete the temporary output. Never invoke repair or reboot tools to test server startup.
7. **Reload/reconnect once.** Use `hermes mcp test <server-name>` again after fixing the environment/config. If the server process must be restarted, use the host's documented reload/restart control if available; otherwise perform one bounded restart of the MCP server through the client configuration. Do not claim that `hermes mcp test` restarts the server or injects newly discovered tools into an already-running chat. Re-check the tool list and verify `detect_platform` is exposed in-session.
8. **Stop at the boundary.** If recovery requires credentials, new privileges/elevation, an unavailable network/package source, permission changes, or a host configuration edit unavailable to this agent, do not bypass the boundary. After one failed restart, stop. Return the exact diagnostic, checks/fixes completed, and the minimum operator action needed; do not repeat the same failed repair.

After connection recovery, do not automatically invoke `detect_platform` or a repair just to test transport unless the user requested that diagnostic. Use schema export/import validation as the default non-mutating test. A disconnected MCP server is not permission to run equivalent shell commands against Windows.

## MCP integration

Run `mcp_server.py` with the Python MCP SDK v1.28+ (`mcp>=1.28,<2`). The server uses `mcp.server.fastmcp.FastMCP`, registers seven tools with `@mcp.tool()`, and serves them with `mcp.run()`. Do not substitute `MCPServer` from a different SDK generation.

To inspect the current function-calling schemas without starting a server:

```bash
python mcp_server.py --dump-schemas tools.json
```


### Network connectivity

1. `detect_platform`.
2. Explain that connectivity may drop.
3. Run `run_network_repair` once.
4. Inspect adapter, service, AppX, and command events.
5. Test connectivity independently.
6. Request reboot approval only if the result/reported symptom justifies it and no repair is active.

### Windows Update failure

1. `detect_platform`.
2. Run `run_update_repair` once.
3. Confirm service-start and archive events; do not claim a cache was archived unless an event says so.
4. Ask the user to retry Windows Update.
5. Treat any reboot as a separate approved action.

### Clock drift or TLS symptoms

1. `detect_platform`.
2. Run `run_time_repair`.
3. Inspect peer configuration, resync attempts, and status output.
4. Re-test time-dependent behavior independently.

### System corruption

1. `detect_platform`.
2. Warn about duration and resource use.
3. Run `run_system_repair`.
4. Read DISM/SFC verdict and raw diagnostic tail.
5. Do not claim corruption was repaired if the event verdict is partial, unknown, or failed.

### Disk health concern

1. Confirm backups and authorization.
2. `detect_platform`.
3. Warn that disk operations can be long-running and reboot-sensitive.
4. Run `run_disk_repair`.
5. Distinguish SMART unavailability, online scan status, errors found, and scheduled repair from one another.
6. Never interrupt an active filesystem repair casually.

### MCP/fleet integration

- Treat the process-wide lock as local to one server instance; add external coordination for multiple hosts or server processes.
- Capture structured responses as audit records while minimizing sensitive output.
- Use `dump_schemas()` to inspect the current function-calling schema rather than hardcoding a stale schema in a client.
- Keep human approval outside the model's private reasoning and record the approval boundary in the calling application.

## Development and change workflow

### Inspect

1. Check repository root, branch, status, and existing diff.
2. Read the affected module, its tests, CI workflow, and relevant license/security guidance.
3. For CI failures, capture the exact job, platform, interpreter, failing step, and full diagnostic.
4. Separate confirmed facts from hypotheses.

### Reproduce

1. Run the narrowest deterministic reproducer.
2. Add or update a focused regression test when practical.
3. Confirm the test detects the defect before modifying implementation.

### Implement

- Preserve explicit subprocess argv, bounded timeouts, platform guards, service ordering, archive safeguards, bilingual key symmetry, the one-repair lock, and reboot confirmation.
- Keep Python behavior unchanged when adding only legal notices or documentation headers.
- Do not weaken tests to hide a regression.

### Verify

From the repository root:

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
ruff check . --output-format=github
ruff format --check .
```

If a check cannot run, report the exact blocker and do not call it passing. Before any commit, inspect `git diff --check`, the full diff, and staged paths. Do not stage `SKILL.md`; it is a local operator artifact and must remain untracked.

## Version, evidence, and legal discipline

- Verify `repair_core.__version__` before changing the frontmatter version.
- The documented test count is a current repository fact only when freshly verified.
- Do not call the repository “enterprise-grade,” “commercial,” “guaranteed,” or “production-ready” as a technical guarantee. Use those as product positioning only when accurate and qualified.
- `LICENSE` is a source-available Personal and Internal Use License. It is not legal advice and cannot revoke prior grants or third-party rights.
- Keep local-only skill content out of `git add`, commits, pushes, releases, and public repository pages.
