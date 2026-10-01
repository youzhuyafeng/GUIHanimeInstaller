@echo off
REM Build hanime_installer.py into a single-file executable: dist\HanimeInstaller.exe
REM NOTE: keep this file ASCII-only and CRLF-terminated. cmd.exe parses .bat files
REM using the OEM codepage, so non-ASCII text here turns into mojibake.
setlocal

cd /d "%~dp0"

REM Prefer "py -3" (picks the newest 3.x, since yt-dlp deprecated 3.9); fall back to "python".
set "PY=python"
where py >nul 2>nul && set "PY=py -3"

%PY% --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10 or newer:
    echo         https://www.python.org/downloads/
    echo         Remember to tick "Add Python to PATH" during installation.
    exit /b 1
)

echo Using interpreter: %PY%
%PY% --version

echo [1/3] Installing dependencies...
%PY% -m pip install -r requirements.txt || goto :error

echo [2/3] Cleaning previous build output...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist HanimeInstaller.spec del /q HanimeInstaller.spec

echo [3/3] Packaging with PyInstaller...
%PY% -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name HanimeInstaller ^
    --collect-all yt_dlp ^
    hanime_installer.py || goto :error

echo.
echo Build finished: dist\HanimeInstaller.exe
goto :eof

:error
echo.
echo Build failed. Please check the error messages above.
exit /b 1
