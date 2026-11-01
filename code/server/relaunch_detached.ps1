$ErrorActionPreference = 'Continue'
# kill any surviving pilotA processes (safe: only these scripts)
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object {
  $_.CommandLine -match 'pilotA_(full_8B|erosion)\.py'
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 3
$py = 'E:\n0r52\venv\Scripts\python.exe'
$p1 = Start-Process -FilePath $py -ArgumentList 'E:\n0r53\pilot\pilotA_full_8B.py','run','--workers','28' `
  -WorkingDirectory 'E:\n0r53\pilot' -RedirectStandardOutput 'E:\n0r53\pilot\pilotA_full_8B_run.log' `
  -RedirectStandardError 'E:\n0r53\pilot\pilotA_full_8B_err.log' -WindowStyle Hidden -PassThru
"pilotA_full_8B pid=$($p1.Id)"
$p2 = Start-Process -FilePath $py -ArgumentList 'E:\n0r53\pilot\pilotA_erosion.py','run','--workers','4' `
  -WorkingDirectory 'E:\n0r53\pilot' -RedirectStandardOutput 'E:\n0r53\pilot\pilotA_erosion_run.log' `
  -RedirectStandardError 'E:\n0r53\pilot\pilotA_erosion_err.log' -WindowStyle Hidden -PassThru
"pilotA_erosion pid=$($p2.Id)"
