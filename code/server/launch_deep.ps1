$py = "E:\n0r52\venv\Scripts\python.exe"
$L  = "E:\n0r53\logs"
$line = "cmd.exe /c `"cd /d E:\n0r53\code && set `"N0R53_RUNS=E:\n0r53\runs`" && `"$py`" E:\n0r53\code\addenda53b.py a6_barrier_deep --models SMF4B --workers 4 > $L\a6_barrier_deep.log 2>&1`""
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $line; CurrentDirectory = 'E:\n0r53\code' }
"a6_barrier_deep: pid=$($r.ProcessId) rc=$($r.ReturnValue)"
Start-Process powershell -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File E:\n0r53\watch_queue.ps1' -WindowStyle Hidden
"watcher launched"
