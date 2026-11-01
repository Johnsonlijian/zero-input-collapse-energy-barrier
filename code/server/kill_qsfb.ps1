$ErrorActionPreference = 'Continue'
# kill the pilotB_quasistatic fallback tree without touching campaign.py workers
$procs = Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
  Where-Object { $_.CommandLine -match 'pilotB_quasistatic' }
foreach ($p in $procs) { "killing $($p.ProcessId) :: $($p.CommandLine.Substring(0,[Math]::Min(110,$_.CommandLine.Length)))" }
$procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
# spawn children may not carry the script name in their cmdline; find orphans by parent
$kids = Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
  Where-Object { $procs.ProcessId -contains $_.ParentProcessId }
$kids | ForEach-Object { "killing child $($_.ProcessId)"; Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
"done"
