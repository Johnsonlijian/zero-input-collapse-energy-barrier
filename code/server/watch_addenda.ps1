$L = "E:\n0r53\logs"
$out = "$L\addenda_watch.log"
$dirs = @{
  a6 = "E:\n0r53\runs\aftershock_a6\SMF4B"
  ms = "E:\n0r53\runs\aftershock_ms\SMF4B"
  ke = "E:\n0r53\runs\kick_energy"
}
while ($true) {
  $a6 = @(Get-ChildItem "$($dirs.a6)\*.json" -ErrorAction SilentlyContinue).Count
  $ms = @(Get-ChildItem "$($dirs.ms)\*.json" -ErrorAction SilentlyContinue).Count
  $ke = @(Get-ChildItem "$($dirs.ke)\*\*.json" -Recurse -ErrorAction SilentlyContinue).Count
  $err = @(Get-ChildItem "E:\n0r53\runs\aftershock_a6\*\*.err","E:\n0r53\runs\aftershock_ms\*\*.err","E:\n0r53\runs\kick_energy\*\*.err" -ErrorAction SilentlyContinue).Count
  $line = "{0} a6={1}/300 ms={2}/400 ke={3}/910 err={4}" -f (Get-Date -Format "HH:mm:ss"), $a6, $ms, $ke, $err
  Add-Content $out $line
  if ($a6 -ge 300 -and $ms -ge 400 -and $ke -ge 910) { Add-Content $out "ALL DONE"; break }
  Start-Sleep 900
}
