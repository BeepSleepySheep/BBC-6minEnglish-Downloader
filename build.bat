@echo off
REM ============================================================
REM  BBC 6 Minute English downloader - one-click build script
REM  Flow: install deps -> SVG to hi-res ICO -> PyInstaller exe
REM  Run: double click build.bat, or execute in cmd/PowerShell
REM  Output: dist\bbc-6minenglish-downloader-windows-x64.exe
REM ============================================================
setlocal
cd /d "%~dp0"
set "EXE_NAME=bbc-6minenglish-downloader-windows-x64"

echo [1/4] Installing / updating dependencies...
python -m pip install --upgrade pip -q || goto :err
python -m pip install -r requirements.txt -q || goto :err
python -m pip install pyinstaller svglib reportlab rlPyCairo pillow -q || goto :err

echo [2/4] Converting SVG to hi-res ICO...
python build_icon.py || goto :err

echo [3/4] Building executable with PyInstaller...
pyinstaller -F --clean --noconfirm -n %EXE_NAME% -i bbc6min_teal.ico bbc_6minute_english_downloader.py || goto :err

echo [4/4] Build finished!
echo Executable: %~dp0dist\%EXE_NAME%.exe
echo Tip: attach dist\%EXE_NAME%.exe to the GitHub Release.
goto :eof

:err
echo.
echo Build failed. Check the error messages above.
exit /b 1
