@echo off
title Road ID System - Frontend
echo ============================================
echo  Road Identification System - Frontend
echo ============================================
echo.

cd /d "%~dp0frontend"
start "Frontend - Road ID" cmd /k "npm run dev"

echo.
echo ============================================
echo  Frontend started!
echo  URL: http://localhost:5173
echo ============================================
echo.
pause
