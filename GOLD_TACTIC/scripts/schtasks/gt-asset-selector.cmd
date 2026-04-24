@echo off
setlocal
set "GT_BASE=C:\Users\aggel\Desktop\trading"
set "GT_LOG=%USERPROFILE%\.claude\logs\gt-asset-selector.log"
cd /d "%GT_BASE%"
echo [%date% %time%] Asset-Selector START >> "%GT_LOG%" 2>&1
claude --model claude-sonnet-4-6 -p "Read GOLD_TACTIC/prompts/asset_selector.md and execute exactly." --allowedTools "Bash,Read,Write,Grep,Glob" >> "%GT_LOG%" 2>&1
set RC=%ERRORLEVEL%
echo [%date% %time%] Asset-Selector END rc=%RC% >> "%GT_LOG%" 2>&1
exit /b %RC%
