$py = "E:\n0r52\venv\Scripts\python.exe"
$L  = "E:\n0r53\logs"
$line = "cmd.exe /c `"cd /d E:\n0r53\code && set `"N0R53_RUNS=E:\n0r53\runs`" && `"$py`" E:\n0r53\code\addenda53.py kick_energy --models SMF4B SMF2B SMF8B SMF4CG SMF8CG --tags ta tstar --workers 8 > $L\kick_energy_v2_all.log 2>&1`""
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $line; CurrentDirectory = 'E:\n0r53\code' }
"kick_energy v2 all: pid=$($r.ProcessId) rc=$($r.ReturnValue)"
