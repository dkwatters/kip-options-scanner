# SP-001 Scheduled Scans Setup

SP-001 can be run from Windows Task Scheduler by calling `research_scan.py` in
scheduled mode. Scheduled runs archive to `data\research\opportunity_scans.sqlite`
with `run_mode = scheduled` and the supplied `scheduled_time_label`.

## Manual Test Command

From `C:\Users\dkwat\kip-options-scanner`:

```powershell
python research_scan.py --run-mode scheduled --scheduled-time-label "TEST ET"
```

The default manual research command remains:

```powershell
python research_scan.py
```

That default archives as `run_mode = research-script`.

## Register Scheduled Tasks

This repository includes a helper script:

```powershell
Set-Location "C:\Users\dkwat\kip-options-scanner"
.\scripts\register_sp001_scheduled_tasks.ps1
```

The helper uses this Python executable:

```text
C:\Users\dkwat\AppData\Local\Programs\Python\Python314\python.exe
```

Windows Task Scheduler stores trigger times in the machine's local timezone.
On this Central-time machine, the three SP-001 ET observations are registered
at these local trigger times:

| Task name | Local trigger time | Archived label |
| --- | ---: | --- |
| SP-001 10:00 ET | 09:00 | 10:00 ET |
| SP-001 12:00 ET | 11:00 | 12:00 ET |
| SP-001 14:00 ET | 13:00 | 14:00 ET |

## Expanded PowerShell Commands

These commands are equivalent to the helper script:

```powershell
$ProjectRoot = "C:\Users\dkwat\kip-options-scanner"
$PythonExe = "C:\Users\dkwat\AppData\Local\Programs\Python\Python314\python.exe"
$ResearchScan = Join-Path $ProjectRoot "research_scan.py"
$UserId = "$env:USERDOMAIN\$env:USERNAME"
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 2)
$Principal = New-ScheduledTaskPrincipal -UserId $UserId -LogonType Interactive -RunLevel LeastPrivilege
```

```powershell
$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$ResearchScan`" --run-mode scheduled --scheduled-time-label `"10:00 ET`"" -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At "09:00"
Register-ScheduledTask -TaskName "SP-001 10:00 ET" -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description "Run SP-001 research_scan.py for 10:00 ET." -Force
```

```powershell
$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$ResearchScan`" --run-mode scheduled --scheduled-time-label `"12:00 ET`"" -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At "11:00"
Register-ScheduledTask -TaskName "SP-001 12:00 ET" -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description "Run SP-001 research_scan.py for 12:00 ET." -Force
```

```powershell
$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$ResearchScan`" --run-mode scheduled --scheduled-time-label `"14:00 ET`"" -WorkingDirectory $ProjectRoot
$Trigger = New-ScheduledTaskTrigger -Daily -At "13:00"
Register-ScheduledTask -TaskName "SP-001 14:00 ET" -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description "Run SP-001 research_scan.py for 14:00 ET." -Force
```

## Validation

### Verify Scheduled Tasks Exist

Use PowerShell to confirm the three SP-001 tasks are registered:

```powershell
Get-ScheduledTask -TaskName "SP-001 10:00 ET","SP-001 12:00 ET","SP-001 14:00 ET"
```

Expected result: all three tasks are returned and show a ready or enabled state.

To inspect the configured triggers and action paths:

```powershell
Get-ScheduledTask -TaskName "SP-001 10:00 ET","SP-001 12:00 ET","SP-001 14:00 ET" |
    Select-Object TaskName,State,Actions,Triggers
```

Confirm that each action calls `research_scan.py` with `--run-mode scheduled` and the matching `--scheduled-time-label`.

### Check Last Run Status

After the scheduled times have passed, check the last run timestamp and task result:

```powershell
Get-ScheduledTaskInfo -TaskName "SP-001 10:00 ET","SP-001 12:00 ET","SP-001 14:00 ET" |
    Select-Object TaskName,LastRunTime,LastTaskResult,NextRunTime
```

Validation criteria:

- `LastRunTime` should be populated for each task after its scheduled trigger.
- `LastTaskResult` should be `0` for a successful run.
- A non-zero `LastTaskResult` means Task Scheduler started or attempted the task, but the run needs investigation.

### Confirm Dashboard Protocol Progress

Open the Research Dashboard and review SP-001 protocol progress. A completed local validation should show:

- Scheduled observations recorded for `10:00 ET`, `12:00 ET`, and `14:00 ET`.
- The archived observations counted as scheduled protocol progress.
- Manual scans or default `python research_scan.py` runs excluded from scheduled progress.

If Task Scheduler shows success but the dashboard does not show protocol progress, check that the task action used the expected project root, Python executable, `--run-mode scheduled`, and scheduled time label.

### Local Laptop Limitations

Windows Task Scheduler on a local laptop is adequate for Phase 1 validation but is not continuous infrastructure.

Known limitations:

- Sleep or hibernation can prevent the task from running at the intended time.
- Power loss, battery saver settings, or a closed laptop can delay or skip observations.
- Trigger times are stored in the Windows machine's local timezone, while SP-001 labels are Eastern-time research labels.
- Daylight saving time and manual timezone changes can shift local trigger alignment.
- The current task principal uses an interactive user context, so Windows login/session state can affect execution.
- Network availability and market-data provider access are still required when the task runs.

These limitations are the reason Phase 2 moves autonomous observation to cloud continuous observation infrastructure.
