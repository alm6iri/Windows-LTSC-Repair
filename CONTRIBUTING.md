# Contributing to Windows-LTSC-Repair

This repository is maintained for personal and internal use. Read `LICENSE`
before copying, modifying, sharing, or contributing code.

## Contribution workflow

1. Create a branch from `main`.
2. Make a focused change and add or update tests for behavior changes.
3. Run the local verification commands:

   ```bash
   python -m compileall -q .
   python -m unittest discover -s tests -v
   ruff check .
   ruff format --check .
   ```

4. Review `git diff --check` and remove generated files, logs, binaries, and
   secrets.
5. Use a Conventional Commit message and open a pull request against `main`.

## Engineering standards

- Keep repair logic in the narrowest appropriate module under `repair_core/`.
- Use explicit subprocess argument lists; never construct shell command strings
  from user input.
- Bound external commands with timeouts and preserve the single-operation lock.
- Do not add system-mutating commands without a test asserting their exact
  command shape and safety preconditions.
- Preserve platform guards, elevation checks, archive safeguards, and the
  explicit reboot confirmation gate.

## Commercial and distribution restrictions

Contributions do not grant permission to commercially redistribute, resell,
sublicense, host, or package this project. Any use outside personal or internal
organizational use requires a separate written license from the copyright holder.
See `LICENSE` for the controlling terms.

## Security reports

Do not disclose vulnerabilities in public issues. Use a private GitHub security
advisory or the contact process in `SECURITY.md`.
