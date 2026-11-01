$killed = @()
Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*aftershock_a6*' -or $_.ParentProcessId -eq 20348 -or $_.ProcessId -eq 20348 } | ForEach-Object {
  $killed += $_.ProcessId
  Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
"killed: $($killed -join ',')"
