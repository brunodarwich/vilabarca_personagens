@echo off
setlocal

REM ============= Run Streamlit dashboard =============
REM Determine script directory
set "SCRIPT_DIR=%~dp0"

REM Prefer venv Python if available
set "VENV_PY=%SCRIPT_DIR%.venv\Scripts\python.exe"
if exist "%VENV_PY%" (
  set "PY=%VENV_PY%"
) else (
  where python >nul 2>&1
  if %ERRORLEVEL%==0 (
    for /f "delims=" %%i in ('where python') do set "PY=%%i"
  ) else (
    echo [ERRO] Python nao encontrado. Crie a venv em "%SCRIPT_DIR%.venv" ou instale Python 3.12.
    pause
    exit /b 1
  )
)

set "STREAMLIT_BROWSER_GATHER_USAGE_STATS=false"
pushd "%SCRIPT_DIR%"
"%PY%" -m streamlit run "%SCRIPT_DIR%app.py"
popd

endlocal
