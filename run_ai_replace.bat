@echo off
REM Тихий запуск AI Replace для привязки к кнопке мыши в Logitech Options+
REM Лог пишется самим Python-скриптом в ai_replace.log
cd /d "%~dp0"
start "" /B pythonw.exe "%~dp0ai_replace.py"