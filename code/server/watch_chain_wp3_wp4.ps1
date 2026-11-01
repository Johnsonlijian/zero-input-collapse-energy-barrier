$ErrorActionPreference = 'Continue'
$env:N0R52_RUNS = 'E:\n0r53\runs'
$env:N0R53_RUNS = 'E:\n0r53\runs'
$py = 'E:\n0r52\venv\Scripts\python.exe'
$cc = 'E:\n0r53\code_copy'
$c53 = 'E:\n0r53\code'
$log = 'E:\n0r53\logs\chain_wp3b_wp4.log'
function L($m) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $m" | Out-File $log -Append -Encoding utf8 }

function CampProcs($pat) {
    Get-CimInstance Win32_Process -Filter "name='python.exe'" | Where-Object { $_.CommandLine -like $pat }
}
function Wait-NoProc($pat) {
    do {
        Start-Sleep 60
        $n = @(CampProcs $pat).Count
    } while ($n -gt 0)
}
function Launch-Py($workdir, $pyArgs, $outLog, $errLog) {
    L "LAUNCH: python $($pyArgs -join ' ') > $outLog"
    Start-Process -FilePath $py -ArgumentList $pyArgs -WorkingDirectory $workdir `
        -RedirectStandardOutput $outLog -RedirectStandardError $errLog -WindowStyle Hidden
}
function Launch-Wait($workdir, $pyArgs, $outLog, $errLog, $pat) {
    Launch-Py $workdir $pyArgs $outLog $errLog
    Start-Sleep 120
    Wait-NoProc $pat
    L "DONE: $($pyArgs -join ' ')"
}

L "watcher start; waiting for IDA to exit"
# 1. wait for IDA master to exit
Wait-NoProc '*campaign.py ida*'
L "IDA exited; waiting for zic_wp3a (launched by watch_and_chain.ps1)"
# 2. wait for zic_wp3a to appear (old watcher), fallback: launch it myself after 15 min
$deadline = (Get-Date).AddMinutes(15)
while ((Get-Date) -lt $deadline) {
    if (@(CampProcs '*campaign.py zic*').Count -gt 0) { break }
    if (Test-Path 'E:\n0r53\logs\zic_wp3a.log') {
        $len = (Get-Item 'E:\n0r53\logs\zic_wp3a.log').Length
        if ($len -gt 0 -and @(CampProcs '*campaign.py zic*').Count -eq 0) { break }
    }
    Start-Sleep 60
}
if (@(CampProcs '*campaign.py zic*').Count -eq 0) {
    L "zic_wp3a not detected -> fallback launch"
    Launch-Py $cc @('campaign.py','zic','--models','SMF2B','SMF2CG','SMF4CG','SMF8CG','--levels','hi','lo','--workers','20') 'E:\n0r53\logs\zic_wp3a.log' 'E:\n0r53\logs\zic_wp3a_err.log'
    Start-Sleep 120
}
Wait-NoProc '*campaign.py zic*'
L "zic_wp3a finished"

# 3. chain: zic_wp3b -> rest_wp3a -> rest_wp3b
Launch-Wait $cc @('campaign.py','zic','--models','SMF12B','SMF12CG','SMF20B','SMF20CG','--sets','FF','--levels','hi','lo','--workers','20') 'E:\n0r53\logs\zic_wp3b.log' 'E:\n0r53\logs\zic_wp3b_err.log' '*campaign.py zic*'
Launch-Wait $cc @('campaign.py','rest','--models','SMF2B','SMF2CG','SMF4CG','SMF8CG','--levels','hi','--workers','20') 'E:\n0r53\logs\rest_wp3a.log' 'E:\n0r53\logs\rest_wp3a_err.log' '*campaign.py rest*'
Launch-Wait $cc @('campaign.py','rest','--models','SMF12B','SMF12CG','SMF20B','SMF20CG','--sets','FF','--levels','hi','--workers','20') 'E:\n0r53\logs\rest_wp3b.log' 'E:\n0r53\logs\rest_wp3b_err.log' '*campaign.py rest*'
L "WP3 chain done; starting WP4 for SMF2B SMF2CG SMF4CG SMF8CG (20 workers each stage)"

# 4. WP4 per model: push -> kick -> kick_undamped -> erosion
foreach ($m in @('SMF2B','SMF2CG','SMF4CG','SMF8CG')) {
    Launch-Wait $c53 @('campaign53.py','push','--models',$m,'--workers','20') "E:\n0r53\logs\wp4_push_$m.log" "E:\n0r53\logs\wp4_push_${m}_err.log" '*campaign53.py push*'
    Launch-Wait $c53 @('campaign53.py','kick','--models',$m,'--workers','20') "E:\n0r53\logs\wp4_kick_$m.log" "E:\n0r53\logs\wp4_kick_${m}_err.log" '*campaign53.py kick*'
    Launch-Wait $c53 @('campaign53.py','kick_undamped','--models',$m,'--workers','20') "E:\n0r53\logs\wp4_kickund_$m.log" "E:\n0r53\logs\wp4_kickund_${m}_err.log" '*campaign53.py kick_undamped*'
    Launch-Wait $c53 @('campaign53.py','erosion','--models',$m,'--workers','20') "E:\n0r53\logs\wp4_erosion_$m.log" "E:\n0r53\logs\wp4_erosion_${m}_err.log" '*campaign53.py erosion*'
    L "WP4 done for $m"
}
L "ALL DONE"
