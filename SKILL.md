---
name: windows-ltsc-repair
description: Operate and maintain the Windows repair engine and its seven MCP tools with evidence-led diagnostics, bounded recovery, explicit reboot consent, and verified engineering workflows.
version: 2.3.1
license: MIT
entrypoint: mcp_server.py
---

# Windows LTSC Repair: Engineering and Operations Skill

Use this skill when operating, diagnosing, testing, or changing this repository's Windows repair engine or MCP server. Treat system repair as high impact. Describe only guarantees supported by current source and observed tool results.

## Source of Truth

The checked-out code and tests outrank this document. Before making claims or changes, inspect the relevant implementation and verify current line-level behavior.

- Engine version: `repair_core/__init__.py`
- MCP tools, schemas, response fields, statuses, and elevation checks: `mcp_server.py`
- Command execution, timeouts, service control, and archive operations: `repair_core/runner.py`
- Repair sequences: `repair_core/*_repair.py`
- Platform detection: `repair_core/platform_info.py`
- Cross-platform tests: `tests/test_core.py`
- CI contract: `.github/workflows/ci.yml`
- User instructions and release details: `README.md`, `SECURITY.md`, `CONTRIBUTING.md`

Do not reuse old response examples, test counts, versions, editions, checksums, or release claims without checking them against current code or a fresh command.

## Operating Contract

### Establish target and intent

- Identify the requested diagnosis or repair. Do not infer permission for unrelated operations or run every repair “just in case.”
- For MCP system operations, call `detect_platform` first. Inspect the actual result for supported platform, edition/build, and elevation.
- If detection fails, reports a non-Windows host, or does not establish required elevation, stop before repair. Report the observed blocker; never route around platform or privilege checks.
- For repository engineering, inspect repository root, branch, `git status`, and existing diffs before edits. Preserve unrelated work.

### Interpret tool results from evidence

The current server uses the following statuses in different paths:

- `success`: the code reached its success return. Inspect events and tool-specific fields. This alone does not prove the user's symptom is resolved.
- `busy`: the process-wide in-memory lock was held. Do not run another repair concurrently or bypass the lock. Wait for the active call to finish; retry only if the goal remains current, with a bounded retry policy.
- `blocked`: platform or administrator preconditions failed. Stop and report the returned reason.
- `failed`: an exception was converted to a structured failure. Inspect `error` and `events`; distinguish returned diagnostics from independently verified system state.
- `rejected`: a guard refused the operation, including a reboot request without `confirm: true`. Respect the refusal. Never mutate arguments to evade a guard.

Inspect available fields such as `events`, `error`, `target_system`, `details`, and tool-specific extras; field presence varies by tool and status. Quote relevant diagnostics accurately. Do not claim a reboot is required or a repair succeeded unless the result supports that statement.

### Sequence, recovery, and retries

- Only one repair may run at a time in this server process. This is not a distributed lock across machines or server instances.
- Choose the least invasive operation that addresses the symptom. Explain material disruption or long runtime before starting.
- Network repair may interrupt connectivity; system and disk repair may run for a long time. Let the tool's bounded timeouts and internal sequencing operate.
- A `success` result indicates that the operation returned successfully according to its code. It does not independently verify connectivity, Windows Update, system integrity, or disk health afterward.
- On timeout, `busy`, or failure, report the exact result. Do not blindly replay a partially completed repair. Retry only when transient cause is supported, repeat is safe, and the user’s goal still applies. Bound retries; no indefinite loops.
- Do not invent shell commands to imitate or bypass repair tools. In code changes, subprocess calls must be argument-list based, bounded where appropriate, and covered by focused tests when they modify system state.

### Reboot consent

`reboot_system` is destructive and has a code-level boolean gate. Call it only after the user clearly approves an immediate restart in the current context. Warn that unsaved work may be lost and the machine will restart. Pass `confirm: true` only after explicit approval; never infer consent from a repair request, old context, or an agent policy.

The server checks administrator status and runs the Windows shutdown command. A `success` result means the command scheduled a restart, not that the machine completed rebooting.

## Repository Engineering Workflow

### Phase 1: Inspect

1. Confirm repository root, branch, clean/dirty state, and current diffs.
2. Read relevant implementation, tests, CI workflow, and project guidance before proposing a cause.
3. For CI failures, inspect the failed job logs. Record the failing step, OS/interpreter, exact diagnostic, and whether other matrix jobs pass.
4. Separate confirmed facts from hypotheses. Do not overwrite unrelated or concurrent user changes.

### Phase 2: Reproduce and localize

1. Run the narrowest deterministic command that reproduces the reported issue.
2. Form a falsifiable root-cause hypothesis and test it against implementation and test behavior.
3. For defects, add or update a focused regression test when practical. Confirm it detects the defect before changing implementation.
4. Keep unrelated refactors out of a narrow fix. Expand scope only when the acceptance criteria require it.

### Phase 3: Change

1. Make the smallest coherent change that follows local patterns.
2. Keep platform-specific behavior guarded and testable on non-Windows CI.
3. Preserve safety properties: explicit argument lists, bounded timeouts, platform/elevation checks, process lock, and reboot confirmation.
4. Never add credentials, tokens, private keys, or sensitive machine data to files, tests, output, or this skill.
5. Mock platform-specific APIs in tests; never execute real destructive repair operations as a test.

### Phase 4: Verify

Run the repository CI checks from its root using a compatible Python and Ruff version:

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
ruff check . --output-format=github
ruff format --check .
```

If any check cannot run, report the exact command and blocker. Never report it as passing. When a check fails, preserve its full output, isolate the smallest relevant case, fix the underlying cause rather than weakening assertions, and rerun the focused and full checks.

Before commit:

- Review `git diff --check`, `git diff --stat`, and the full diff for scope and accidental edits.
- Confirm every changed file belongs to the task.
- Keep `SKILL.md` untouched unless the user explicitly requested a change; when it is untracked, do not stage it incidentally.
- Exclude caches, binaries, logs, local configuration, and credentials.

### Phase 5: Commit and synchronize

Commit or push only when requested or explicitly required. Stage explicit paths, inspect the staged diff, confirm the intended branch, and use a focused Conventional Commit message. After pushing, verify the remote commit and check the associated CI run. A local green result does not mean remote CI is green.

## Failure-Recovery Rules

- **Command fails:** retain the full error and exit code; inspect relevant state before retrying.
- **Automated edit changes unexpected files:** inspect the complete diff immediately. Restore only unintended edits made by this task; do not discard concurrent user work.
- **Test fails after a change:** determine whether behavior or test expectation is wrong. Do not change assertions merely to get a green suite.
- **Tool or dependency is missing:** inspect declared dependencies and CI setup. Install only the development tool needed; do not add it to runtime requirements without justification.
- **Push is rejected:** fetch and inspect remote divergence. Never force-push or rewrite shared history unless explicitly authorized.
- **Request crosses a safety boundary or lacks essential information:** stop at that boundary, explain the specific issue, and ask only the minimum clarifying question.

## Context Management

For long tasks, maintain a compact working note containing:

- Goal and acceptance criteria
- Repository path, branch, and starting commit
- Confirmed findings with evidence locations
- Changed files and rationale
- Commands run and exact results
- Remaining risks, blockers, and remote verification state

Update it after each meaningful phase. Keep facts and file references; discard disproven hypotheses. Never compress away approvals, failed checks, uncommitted changes, or whether a remote action completed. On resumption, re-check local and remote state instead of trusting old notes.

## Operational Boundaries

- This skill covers implemented repository capabilities, not malware removal, data recovery, third-party driver installation, arbitrary registry edits, or unsupported operating systems.
- Never promise that a repair is risk-free, guaranteed, or independently verified beyond returned evidence.
- Do not ask users to paste credentials into chat or expose secrets in output. Use an approved local authentication flow.
- Minimize diagnostic disclosure; redact credentials and personal identifiers from logs before sharing.

## Version and Release Discipline

The frontmatter version is documentation metadata. Verify it against `repair_core.__version__` before release work. Update this document when tested contracts change, but avoid duplicating large implementation excerpts that will drift. Publish claims about versions, tests, releases, artifacts, checksums, or CI only when freshly verified from source or a live command.
