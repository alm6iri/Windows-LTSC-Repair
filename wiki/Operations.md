# Operations and Safety

## Before starting

1. Confirm the requested repair and the target machine.
2. Verify that you are authorized to administer the system.
3. Save work, create or verify backups, and ensure recovery media is available.
4. Run platform detection and confirm Windows/elevation before starting a repair.
5. Explain expected disruption and wait time to the operator.

## MCP tools

| Tool | Purpose | Notes |
|---|---|---|
| `detect_platform` | Read-only platform/elevation details | Run before repair calls. |
| `run_network_repair` | Network stack maintenance | May interrupt connectivity; restart may be required to apply all changes. |
| `run_update_repair` | Windows Update component maintenance | Services/cache are handled by the repair module; inspect every event. |
| `run_time_repair` | Windows Time registration/synchronization | Check reported command outcomes and final status. |
| `run_system_repair` | System file/component-store checks | May be long-running and resource-intensive. |
| `run_disk_repair` | Disk health checks and conditional scheduling | Follow returned events; do not assume a scan scheduled or completed. |
| `reboot_system(confirm)` | Request a system restart | Only call with `confirm: true` after explicit, current operator approval. |

The reboot tool is not covered by the repair lock. Never request a reboot while a repair is active; the caller must enforce this sequencing.

The tool registry and implementation in `mcp_server.py` are authoritative. This table is a navigation aid, not a promise of exact parameters or response fields.

## Response handling

Inspect the complete response, especially `status`, `events`, `error`, `target_system`, and any operation-specific details.

- `success`: code path returned success. Independently test the original symptom.
- `busy`: a repair is active in this MCP server process. Never run in parallel or try to bypass the lock. Wait for completion; retry at most once if it is still appropriate.
- `blocked`: a platform or elevation precondition failed. Stop and fix the environment through an authorized path.
- `failed`: inspect the returned exception and event trail; don't replay a potentially partial system mutation blindly.
- `rejected`: a guard declined the request. Respect it and explain what approval or precondition is missing.

Status values can differ among operation paths. Follow actual payload fields rather than assuming every response has the same shape.

## Reboot policy

A reboot can lose unsaved work and disrupt remote access. Explain the consequence and get explicit approval for an immediate restart in the current interaction. Pass `confirm: true` only after approval. The tool response indicates the shutdown command's result, not that Windows completed the subsequent startup.

## GUI workflow

The desktop app provides network, update, time, system, disk, and reboot controls. Its log records events and supports English/Arabic display. Review the log and test the requested outcome after each operation. Don't start a second repair while the first is active.

## Troubleshooting sequence

1. Record Windows edition/build, Python or executable version, elevation, and exact symptom.
2. Run detection and inspect its returned details.
3. Choose one relevant repair and preserve its complete event output.
4. If blocked or busy, stop and resolve the stated condition; never circumvent it.
5. After completion, perform a low-risk verification of the original symptom.
6. Report what changed, what was verified, what remains uncertain, and whether a reboot was authorized.

For bugs, see [Development](Development.md). For security vulnerabilities, follow `SECURITY.md`; do not publish exploit details in public issues.
