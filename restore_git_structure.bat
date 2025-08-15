@echo off
echo ========================================
echo   MyAvatar Git Structure Restoration
echo ========================================
echo.

REM Step 1: Navigate to MyAvatar directory
cd /d "C:\Brugere\mogen\Projects\python\CHATGPT\MyAvatar"

REM Step 2: Initialize new Git repository
echo Initializing new Git repository in MyAvatar...
git init

REM Step 3: Add all current files (including your dashboard changes)
echo Adding all files...
git add .

REM Step 4: Create initial commit with your changes
echo Creating initial commit...
git commit -m "Restored MyAvatar as independent repository with dashboard 3D Avatars update"

REM Step 5: Add Railway remote (replace with your actual Railway Git URL)
echo Adding Railway remote...
echo NOTE: You need to add your Railway Git remote URL manually:
echo git remote add origin YOUR_RAILWAY_GIT_URL
echo.

REM Step 6: Show status
echo Current status:
git status
echo.
echo Git log:
git log --oneline -3

echo.
echo ========================================
echo   Restoration Complete!
echo   Next: Add Railway remote and push
echo ========================================
pause
