@echo off
REM Quick setup script for Vishwa on Windows

echo ============================================================
echo Vishwa Quick Setup
echo ============================================================
echo.

REM Check Python version
echo [1/5] Checking Python version...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

python --version
echo.

REM Create virtual environment
echo [2/5] Creating virtual environment...
if not exist venv (
    python -m venv venv
    echo Created venv
) else (
    echo venv already exists
)
echo.

REM Activate virtual environment
echo [3/5] Activating virtual environment...
call venv\Scripts\activate.bat
echo.

REM Install dependencies
echo [4/5] Installing Vishwa and dependencies...
pip install -e . --quiet
if errorlevel 1 (
    echo [ERROR] Installation failed
    pause
    exit /b 1
)
echo Installed successfully
echo.

REM Check configuration
echo [5/5] Checking configuration...
if not exist .env (
    echo Creating .env from template...
    copy .env.example .env >nul
    echo [!] Please edit .env and add your API keys
    echo     ANTHROPIC_API_KEY=sk-ant-...
    echo     or
    echo     OPENAI_API_KEY=sk-...
    echo.
) else (
    echo .env file exists
)

echo.
echo ============================================================
echo Setup Complete!
echo ============================================================
echo.
echo Next steps:
echo   1. Edit .env file and add your API key
echo   2. Run: vishwa check
echo   3. Try: vishwa "list all Python files"
echo.
echo To activate virtual environment later:
echo   venv\Scripts\activate
echo.
pause
