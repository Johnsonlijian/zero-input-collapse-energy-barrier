$ErrorActionPreference = 'Continue'
$env:QS_RATE = '0.025'
$env:QS_DT = '0.01'
$env:QS_VALDIR = 'runsB_val2'
$py = 'E:\n0r52\venv\Scripts\python.exe'
$p = Start-Process -FilePath $py -ArgumentList 'E:\n0r53\pilot\pilotB_quasistatic.py','run','--workers','8' `
  -WorkingDirectory 'E:\n0r53\pilot' -RedirectStandardOutput 'E:\n0r53\pilot\pilotB_val2_run.log' `
  -RedirectStandardError 'E:\n0r53\pilot\pilotB_val2_err.log' -WindowStyle Hidden -PassThru
"pilotB_val2 pid=$($p.Id)"
