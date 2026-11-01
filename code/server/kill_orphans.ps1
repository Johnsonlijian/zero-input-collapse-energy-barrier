$procs = Get-CimInstance Win32_Process
$live = @{}
foreach ($p in $procs) { $live[$p.ProcessId] = $p }
$orphans = @()
foreach ($p in $procs) {
  if ($p.Name -like '*python*' -and $p.CommandLine -and $p.CommandLine -like '*spawn_main*') {
    if (-not $live.ContainsKey($p.ParentProcessId)) { $orphans += $p.ProcessId }
  }
}
"orphan spawn_main workers: $($orphans -join ',')"
foreach ($k in $orphans) { Stop-Process -Id $k -Force -ErrorAction SilentlyContinue }
