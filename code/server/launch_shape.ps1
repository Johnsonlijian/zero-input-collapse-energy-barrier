$ErrorActionPreference = 'Continue'
$py = 'E:\n0r52\venv\Scripts\python.exe'
$p = Start-Process -FilePath $py -ArgumentList 'E:\n0r53\pilot\pilotA_shape.py','run','--workers','8' `
  -WorkingDirectory 'E:\n0r53\pilot' -RedirectStandardOutput 'E:\n0r53\pilot\pilotA_shape_run.log' `
  -RedirectStandardError 'E:\n0r53\pilot\pilotA_shape_err.log' -WindowStyle Hidden -PassThru
"pilotA_shape pid=$($p.Id)"
