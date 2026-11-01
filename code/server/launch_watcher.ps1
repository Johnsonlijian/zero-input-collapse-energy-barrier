$p = Start-Process -FilePath 'powershell.exe' -ArgumentList '-ExecutionPolicy','Bypass','-File','E:\n0r53\watch_and_chain.ps1' -WindowStyle Hidden -PassThru
"watcher pid=$($p.Id)"
