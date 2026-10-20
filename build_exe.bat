@echo off
rem Build CodeReader.exe with PyInstaller (run in WinPython Command Prompt).
rem Messages are ASCII only so they are not garbled by the console code page.
cd /d "%~dp0"
python -m pip install -r requirements.txt pyinstaller || goto :error
python -m pytest --disable-warnings -q || goto :error
python -m PyInstaller --noconfirm code_reader.spec || goto :error
echo.
echo Build OK: dist\CodeReader\CodeReader.exe
echo Copy the whole dist\CodeReader folder to distribute.
pause
exit /b 0
:error
echo.
echo Build FAILED. See the messages above.
pause
exit /b 1
