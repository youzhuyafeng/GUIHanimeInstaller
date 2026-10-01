@echo off
REM 打包 hanime_installer.py 为单文件可执行程序，产物在 dist\ 目录下。
setlocal

cd /d "%~dp0"

echo [1/3] 安装依赖...
python -m pip install -r requirements.txt || goto :error

echo [2/3] 清理旧的构建产物...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist HanimeInstaller.spec del /q HanimeInstaller.spec

echo [3/3] 使用 PyInstaller 打包...
python -m PyInstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name HanimeInstaller ^
    --hidden-import yt_dlp ^
    --collect-all yt_dlp ^
    hanime_installer.py || goto :error

echo.
echo 打包完成：dist\HanimeInstaller.exe
goto :eof

:error
echo.
echo 打包失败，请检查上面的错误信息。
exit /b 1
