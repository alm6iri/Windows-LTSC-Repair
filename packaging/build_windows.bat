@echo off
REM =====================================================================
REM  Windows-LTSC-Repair - one-command release build (run on Windows)
REM  Produces: dist\Windows-LTSC-Repair.exe  (onefile, windowed,
REM            requireAdministrator manifest, multi-resolution icon)
REM =====================================================================
setlocal
cd /d "%~dp0.."

echo [1/4] Checking Python...
python --version || goto :fail

echo [2/4] Installing build dependencies...
python -m pip install --upgrade pip || goto :fail
python -m pip install -r requirements.txt pyinstaller || goto :fail

echo [3/4] Running the test suite (build aborts on failure)...
python -m unittest discover -s tests -v || goto :fail

echo [4/4] Building the executable...
python -m PyInstaller --noconfirm --clean Windows-LTSC-Repair.spec || goto :fail

if not exist "dist\Windows-LTSC-Repair.exe" goto :fail

for %%A in ("dist\Windows-LTSC-Repair.exe") do echo. & echo BUILD OK: dist\Windows-LTSC-Repair.exe  [%%~zA bytes]
exit /b 0

:fail
echo.
echo BUILD FAILED - see the log above.
exit /b 1
