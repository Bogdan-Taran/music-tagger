@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto dependencies
where py >nul 2>nul
if errorlevel 1 goto usepython
py -3 -m venv .venv
if errorlevel 1 goto error
goto dependencies
:usepython
python -m venv .venv
if errorlevel 1 goto error
:dependencies
.venv\Scripts\python.exe -c "import mutagen, PIL" >nul 2>nul
if not errorlevel 1 goto launch
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto error
:launch
start "" ".venv\Scripts\pythonw.exe" "music_tagger.py"
exit /b 0
:error
echo Не удалось запустить приложение. Установите Python 3.11 или новее с python.org.
echo При первой установке библиотек нужен интернет. Подробности ошибки выше.
pause
exit /b 1
