$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\Users\dkwat\kip-options-scanner"
$PythonExe = "C:\Users\dkwat\AppData\Local\Programs\Python\Python314\python.exe"
$ResearchScan = Join-Path $ProjectRoot "research_scan.py"
$UserId = "$env:USERDOMAIN\$env:USERNAME"

$Tasks = @(
    @{
        Name = "SP-001-1000-ET"
        LocalTime = "09:00"
        Label = "10:00 ET"
    },
    @{
        Name = "SP-001-1200-ET"
        LocalTime = "11:00"
        Label = "12:00 ET"
    },
    @{
        Name = "SP-001-1400-ET"
        LocalTime = "13:00"
        Label = "14:00 ET"
    }
)

foreach ($Task in $Tasks) {
    $Arguments = "`"$ResearchScan`" --run-mode scheduled --scheduled-time-label `"$($Task.Label)`""
    $Action = New-ScheduledTaskAction `
        -Execute $PythonExe `
        -Argument $Arguments `
        -WorkingDirectory $ProjectRoot
    $Trigger = New-ScheduledTaskTrigger -Daily -At $Task.LocalTime
    $Principal = New-ScheduledTaskPrincipal `
        -UserId $UserId `
        -LogonType Interactive `
        -RunLevel Limited
    $Settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Hours 2)

    try {
        Register-ScheduledTask `
            -TaskName $Task.Name `
            -Action $Action `
            -Trigger $Trigger `
            -Principal $Principal `
            -Settings $Settings `
            -Description "Run SP-001 research_scan.py for $($Task.Label)." `
            -Force | Out-Null

        $CreatedTask = Get-ScheduledTask -TaskName $Task.Name -ErrorAction Stop
        Write-Host "Registered $($CreatedTask.TaskName) at local time $($Task.LocalTime)."
    }
    catch {
        Write-Error "Failed to register or confirm scheduled task '$($Task.Name)': $($_.Exception.Message)"
    }
}
