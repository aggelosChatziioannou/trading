@echo off
REM GOLD TACTIC — Windows Task Scheduler Setup
REM Creates a scheduled task that runs every 5 minutes, 24/7
REM
REM Usage: Right-click this file → Run as Administrator

echo ========================================
echo   GOLD TACTIC - Task Scheduler Setup
echo ========================================
echo.

REM Delete existing task if any
schtasks /delete /tn "GOLD_TACTIC_Runner" /f >nul 2>&1

REM Create new task: every 5 minutes, no end date, run whether logged in or not
schtasks /create ^
  /tn "GOLD_TACTIC_Runner" ^
  /tr "\"C:\Users\chris\Desktop\Aggelos_Trading\run_cycle.bat\"" ^
  /sc minute /mo 5 ^
  /st 00:00 ^
  /ri 5 ^
  /du 9999:59 ^
  /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ✅ Task Scheduler created successfully!
    echo.
    echo   Name:      GOLD_TACTIC_Runner
    echo   Schedule:  Every 5 minutes, 24/7
    echo   Action:    run_cycle.bat → analyst_runner.py
    echo.
    echo   The system will:
    echo   - Check current zone (NIGHT/ASIA/LONDON/NY/EVENING)
    echo   - Run cycle ONLY when next_cycle.json says it's time
    echo   - Use Claude CLI for analysis
    echo   - Send results to Telegram
    echo.
    echo   To stop:   schtasks /delete /tn "GOLD_TACTIC_Runner" /f
    echo   To check:  schtasks /query /tn "GOLD_TACTIC_Runner"
    echo.
) else (
    echo.
    echo ❌ Failed to create task. Try running as Administrator.
    echo    Right-click this file → Run as Administrator
    echo.
)

pause
