@echo off
REM ============================================
REM ОТЛАДОЧНЫЙ ЗАПУСК AI Replace
REM Запустите этот файл вручную двойным кликом,
REM чтобы увидеть окно консоли со всеми сообщениями.
REM ============================================

REM Переключаем консоль на UTF-8
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo  AI Replace — DEBUG MODE
echo  Folder: %~dp0
echo  Time: %date% %time%
echo ============================================
echo.

echo [CHECK] Python...
python --version
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found in PATH!
    echo Install Python from python.org, check "Add Python to PATH"
    pause
    exit /b 1
)

echo [CHECK] Files...
if not exist "%~dp0ai_replace.py" (
    echo [ERROR] ai_replace.py not found
    pause
    exit /b 1
)
if not exist "%~dp0config.json" (
    echo [ERROR] config.json not found
    pause
    exit /b 1
)
if not exist "%~dp0.env" (
    echo [ERROR] .env not found — create it from .env.example
    pause
    exit /b 1
)

echo [CHECK] keyboard library...
python -c "import keyboard; print('keyboard OK')" 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] keyboard not installed. Run: pip install keyboard
)

echo.
echo [RUN] Starting ai_replace.py...
echo ----------------------------------------
python "%~dp0ai_replace.py"
set EXITCODE=%ERRORLEVEL%
echo ----------------------------------------

echo.
echo [RESULT] Script exited with code: %EXITCODE%

echo.
echo [LOG FILE] ai_replace.log:
echo ----------------------------------------
type "%~dp0ai_replace.log" 2>nul
echo ----------------------------------------

echo.
echo Press any key to exit...
pause >nul