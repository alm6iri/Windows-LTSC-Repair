# Windows LTSC Repair

Windows LTSC Repair is a Windows maintenance utility with a CustomTkinter desktop
interface, a platform-independent repair core, and an optional MCP server for
agent-driven operations. The project is designed for explicit, observable
repair workflows rather than opaque automation.

[Open the bilingual project portal](docs/index.html) for the product overview,
operation guide, safety notes, and architecture. Select **EN / AR** in the page
to switch language; Arabic content uses right-to-left layout.

> **License update:** this repository is now governed by the Personal and
> Internal Use License in [`LICENSE`](LICENSE) for material the maintainer has
> authority to license under these terms. Internal business use is permitted;
> commercial redistribution, resale, sublicensing, and third-party service
> delivery require separate written permission. Previous MIT grants remain
> valid for copies received under MIT. Third-party and contributor-owned
> material retains its applicable rights and notices. This is source-available,
> not an OSI-approved open-source license. Consult counsel about relicensing.

## Features

- Windows 10/11 maintenance, including LTSC-oriented platform handling.
- Repair modules for network, Windows Update, time synchronization, system
  integrity, and disk health.
- Structured logging and Arabic/English application strings.
- MCP server (`mcp_server.py`) uses MCP SDK v1.28+ `FastMCP` and exposes seven tools with structured responses, platform/elevation checks, and a reboot gate.
- 76 unit tests that mock Windows-specific behavior; Windows-only skips are reported separately.

## Safety

This software invokes privileged Windows operations. Review the code and terms,
run only on systems you are authorized to administer, and ensure backups and
recovery options are available. Repair operations may interrupt connectivity or
run for an extended period. A successful tool response means its implementation
returned successfully; verify the original system symptom separately.

The MCP server checks platform and elevation for repair operations. It permits
only one repair at a time per server process. `reboot_system` requires
`confirm: true`; obtain explicit user approval before requesting a restart.

## Run from source

```bash
python -m pip install -r requirements.txt
python FixTool.py
```

Run `FixTool.py` on Windows. The GUI may request administrator elevation.

## MCP server

Install the MCP dependency from `requirements.txt` (`mcp>=1.28,<2`). The server uses the Python MCP SDK v1.28+ `FastMCP` implementation at `mcp.server.fastmcp` and registers seven tools:

```json
{
  "mcpServers": {
    "windows-ltsc-repair": {
      "command": "python",
      "args": ["/absolute/path/to/mcp_server.py"]
    }
  }
}
```

Use an elevated host only on an authorized Windows system. The service checks
platform/elevation and returns structured results. It does not replace human
approval for a reboot.

## Build

The Windows executable is built on Windows; PyInstaller does not cross-compile.
Run `packaging\build_windows.bat` to install build requirements, run tests, and
produce `dist\Windows-LTSC-Repair.exe`.

## Verify

```bash
python -m compileall -q .
python -m unittest discover -s tests -v
ruff check .
ruff format --check .
```

CI runs the unit suite on Windows and Ubuntu with Python 3.11, 3.12, and 3.13,
and checks Ruff lint/format on Ubuntu with Python 3.12.

## Documentation

- [Project portal, EN/AR](docs/index.html)
- [Wiki: Welcome](wiki/Welcome.md)
- [Operations and safety](wiki/Operations.md)
- [Architecture and development](wiki/Development.md)
- [License](LICENSE)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
