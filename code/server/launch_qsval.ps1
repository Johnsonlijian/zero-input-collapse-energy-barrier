$ErrorActionPreference = 'Continue'
$py = 'E:\n0r52\venv\Scripts\python.exe'
$p = Start-Process -FilePath $py -ArgumentList 'E:\n0r53\pilot\pilotB_quasistatic.py','run','--workers','8' `
  -WorkingDirectory 'E:\n0r53\pilot' -RedirectStandardOutput 'E:\n0r53\pilot\pilotB_val_run2.log' `
  -RedirectStandardError 'E:\n0r53\pilot\pilotB_val_err2.log' -WindowStyle Hidden -PassThru
"pilotB_val pid=$($p.Id)"
