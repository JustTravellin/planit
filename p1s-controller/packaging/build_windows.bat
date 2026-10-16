@echo off
rem Builds the Windows app and, if Inno Setup is installed, the installer.
rem Run from the p1s-controller folder:  packaging\build_windows.bat
setlocal
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate
pip install -e ".[ui]" pyinstaller || exit /b 1
pyinstaller --noconfirm --distpath dist --workpath build packaging\p1s-gui.spec || exit /b 1
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if exist %ISCC% (
  %ISCC% packaging\installer.iss || exit /b 1
  echo Installer written to dist\P1S-Controller-Setup.exe
) else (
  echo Inno Setup not found; the app folder is in dist\P1S Controller
)
