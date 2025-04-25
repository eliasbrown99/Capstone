@echo off
REM ───────────────────────────────────────────────────────────────
REM   Capstone one-click launcher (Windows)
REM   • prompts for OPENAI_API_KEY and LLAMA_CLOUD_API_KEY
REM   • sets up venv + npm, then runs backend & frontend
REM ───────────────────────────────────────────────────────────────

pushd %~dp0

REM 0) create .env if missing
if not exist .env (
    echo .env not found — creating it.
    echo:> .env
)

REM 0.1) helper :prompt_if_missing
:prompt_if_missing
    :: %1 = KEY_NAME, %2 = PROMPT_TEXT
    findstr /C:"%1=" .env >nul 2>nul
    if %errorlevel% neq 0 (
        echo.
        set /p _val=%2
        echo %1=%_val%>> .env
    )
    goto :eof

call :prompt_if_missing OPENAI_API_KEY     "Enter your OpenAI API key: "
call :prompt_if_missing LLAMA_CLOUD_API_KEY "Enter your LLAMA Cloud API key: "

echo.
type .env | findstr "="
echo.

REM 1) create venv if necessary
if not exist venv (
    echo Creating Python virtual environment ...
    python -m venv venv
)

REM 2) activate venv
call venv\Scripts\activate

REM 3) backend deps
echo Installing backend requirements ...
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

REM 4) frontend deps
if not exist solicitation-frontend\node_modules (
    echo Installing frontend packages ...
    cd solicitation-frontend
    if exist package-lock.json (
        npm ci --no-fund --silent
    ) else (
        npm install --no-fund --silent
    )
    cd ..
)

REM 5) run both services together
echo Starting FastAPI (port 8000) and Vite dev server (port 3000) ...
npx concurrently ^
  "python -m app.main" ^
  "npm --prefix solicitation-frontend run dev" ^
  --name "backend,frontend" ^
  --prefix-colors "cyan,magenta"

popd
