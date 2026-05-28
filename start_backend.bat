@echo off
title Road ID System - Backend
echo ============================================
echo  Road Identification System - Backend
echo ============================================
echo.

cd /d "%~dp0"

echo [1/2] Starting FastAPI server on port 8000...
start "FastAPI - Road ID" cmd /k "cd /d %~dp0backend && ..\\.venv\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 3 /nobreak >nul

echo [2/2] Starting Celery worker...
start "Celery Worker - Road ID" cmd /k "cd /d %~dp0backend && ..\\.venv\Scripts\celery.exe -A celery_app worker --loglevel=info --pool=solo -Q video_processing"

echo.
echo ============================================
echo  Backend started successfully!
echo  FastAPI:  http://localhost:8000
echo  API Docs: http://localhost:8000/docs
echo ============================================
echo.
echo Make sure Redis is running on localhost:6379
echo Make sure MongoDB is running on localhost:27017
echo.
pause
