$env:N0R53_RUNS = 'E:\n0r53\runs'
$py = 'E:\n0r52\venv\Scripts\python.exe'
Start-Process -FilePath $py -ArgumentList 'E:\n0r53\code\campaign53.py','erosion','--models','SMF4B','SMF8B','--workers','8' -RedirectStandardOutput 'E:\n0r53\logs\erosion_wp4a.log' -RedirectStandardError 'E:\n0r53\logs\erosion_wp4a_err.log' -WorkingDirectory 'E:\n0r53\code' -WindowStyle Hidden
