@echo off
setlocal
cd /d "C:\Users\17044\OneDrive\Documents\Hermes Agent"

:: Start the messaging gateway in a new background window
echo Starting Hermes Gateway (Telegram Bot)...
start "Hermes Gateway" .\venv\Scripts\python.exe hermes gateway run

:: Start the Web Dashboard in a new background window
echo Starting Hermes Dashboard...
start "Hermes Dashboard" .\venv\Scripts\python.exe hermes dashboard --no-open

:: Give the gateway and dashboard a few seconds to initialize
timeout /t 3 /nobreak >nul

:: TUI disabled by default (lighter on older PCs)
:: To use TUI occasionally, run: .\venv\Scripts\python.exe hermes --tui
:: echo Starting Hermes TUI...
.\venv\Scripts\python.exe hermes --tui

:: No pause needed when TUI is disabled