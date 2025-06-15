REM === MyAvatar_Complete.bat ===
REM Starter automatisk NGROK tunnel og aktiverer Python-miljø med MyAvatar-server

@echo off
echo ========================================
echo 🚀 Starter MyAvatar Server og NGROK
echo ========================================
echo.

REM Start NGROK i separat CMD-vindue
start cmd /k "cd /d C:\Users\mogen\Projects\python\CHATGPT\MyAvatar && ngrok http 8000"

REM Aktiver Python-miljø og start server i separat CMD-vindue
start cmd /k "cd /d C:\Users\mogen\Projects\python\CHATGPT\MyAvatar && call venv\Scripts\activate.bat && uvicorn portal.main:app --reload"

echo ========================================
echo 🌐 MyAvatar startet! Kig i de to åbne CMD-vinduer.
echo ========================================
pause