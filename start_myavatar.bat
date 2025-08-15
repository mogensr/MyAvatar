@echo off
echo ========================================
echo    MyAvatar Development Environment
echo ========================================
echo.

REM Change to MyAvatar directory
cd /d "C:\Brugere\mogen\Projects\python\CHATGPT\MyAvatar"

REM Activate virtual environment
call venv\Scripts\activate

REM Show current status
echo Current Directory: %CD%
echo Virtual Environment: ACTIVE
echo Git Branch:
git branch --show-current 2>nul || echo "Not a git repository or git not available"
echo.

REM Set window title
title MyAvatar Development - %CD%

REM Keep command prompt open
cmd /k
