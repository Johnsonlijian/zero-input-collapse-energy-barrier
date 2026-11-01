$py = "E:\n0r52\venv\Scripts\python.exe"
$L  = "E:\n0r53\logs"
$line = "cmd.exe /c `"cd /d E:\n0r53\code && set `"N0R53_RUNS=E:\n0r53\runs`" && `"$py`" E:\n0r53\code\addenda53.py aftershock_a6 --models SMF4B --tags early1 early2 ta --rid-stride 5 --workers 8 > $L\aftershock_a6_pilot.log 2>&1`""
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $line; CurrentDirectory = 'E:\n0r53\code' }
"aftershock_a6_pilot: pid=$($r.ProcessId) rc=$($r.ReturnValue)"
