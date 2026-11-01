$py = "E:\n0r52\venv\Scripts\python.exe"
$L  = "E:\n0r53\logs"
$jobs = @(
  @{ log = "aftershock_a6_full"; cmd = "aftershock_a6 --models SMF4B --tags early1 early2 ta --workers 8" },
  @{ log = "aftershock_ms_full"; cmd = "aftershock_ms --models SMF4B --workers 12" }
)
foreach ($j in $jobs) {
  $line = "cmd.exe /c `"cd /d E:\n0r53\code && set `"N0R53_RUNS=E:\n0r53\runs`" && `"$py`" E:\n0r53\code\addenda53.py $($j.cmd) > $L\$($j.log).log 2>&1`""
  $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $line; CurrentDirectory = 'E:\n0r53\code' }
  "{0}: pid={1} rc={2}" -f $j.log, $r.ProcessId, $r.ReturnValue
}
