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
