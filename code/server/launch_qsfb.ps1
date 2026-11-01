$ErrorActionPreference = 'Continue'
$py = 'E:\n0r52\venv\Scripts\python.exe'
$p = Start-Process -FilePath $py -ArgumentList 'E:\n0r53\pilot\pilotB_quasistatic.py','fallback','--workers','8' `
  -WorkingDirectory 'E:\n0r53\pilot' -RedirectStandardOutput 'E:\n0r53\pilot\pilotB_fb_run.log' `
  -RedirectStandardError 'E:\n0r53\pilot\pilotB_fb_err.log' -WindowStyle Hidden -PassThru
"pilotB_fb pid=$($p.Id)"
