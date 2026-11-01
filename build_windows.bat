@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Сначала запустите start_windows.bat.
 pause
 exit /b 1
)
.venv\Scripts\python.exe -m pip install pyinstaller
if errorlevel 1 goto error
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed --name MusicTagger music_tagger.py
if errorlevel 1 goto error
echo Готово: dist\MusicTagger.exe. Этот файл можно запускать без Python.
pause
exit /b 0
:error
echo Сборка не выполнена. Подробности ошибки выше.
pause
exit /b 1
