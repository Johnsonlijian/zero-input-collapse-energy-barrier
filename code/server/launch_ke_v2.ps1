$py = "E:\n0r52\venv\Scripts\python.exe"
$L  = "E:\n0r53\logs"
$line = "cmd.exe /c `"cd /d E:\n0r53\code && set `"N0R53_RUNS=E:\n0r53\runs`" && `"$py`" E:\n0r53\code\addenda53.py kick_energy --models SMF4B --tags ta tstar --rid-stride 5 --workers 4 > $L\kick_energy_v2.log 2>&1`""
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $line; CurrentDirectory = 'E:\n0r53\code' }
"kick_energy v2: pid=$($r.ProcessId) rc=$($r.ReturnValue)"
