# Slot queue watcher v2: a phase is done only when NO live process carries its
# command line (phase + model token). Budget: 32 workers total.
$py = "E:\n0r52\venv\Scripts\python.exe"
$L  = "E:\n0r53\logs"
$qlog = "$L\a6_queue.log"
function logq($m) { Add-Content $qlog ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $m) }

# running jobs: name -> (cmdline match token, nominal workers)
$running = @(
  @{ name="aftershock_a6";   match="*addenda53.py aftershock_a6*SMF4B*"; w=8  },
  @{ name="aftershock_ms4B"; match="*addenda53.py aftershock_ms*SMF4B*"; w=12 },
  @{ name="ms_SMF8B";        match="*addenda53.py aftershock_ms*SMF8B*"; w=8  },
  @{ name="ms_SMF4CG";       match="*addenda53.py aftershock_ms*SMF4CG*"; w=8  },
  @{ name="ms_SMF8CG";       match="*addenda53.py aftershock_ms*SMF8CG*"; w=8  },
  @{ name="push_deep_tall";  match="*push_deep*SMF12B*";                w=8  },
  @{ name="a6_deep";         match="*addenda53b.py a6_barrier_deep*";   w=4  }
)

# queue (launch in order when slots free)
$queue = @(
  @{ name="ktan_small";   w=8; cmd="E:\n0r53\code\campaign53.py ktan --models SMF2B SMF2CG SMF4B SMF4CG SMF8B SMF8CG --tags ta tstar early1 early2 late rescued lo_ke lo_drift --workers 8"; log="ktan_small.log"; match="*campaign53.py ktan*SMF2B*"; done=$false },
  @{ name="ktan_tall";    w=8; cmd="E:\n0r53\code\campaign53.py ktan --models SMF12B SMF12CG SMF20B SMF20CG --tags ta tstar --workers 8"; log="ktan_tall.log"; match="*campaign53.py ktan*SMF12B*"; done=$false },
  @{ name="ms_SMF2B";     w=8; cmd="E:\n0r53\code\addenda53.py aftershock_ms --models SMF2B --workers 8"; log="ms_SMF2B.log"; match="*addenda53.py aftershock_ms*SMF2B*"; done=$false }
)

function alive($match) {
  $procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue
  foreach ($p in $procs) { if ($p.CommandLine -like $match) { return $true } }
  return $false
}
function launch($q) {
  $line = "cmd.exe /c `"cd /d E:\n0r53\code && set `"N0R53_RUNS=E:\n0r53\runs`" && `"$py`" $($q.cmd) > $L\$($q.log) 2>&1`""
  Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $line; CurrentDirectory = 'E:\n0r53\code' } | Out-Null
}

logq "watcher v2 start"
$cyc = 0
while ($true) {
  $busy = 0
  foreach ($j in $running) {
    if ($j.dead) { continue }
    if (-not (alive $j.match)) { $j.dead = $true; logq "$($j.name) detected done" }
    else { $busy += $j.w }
  }
  foreach ($q in $queue) {
    if ($q.done) { continue }
    if ($busy + $q.w -le 32) {
      launch $q; $busy += $q.w; $q.done = $true
      $running += @{ name=$q.name; match=$q.match; w=$q.w; dead=$false }
      logq "LAUNCH $($q.name) ($($q.w)w) -> $($q.log)"
    }
  }
  # hourly: re-run a6_barrier_deep + a6_barrier_deep2 for newly finished states
  $cyc++
  if ($cyc % 6 -eq 0 -and $busy + 4 -le 32) {
    $a6dead = $true
    foreach ($j in $running) { if ($j.name -eq "a6_deep") { $a6dead = $j.dead } }
    if ($a6dead -and -not (alive "*addenda53b.py a6_barrier_deep*")) {
      $line = "cmd.exe /c `"cd /d E:\n0r53\code && set `"N0R53_RUNS=E:\n0r53\runs`" && `"$py`" E:\n0r53\code\addenda53b.py a6_barrier_deep --models SMF4B SMF8B SMF4CG SMF8CG SMF2B --workers 4 > $L\a6_barrier_deep.log 2>&1`""
      Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{ CommandLine = $line; CurrentDirectory = 'E:\n0r53\code' } | Out-Null
      $busy += 4
      foreach ($j in $running) { if ($j.name -eq "a6_deep") { $j.dead = $false } }
      logq "RELAUNCH a6_barrier_deep (4w) cycle $cyc"
    }
  }
  Start-Sleep 600
}
