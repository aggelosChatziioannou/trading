# ============================================================
# GOLD TACTIC - Scheduled Tasks UNINSTALLER + Process Killer
# ============================================================
# Removes ALL \GoldTactic\* Windows scheduled tasks
# AND kills any running claude/cmd/python processes that were
# spawned by gt-asset-selector.cmd / gt-market-monitor.cmd.
# ============================================================

# ---------- Self-elevate ----------
$currentIdentity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "==> Self-elevate (expect UAC prompt)..." -ForegroundColor Yellow
    $scriptPath = $MyInvocation.MyCommand.Path
    if (-not $scriptPath) { $scriptPath = $PSCommandPath }
    Start-Process -FilePath "powershell.exe" `
        -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-File","`"$scriptPath`"" `
        -Verb RunAs
    exit
}

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Red
Write-Host " GOLD TACTIC - SCHEDULED TASKS UNINSTALLER" -ForegroundColor Red
Write-Host "============================================================" -ForegroundColor Red
Write-Host ""

$TaskPath = "\GoldTactic\"

# ============================================================
# STEP 1 - List existing tasks
# ============================================================
Write-Host "[1/4] Searching for existing \GoldTactic\* tasks ..." -ForegroundColor Yellow
$tasks = @(Get-ScheduledTask -TaskPath $TaskPath -ErrorAction SilentlyContinue)
if ($tasks.Count -eq 0) {
    Write-Host "  (no Windows scheduled tasks found)" -ForegroundColor DarkGray
} else {
    Write-Host ("  Found {0} tasks:" -f $tasks.Count) -ForegroundColor Cyan
    foreach ($t in $tasks) {
        Write-Host ("    - {0}  [State: {1}]" -f $t.TaskName, $t.State)
    }
}
Write-Host ""

# ============================================================
# STEP 2 - Stop any currently-running tasks
# ============================================================
Write-Host "[2/4] Stop running tasks ..." -ForegroundColor Yellow
$running = @($tasks | Where-Object { $_.State -eq 'Running' })
if ($running.Count -eq 0) {
    Write-Host "  (no tasks in Running state)" -ForegroundColor DarkGray
} else {
    foreach ($t in $running) {
        try {
            Stop-ScheduledTask -TaskName $t.TaskName -TaskPath $TaskPath -ErrorAction Stop
            Write-Host ("  * Stopped: {0}" -f $t.TaskName) -ForegroundColor Green
        } catch {
            Write-Host ("  ! Could not stop {0}: {1}" -f $t.TaskName, $_.Exception.Message) -ForegroundColor Red
        }
    }
}
Write-Host ""

# ============================================================
# STEP 3 - Kill lingering wrapper processes
# ============================================================
Write-Host "[3/4] Killing lingering cmd/claude/python processes from wrappers ..." -ForegroundColor Yellow

$killPatterns = @(
    "gt-asset-selector",
    "gt-market-monitor",
    "GOLD_TACTIC\\prompts\\asset_selector",
    "GOLD_TACTIC\\prompts\\market_monitor",
    "GOLD_TACTIC/prompts/asset_selector",
    "GOLD_TACTIC/prompts/market_monitor"
)

$killed = 0
try {
    $procs = Get-CimInstance Win32_Process -ErrorAction Stop |
        Where-Object { $_.CommandLine } |
        Where-Object {
            $cl = $_.CommandLine
            ($killPatterns | ForEach-Object { $cl -like "*$_*" }) -contains $true
        }

    if ($procs) {
        foreach ($p in $procs) {
            try {
                Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop
                Write-Host ("  x Killed PID {0} [{1}]" -f $p.ProcessId, $p.Name) -ForegroundColor Green
                $killed++
            } catch {
                Write-Host ("  ! PID {0} could not be terminated: {1}" -f $p.ProcessId, $_.Exception.Message) -ForegroundColor DarkYellow
            }
        }
    } else {
        Write-Host "  (no processes found with matching command line)" -ForegroundColor DarkGray
    }
} catch {
    Write-Host ("  ! WMI query failed: {0}" -f $_.Exception.Message) -ForegroundColor Red
}
Write-Host ("  Total processes terminated: {0}" -f $killed) -ForegroundColor Cyan
Write-Host ""

# ============================================================
# STEP 4 - Unregister tasks
# ============================================================
Write-Host "[4/4] Unregistering tasks from Task Scheduler ..." -ForegroundColor Yellow
if ($tasks.Count -eq 0) {
    Write-Host "  (nothing to remove)" -ForegroundColor DarkGray
} else {
    foreach ($t in $tasks) {
        try {
            Unregister-ScheduledTask -TaskName $t.TaskName -TaskPath $TaskPath -Confirm:$false -ErrorAction Stop
            Write-Host ("  - Removed: {0}" -f $t.TaskName) -ForegroundColor Green
        } catch {
            Write-Host ("  ! Could not remove {0}: {1}" -f $t.TaskName, $_.Exception.Message) -ForegroundColor Red
        }
    }
}
Write-Host ""

# ============================================================
# Verification
# ============================================================
Write-Host "Verification ..." -ForegroundColor Yellow
$remaining = @(Get-ScheduledTask -TaskPath $TaskPath -ErrorAction SilentlyContinue)
if ($remaining.Count -eq 0) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " OK - No more \GoldTactic\* scheduled tasks" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "GOLD TACTIC pipeline stopped." -ForegroundColor Cyan
    Write-Host "To re-enable it later, run install-all.ps1." -ForegroundColor Cyan
    $exitCode = 0
} else {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host (" WARN: {0} tasks remain -- see errors above" -f $remaining.Count) -ForegroundColor Red
    Write-Host "============================================================" -ForegroundColor Red
    $remaining | Format-Table TaskName,State -AutoSize
    $exitCode = 1
}

Write-Host ""
Read-Host "Press Enter to close"
exit $exitCode
