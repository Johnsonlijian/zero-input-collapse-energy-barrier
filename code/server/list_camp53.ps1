Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*campaign53.py*' } | Select-Object ProcessId, ParentProcessId, CreationDate | Format-List
