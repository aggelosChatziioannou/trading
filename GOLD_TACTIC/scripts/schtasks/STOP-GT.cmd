@echo off
REM ============================================================
REM  GOLD TACTIC — One-click KILL & UNINSTALL
REM  Κάνε double-click αυτό το αρχείο.
REM  Θα ανοίξει PowerShell ως Administrator (UAC prompt),
REM  θα σταματήσει τα running tasks, θα σκοτώσει τα processes,
REM  και θα σβήσει τα 7 Windows scheduled tasks.
REM ============================================================

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall-all.ps1"
