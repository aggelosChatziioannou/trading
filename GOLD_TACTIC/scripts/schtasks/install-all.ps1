# ============================================================
# GOLD TACTIC v7.2 — Windows Scheduled Tasks Installer
# ============================================================
# Εγκαθιστά 7 scheduled tasks κάτω από το folder \GoldTactic\
# Idempotent: αν υπάρχουν ήδη tasks, τα σβήνει και τα ξαναφτιάχνει.
#
# Χρήση (PowerShell as Administrator):
#   powershell -ExecutionPolicy Bypass -File ".\install-all.ps1"
# ============================================================

# ---------- Self-elevate ----------
$currentIdentity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal($currentIdentity)
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "==> Δεν τρέχεις ως Administrator — κάνω self-elevate..." -ForegroundColor Yellow
    $scriptPath = $MyInvocation.MyCommand.Path
    if (-not $scriptPath) { $scriptPath = $PSCommandPath }
    Start-Process -FilePath "powershell.exe" `
        -ArgumentList "-NoProfile","-ExecutionPolicy","Bypass","-File","`"$scriptPath`"" `
        -Verb RunAs
    exit
}

$ErrorActionPreference = "Stop"

# ---------- Configuration ----------
$BasePath     = "C:\Users\aggel\Desktop\trading"
$SelectorCmd  = "$BasePath\GOLD_TACTIC\scripts\schtasks\gt-asset-selector.cmd"
$MonitorCmd   = "$BasePath\GOLD_TACTIC\scripts\schtasks\gt-market-monitor.cmd"
$TaskPath     = "\GoldTactic\"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " GOLD TACTIC v7.2 — Scheduled Tasks Installer" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Base path     : $BasePath"
Write-Host "Selector cmd  : $SelectorCmd"
Write-Host "Monitor cmd   : $MonitorCmd"
Write-Host "Task folder   : $TaskPath"
Write-Host ""

# ---------- Sanity checks ----------
if (-not (Test-Path $SelectorCmd)) {
    Write-Host "ERROR: Λείπει $SelectorCmd" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
if (-not (Test-Path $MonitorCmd)) {
    Write-Host "ERROR: Λείπει $MonitorCmd" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Βεβαιώσου ότι υπάρχει το logs directory
$LogDir = Join-Path $env:USERPROFILE ".claude\logs"
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
    Write-Host "  + Created log dir: $LogDir" -ForegroundColor DarkGray
}

# ============================================================
# STEP 1 — Cleanup παλιών tasks
# ============================================================
Write-Host "[1/3] Cleanup παλιών tasks στο $TaskPath ..." -ForegroundColor Yellow
$oldTasks = Get-ScheduledTask -TaskPath $TaskPath -ErrorAction SilentlyContinue
if ($oldTasks) {
    foreach ($t in $oldTasks) {
        Write-Host ("  - Removing {0}" -f $t.TaskName) -ForegroundColor DarkGray
        Unregister-ScheduledTask -TaskName $t.TaskName -TaskPath $TaskPath -Confirm:$false
    }
    Write-Host ("  Removed {0} old task(s)" -f $oldTasks.Count) -ForegroundColor DarkGray
} else {
    Write-Host "  (δεν υπήρχαν παλιά tasks)" -ForegroundColor DarkGray
}
Write-Host ""

# ============================================================
# STEP 2 — Create 7 scheduled tasks
# ============================================================
Write-Host "[2/3] Δημιουργία 7 scheduled tasks ..." -ForegroundColor Yellow

# Common settings
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 15)

# Run as current (non-admin) user — το wrapper θέλει %USERPROFILE% του αληθινού χρήστη
$principal = New-ScheduledTaskPrincipal `
    -UserId ("{0}\{1}" -f $env:USERDOMAIN, $env:USERNAME) `
    -LogonType Interactive `
    -RunLevel Limited

# Actions
$selectorAction = New-ScheduledTaskAction -Execute $SelectorCmd -WorkingDirectory $BasePath
$monitorAction  = New-ScheduledTaskAction -Execute $MonitorCmd  -WorkingDirectory $BasePath

$Weekdays = @("Monday","Tuesday","Wednesday","Thursday","Friday")
$Weekend  = @("Saturday","Sunday")

# Helper — wrap Register-ScheduledTask with colored output
function Register-GTTask {
    param(
        [string]$Name,
        [object]$Action,
        [object]$Trigger,
        [string]$Description
    )
    try {
        Register-ScheduledTask `
            -TaskName    $Name `
            -TaskPath    $TaskPath `
            -Action      $Action `
            -Trigger     $Trigger `
            -Settings    $settings `
            -Principal   $principal `
            -Description $Description `
            -Force | Out-Null
        Write-Host ("  + {0}" -f $Name) -ForegroundColor Green
        return $true
    } catch {
        Write-Host ("  x {0} -- {1}" -f $Name, $_.Exception.Message) -ForegroundColor Red
        return $false
    }
}

# Helper — build ένα weekly trigger με repetition κάθε N λεπτά για M ώρες
function New-RepeatingWeeklyTrigger {
    param(
        [string[]]$DaysOfWeek,
        [string]$StartTime,
        [int]$IntervalMinutes,
        [int]$DurationHours
    )
    $trig = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $DaysOfWeek -At $StartTime
    # Borrow a Repetition block from a Once trigger (γνωστό PS pattern)
    $tmp = New-ScheduledTaskTrigger `
        -Once -At $StartTime `
        -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes) `
        -RepetitionDuration (New-TimeSpan -Hours   $DurationHours)
    $trig.Repetition = $tmp.Repetition
    return $trig
}

$results = @{}

# ---- 1. GT-Selector-AM (weekday 08:00) ----
$trig = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Weekdays -At "08:00"
$results["GT-Selector-AM"] = Register-GTTask -Name "GT-Selector-AM" -Action $selectorAction -Trigger $trig `
    -Description "Asset Selector pre-London KZ (weekday 08:00 EET)"

# ---- 2. GT-Selector-Mid (weekday 14:30) ----
$trig = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Weekdays -At "14:30"
$results["GT-Selector-Mid"] = Register-GTTask -Name "GT-Selector-Mid" -Action $selectorAction -Trigger $trig `
    -Description "Asset Selector pre-NY KZ (weekday 14:30 EET)"

# ---- 3. GT-Selector-EVE (weekday 20:00) ----
$trig = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Weekdays -At "20:00"
$results["GT-Selector-EVE"] = Register-GTTask -Name "GT-Selector-EVE" -Action $selectorAction -Trigger $trig `
    -Description "Asset Selector end-of-day + overnight (weekday 20:00 EET)"

# ---- 4. GT-Selector-WE (Sat+Sun 10:00) ----
$trig = New-ScheduledTaskTrigger -Weekly -DaysOfWeek $Weekend -At "10:00"
$results["GT-Selector-WE"] = Register-GTTask -Name "GT-Selector-WE" -Action $selectorAction -Trigger $trig `
    -Description "Asset Selector weekend crypto (Sat+Sun 10:00 EET)"

# ---- 5. GT-Monitor-Peak (weekday 08:00-22:00, every 20 min = 14h window) ----
$trig = New-RepeatingWeeklyTrigger -DaysOfWeek $Weekdays -StartTime "08:00" -IntervalMinutes 20 -DurationHours 14
$results["GT-Monitor-Peak"] = Register-GTTask -Name "GT-Monitor-Peak" -Action $monitorAction -Trigger $trig `
    -Description "Market Monitor peak (weekday 08:00-22:00, every 20 min, covers London + NY KZ)"

# ---- 6. GT-Monitor-OffPeak (weekday 22:00 -> +10h -> 08:00, every 40 min) ----
$trig = New-RepeatingWeeklyTrigger -DaysOfWeek $Weekdays -StartTime "22:00" -IntervalMinutes 40 -DurationHours 10
$results["GT-Monitor-OffPeak"] = Register-GTTask -Name "GT-Monitor-OffPeak" -Action $monitorAction -Trigger $trig `
    -Description "Market Monitor off-peak (weekday 22:00-08:00, every 40 min, Asian session)"

# ---- 7. GT-Monitor-Weekend (Sat+Sun 10:00-22:00, every 40 min = 12h) ----
$trig = New-RepeatingWeeklyTrigger -DaysOfWeek $Weekend -StartTime "10:00" -IntervalMinutes 40 -DurationHours 12
$results["GT-Monitor-Weekend"] = Register-GTTask -Name "GT-Monitor-Weekend" -Action $monitorAction -Trigger $trig `
    -Description "Market Monitor weekend (Sat+Sun 10:00-22:00, every 40 min, crypto only)"

Write-Host ""

# ============================================================
# STEP 3 — Summary
# ============================================================
Write-Host "[3/3] Verification ..." -ForegroundColor Yellow
Write-Host ""

$tasks = @(Get-ScheduledTask -TaskPath $TaskPath -ErrorAction SilentlyContinue)
$count = $tasks.Count
$failed = @($results.GetEnumerator() | Where-Object { -not $_.Value } | ForEach-Object { $_.Key })

if ($count -eq 7 -and $failed.Count -eq 0) {
    $summary = foreach ($t in $tasks) {
        $info = Get-ScheduledTaskInfo -TaskName $t.TaskName -TaskPath $TaskPath
        [pscustomobject]@{
            TaskName    = $t.TaskName
            State       = $t.State
            NextRunTime = $info.NextRunTime
            LastRunTime = $info.LastRunTime
        }
    }
    $summary | Sort-Object TaskName | Format-Table -AutoSize

    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host " ✅ 7/7 tasks installed" -ForegroundColor Green
    Write-Host "============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Logs folder : $LogDir" -ForegroundColor Cyan
    Write-Host "Wrappers    : $BasePath\GOLD_TACTIC\scripts\schtasks\" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Για verification:"
    Write-Host "  Get-ScheduledTask -TaskPath '\GoldTactic\*' | Format-Table" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Για rollback (αν χρειαστεί):"
    Write-Host "  Get-ScheduledTask -TaskPath '\GoldTactic\*' | Unregister-ScheduledTask -Confirm:`$false" -ForegroundColor Gray
    Write-Host ""
    $exitCode = 0
} else {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host (" ❌ Installer FAILED -- found {0}/7 tasks" -f $count) -ForegroundColor Red
    if ($failed.Count -gt 0) {
        Write-Host (" Failed: {0}" -f ($failed -join ", ")) -ForegroundColor Red
    }
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host ""
    if ($tasks.Count -gt 0) {
        Write-Host "Tasks που βρέθηκαν:"
        $tasks | Select-Object TaskName, State | Format-Table -AutoSize
    }
    $exitCode = 1
}

Write-Host ""
Read-Host "Press Enter to close"
exit $exitCode
