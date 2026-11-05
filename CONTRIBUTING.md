# Contributing to Windows-LTSC-Repair

Thank you for considering a contribution! This project follows standard
open-source engineering practices. Please read this guide before opening a
pull request.

## How to Contribute

1. **Fork** the repository and create your branch from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```
2. **Make your changes** following the coding standards below.
3. **Run the test suite** locally and ensure it passes:
   ```bash
   python -m unittest discover -s tests -v
   ```
4. **Commit** with a clear, descriptive message using
   [Conventional Commits](https://www.conventionalcommits.org/):
   ```bash
   git commit -m "fix(core): prevent service deadlock on repeated runs"
   ```
5. **Push** and open a pull request against `main`.

## Coding Standards

- All Python code must run on the minimum supported Python version
  (see `pyproject.toml` for the exact floor).
- Every new feature or bug fix **must include or update unit tests**.
- Prefer explicit argument lists over shell-string concatenation when
  invoking external commands.
- Keep module responsibilities narrow: one concern per module under
  `repair_core/`.
- Do not introduce any command that modifies system state without a
  corresponding test asserting the exact command shape.

## Pull Request Checklist

- [ ] Tests pass (`python -m unittest discover -s tests`)
- [ ] New/changed behavior is covered by tests
- [ ] `README.md` updated if behavior or usage changed
- [ ] Commit messages follow Conventional Commits
- [ ] No system-modifying commands added without a safety guard test

## Reporting Bugs

Open an issue using the **Bug Report** template. Include:

- Windows version and edition (LTSC or otherwise)
- Python version
- Full log output from the tool
- Minimal steps to reproduce

## License

By contributing, you agree that your contributions will be licensed under
the [MIT License](LICENSE) that covers this project.
