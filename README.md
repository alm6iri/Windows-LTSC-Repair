# Windows LTSC Repair Tool 🛠️

An enterprise-grade graphical user interface (GUI) automation utility designed natively using **Python** and **CustomTkinter** to diagnose and repair deep operating system failures unique to Windows 10 LTSC, Enterprise, and mainstream editions—all without compromising or deleting user files.

## Project Architecture & Methodology 🧠
Unlike basic batch scripts that execute linear commands blindly, this tool interacts natively with the Windows Registry Core sub-layers and service infrastructures using localized programmatic threads (`threading.Thread`) to keep the interface highly responsive and entirely lag-free during intense maintenance workflows.

## Key Core Functionalities ⚡
- **Asynchronous Deep Network Stack Reset:** Forced re-injection of vital registry entries for `NlaSvc` (Network Location Awareness) and `CDPSvc`, which are notorious for dropping off or crashing structural network panels. It programmatically triggers physical motherboard interface cards through low-level `WMIC` queries to eliminate ghosting.
- **Aggressive Windows Update Purge:** Safely stops locked cryptographic/update processes (`wuauserv`, `cryptSvc`, `bits`), flushes corrupt databases (`SoftwareDistribution` & `catroot2`), and forces continuous verification synchronization.
- **Atomic Time Calibration:** Re-registers the system's inner hardware clock module directly against the atomic global timeserver `://windows.com`.
- **Dynamic Structural Mirroring (RTL/LTR):** High-utility dynamic UI layout rendering that instantly switches interface anchors, logs, alignment behaviors, and controls depending on language selection.

## Compilation Commands (Source Deployment) 📦
To isolate and build the final executable asset (`.exe`) with built-in Administrative manifest controls (`requireAdministrator`) and your custom multi-resolution icon framework:

```bash
pip install customtkinter pyinstaller
pyinstaller --noconfirm --onefile --windowed --uac-admin --icon="app_icon.ico" FixTools.py
```
