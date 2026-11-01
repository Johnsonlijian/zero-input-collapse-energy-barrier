Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*watch_chain*' -or $_.CommandLine -like '*watch_and_chain*' } | Select-Object ProcessId, CreationDate | Format-Table -AutoSize
