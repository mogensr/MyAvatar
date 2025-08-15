@echo off
echo.
echo ================================================
echo   MyAvatar BackgroundFX Database Update
echo ================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python or add it to your PATH
    pause
    exit /b 1
)

REM Check if we're in the right directory
if not exist "app\db\database.py" (
    echo ERROR: This script must be run from your MyAvatar project root directory
    echo Current directory: %CD%
    echo Expected to find: app\db\database.py
    echo.
    echo Please navigate to your MyAvatar project folder and run this script again
    pause
    exit /b 1
)

echo Found MyAvatar project structure
echo Running database update script...
echo.

REM Run the Python script
python update_videos_table.py

REM Check if the script ran successfully
if errorlevel 1 (
    echo.
    echo ERROR: Database update script failed
    pause
    exit /b 1
)

echo.
echo Script completed successfully!
pause