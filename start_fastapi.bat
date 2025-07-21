@echo off
SETLOCAL EnableDelayedExpansion

REM ##################################################################################
REM # Bu betik, FastAPI sunucunuzu otomatik olarak başlatmak için kullanılır.       #
REM # Detaylı hata ayıklama logları 'batch_debug.log' dosyasına yazılacaktır.      #
REM ##################################################################################

SET LOG_FILE="C:\Users\m.r4sid\OneDrive\Masaüstü\onmuhasebe\batch_debug.log"

REM Her başlatmada yeni bir log kaydı için tarih ve saat ekle
ECHO. >> %LOG_FILE%
ECHO --- Starting start_fastapi.bat (%DATE% %TIME%) --- >> %LOG_FILE%
ECHO Current directory before CD: %CD% >> %LOG_FILE%

REM 1. Projenizin ana dizinine gidin. Bu, 'api' klasörünüzün bulunduğu dizindir.
CD /D "C:\Users\m.r4sid\OneDrive\Masaüstü\onmuhasebe" 2>> %LOG_FILE%
IF %ERRORLEVEL% NEQ 0 (
    ECHO ERROR: Failed to change directory to project root. ErrorLevel: %ERRORLEVEL% >> %LOG_FILE%
    EXIT /B %ERRORLEVEL%
)
ECHO Changed to directory: %CD% >> %LOG_FILE%

REM Define the full path to python.exe in the virtual environment
SET PYTHON_EXE="C:\Users\m.r4sid\OneDrive\Masaüstü\onmuhasebe\api_env\Scripts\python.exe"
ECHO Python executable path: %PYTHON_EXE% >> %LOG_FILE%

REM Check if Python executable exists
IF NOT EXIST %PYTHON_EXE% (
    ECHO ERROR: Python executable not found at %PYTHON_EXE% >> %LOG_FILE%
    EXIT /B 1
)
ECHO Python executable found. >> %LOG_FILE%

REM Run the FastAPI application
REM Standart çıktı ve hata çıktısını log dosyasına yönlendir
%PYTHON_EXE% -m uvicorn api.api_ana:app --host 127.0.0.1 --port 8001 >> %LOG_FILE% 2>&1
IF %ERRORLEVEL% NEQ 0 (
    ECHO ERROR: Uvicorn command failed. ErrorLevel: %ERRORLEVEL% >> %LOG_FILE%
    EXIT /B %ERRORLEVEL%
)

ECHO --- start_fastapi.bat finished successfully --- >> %LOG_FILE%
