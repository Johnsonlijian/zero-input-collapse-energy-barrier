$py = "E:\n0r52\venv\Scripts\python.exe"
$L  = "E:\n0r53\logs"
$env:N0R53_RUNS = "E:\n0r53\runs"
$jobs = @(
  @{ log = "kick_energy_pilot"; cmd = "`"$py`" E:\n0r53\code\addenda53.py kick_energy --models SMF4B --tags ta tstar --rid-stride 5 --workers 4" },
  @{ log = "push_deep_cg";      cmd = "`"$py`" E:\n0r53\code\addenda53.py push_deep --models SMF4CG SMF8CG --tags ta tstar --workers 8" }
)
foreach ($j in $jobs) {
  $line = "cmd.exe /c `"cd /d E:\n0r53\code && set `"N0R53_RUNS=E:\n0r53\runs`" && $($j.cmd) > $L\$($j.log).log 2>&1`""
  $r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $line; CurrentDirectory = 'E:\n0r53\code' }
  "{0}: pid={1} rc={2}" -f $j.log, $r.ProcessId, $r.ReturnValue
}
