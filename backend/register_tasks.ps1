# Register the two background jobs as hidden Windows scheduled tasks. Safe to re-run.
#
#   powershell -ExecutionPolicy Bypass -File backend\register_tasks.ps1
#
# RainRiskIngest:  every 6 hours from 00:30 (forecasts + ML probabilities)
# RainRiskObserve: daily at 20:00 (NASA IMERG observations)
# Both run on battery and start as soon as possible after a missed run.

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)

$ingest = New-ScheduledTaskTrigger -Daily -At 00:30
$ingest.Repetition = (New-ScheduledTaskTrigger -Once -At 00:30 `
    -RepetitionInterval (New-TimeSpan -Hours 6) -RepetitionDuration (New-TimeSpan -Days 1)).Repetition

$jobs = @{
    RainRiskIngest  = @{ Script = 'run_ingest_hidden.vbs';  Trigger = $ingest }
    RainRiskObserve = @{ Script = 'run_observe_hidden.vbs'; Trigger = (New-ScheduledTaskTrigger -Daily -At 20:00) }
}

foreach ($name in $jobs.Keys) {
    $action = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument "`"$here\$($jobs[$name].Script)`"" -WorkingDirectory $here
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $jobs[$name].Trigger -Settings $settings -Force | Out-Null
    Write-Output "registered $name"
}
