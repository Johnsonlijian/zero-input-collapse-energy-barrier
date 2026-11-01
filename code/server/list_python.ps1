Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ForEach-Object {
  $cmd = $_.CommandLine
  if ($null -eq $cmd) { $cmd = "" }
  "{0}  {1}  {2}" -f $_.ProcessId, $_.CreationDate, $cmd.Substring(0, [Math]::Min(100, $cmd.Length))
}
