$ErrorActionPreference = 'Continue'
$py = 'E:\n0r52\venv\Scripts\python.exe'
$p = Start-Process -FilePath $py -ArgumentList 'E:\n0r53\pilot\pilotA_undamped_8B.py','run','--workers','12' `
  -WorkingDirectory 'E:\n0r53\pilot' -RedirectStandardOutput 'E:\n0r53\pilot\pilotA_undamped_8B_run.log' `
  -RedirectStandardError 'E:\n0r53\pilot\pilotA_undamped_8B_err.log' -WindowStyle Hidden -PassThru
"pilotA_undamped_8B pid=$($p.Id)"
