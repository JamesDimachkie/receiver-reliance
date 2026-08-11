# Non-invasive peak-working-set sampler for the post-F-MODEL-003 N=48 enumeration.
#
# Authored additively as evidence tooling.  It does not wrap, modify, or feed the
# enumeration: it locates the already-running canonical
# `python -B -m portability.model.explorer` process by command line and records
# the OS-tracked running maximum (PeakWorkingSet64) until that process exits.
# The reported figure is a sampled lower bound on the true peak.

param(
  [Parameter(Mandatory = $true)][string]$LogPath,
  [int]$IntervalSeconds = 30,
  [int]$StartupWaitSeconds = 240
)

$ErrorActionPreference = 'Continue'
$deadline = (Get-Date).AddSeconds($StartupWaitSeconds)
$target = $null
while ((Get-Date) -lt $deadline) {
  $target = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*portability.model.explorer*' } |
    Select-Object -First 1
  if ($target) { break }
  Start-Sleep -Seconds 2
}

if (-not $target) {
  "SAMPLER_NO_TARGET_PROCESS" | Out-File -FilePath $LogPath -Encoding ascii
  exit 2
}

$targetId = $target.ProcessId
"SAMPLER_TARGET_PID $targetId" | Out-File -FilePath $LogPath -Encoding ascii
"SAMPLER_TARGET_COMMANDLINE $($target.CommandLine)" | Out-File -FilePath $LogPath -Append -Encoding ascii

$max = 0
while ($true) {
  $proc = Get-Process -Id $targetId -ErrorAction SilentlyContinue
  if (-not $proc) { break }
  $peak = $proc.PeakWorkingSet64
  if ($peak -gt $max) { $max = $peak }
  "SAMPLE $(Get-Date -Format o) working_set_bytes=$($proc.WorkingSet64) peak_working_set_bytes=$peak" |
    Out-File -FilePath $LogPath -Append -Encoding ascii
  Start-Sleep -Seconds $IntervalSeconds
}

"SAMPLER_FINAL_PEAK_WORKING_SET_BYTES $max" | Out-File -FilePath $LogPath -Append -Encoding ascii
"SAMPLER_FINAL_PEAK_WORKING_SET_MIB $([math]::Round($max / 1MB, 1))" | Out-File -FilePath $LogPath -Append -Encoding ascii
exit 0
