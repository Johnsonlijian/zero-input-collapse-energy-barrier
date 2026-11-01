$ErrorActionPreference = 'Continue'
$idaPid = 43760
$log = 'E:\n0r53\logs\ida_wp2.log'
$marker = 'E:\n0r53\logs\watcher.log'
"$(Get-Date -Format o) watcher start, watching pid $idaPid" | Out-File $marker
while ($true) {
    $alive = Get-Process -Id $idaPid -ErrorAction SilentlyContinue
    if (-not $alive) { break }
    Start-Sleep -Seconds 60
}
"$(Get-Date -Format o) ida pid $idaPid exited; tail of log:" | Out-File $marker -Append
Get-Content $log -Tail 3 | Out-File $marker -Append
$env:N0R52_RUNS = 'E:\n0r53\runs'
$py = 'E:\n0r52\venv\Scripts\python.exe'
$p = Start-Process -FilePath $py -ArgumentList 'E:\n0r53\code_copy\campaign.py','zic','--models','SMF2B','SMF2CG','SMF4CG','SMF8CG','--levels','hi','lo','--workers','20' `
  -WorkingDirectory 'E:\n0r53\code_copy' -RedirectStandardOutput 'E:\n0r53\logs\zic_wp3a.log' `
  -RedirectStandardError 'E:\n0r53\logs\zic_wp3a_err.log' -WindowStyle Hidden -PassThru
"$(Get-Date -Format o) launched zic_wp3a pid=$($p.Id)" | Out-File $marker -Append
