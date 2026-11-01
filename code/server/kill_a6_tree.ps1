$procs = Get-CimInstance Win32_Process
$roots = @()
foreach ($p in $procs) {
  if ($p.CommandLine -and ($p.CommandLine -like '*addenda53.py*aftershock_a6*' -or $p.CommandLine -like '*aftershock_a6_pilot*')) { $roots += $p.ProcessId }
}
"roots: $($roots -join ',')"
$queue = New-Object System.Collections.Generic.Queue[int]
$killed = New-Object System.Collections.Generic.HashSet[int]
foreach ($r in $roots) { $queue.Enqueue($r) }
$maxIter = 500; $n = 0
while ($queue.Count -gt 0 -and $n -lt $maxIter) {
  $n++
  $pid_ = $queue.Dequeue()
  if (-not $killed.Add($pid_)) { continue }
  foreach ($p in $procs) { if ($p.ParentProcessId -eq $pid_ -and -not $killed.Contains($p.ProcessId)) { $queue.Enqueue($p.ProcessId) } }
}
foreach ($k in $killed) { Stop-Process -Id $k -Force -ErrorAction SilentlyContinue }
"killed: $($killed -join ',')"
