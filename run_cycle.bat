@echo off
REM GOLD TACTIC — Single Cycle Runner
REM Called by Windows Task Scheduler every 5 minutes
REM Runs analyst_runner.py which decides zone, tier, and timing

cd /d "C:\Users\chris\Desktop\Aggelos_Trading"

REM Use Python from known path
"C:\Users\chris\AppData\Local\Programs\Python\Python313\python.exe" GOLD_TACTIC\scripts\analyst_runner.py --cli claude

exit /b %ERRORLEVEL%
