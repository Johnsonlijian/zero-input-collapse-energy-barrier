$ErrorActionPreference = 'Continue'
$env:N0R52_RUNS = 'E:\n0r53\runs'
$py = 'E:\n0r52\venv\Scripts\python.exe'
$p = Start-Process -FilePath $py -ArgumentList 'campaign.py','ida','--models','SMF2B','SMF2CG','SMF4CG','SMF8CG','SMF12B','SMF12CG','SMF20B','SMF20CG','--workers','20' `
  -WorkingDirectory 'E:\n0r53\code_copy' -RedirectStandardOutput 'E:\n0r53\logs\ida_wp2.log' `
  -RedirectStandardError 'E:\n0r53\logs\ida_wp2_err.log' -WindowStyle Hidden -PassThru
"ida_wp2 pid=$($p.Id)"
