# Local sync loop: pull server deltas every ~15 min, ingest new outputs only.
# Never overwrites local files; duplicates -> runs_server_dup; manifest CSV.
$SSH  = "$env:SystemRoot\System32\OpenSSH\ssh.exe"
$SCP  = "$env:SystemRoot\System32\OpenSSH\scp.exe"
$RUNS = "E:\n0r53\runs"
$DUP  = "E:\n0r53\runs_server_dup"
$STG  = "E:\n0r53\server_sync_stage"
$MAN  = "E:\n0r53\logs\server_sync_manifest.csv"
$PROTO_OK = @("R53v1.0+A6","R53v1.0+A6b","R53v1.0+A6d","R53v1.0+A7","R53v1.0+A8","R53v1.0+A15")
# addenda53.py legitimately produced outputs under earlier revisions; accept all vetted hashes
$ACC_ADD = @(
  (Get-FileHash "E:\n0r53\code\addenda53.py" -Algorithm SHA256).Hash,
  "2F0D4C3D76B2359A296C5DB12F4F9A30737C2380C61CAFFA167226142E47F4DF",
  "2289AA15E87C"   # prefix-matched short hash (v0 historical outputs)
)
New-Item -ItemType Directory -Force $STG | Out-Null
if (-not (Test-Path $MAN)) { "relpath,sha256,origin,synced_at" | Out-File $MAN -Encoding utf8 }

# frozen-code reference hashes (full)
$refHash = @{}
foreach ($f in @("E:\n0r53\code\addenda53.py","E:\n0r53\code\addenda53b.py","E:\n0r53\code\campaign53.py","E:\n0r53\code\driver53.py","E:\n0r53\code_copy\driver.py")) {
  $refHash[(Split-Path $f -Leaf)] = (Get-FileHash $f -Algorithm SHA256).Hash
}

while (-not (Test-Path "E:\n0r53\server_sync\STOP")) {
  & $SSH -o BatchMode=yes 5880 "powershell -NoProfile -ExecutionPolicy Bypass -File E:\n0r53\collect_delta.ps1" | Out-Null
  $rc = & $SSH -o BatchMode=yes 5880 "if exist E:\n0r53\delta2.zip (echo YES) else (echo NO)"
  if ($rc -match "YES") {
    & $SCP -o BatchMode=yes 5880:E:/n0r53/delta2.zip "$STG\delta2.zip" 2>$null | Out-Null
    & $SCP -o BatchMode=yes 5880:E:/n0r53/delta_list.txt "$STG\delta_list.txt" 2>$null | Out-Null
    Remove-Item "$STG\files" -Recurse -Force -ErrorAction SilentlyContinue
    Expand-Archive "$STG\delta2.zip" -DestinationPath "$STG\files" -Force -ErrorAction SilentlyContinue
    Get-ChildItem "$STG\files" -Recurse -File | ForEach-Object {
      $f = $_
      # relpath under runs\<phase>\<model>\<file>
      $parts = $f.FullName -split "\\"
      $i = [array]::IndexOf($parts, "files")
      $rel = ($parts[($i+1)..($parts.Length-1)] -join "\")
      if ($f.Extension -eq ".err") {
        Add-Content $MAN "$($rel -replace ',',';'),,err,$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        Add-Content E:\n0r53\logs\server_sync_err.log "$(Get-Date -Format 'HH:mm:ss') ERR $rel`n$(Get-Content $f.FullName -Raw)"
        return
      }
      try { $j = Get-Content $f.FullName -Raw | ConvertFrom-Json } catch {
        Add-Content E:\n0r53\logs\server_sync_err.log "$(Get-Date -Format 'HH:mm:ss') BADJSON $rel"; return
      }
      $ok = $PROTO_OK -contains $j.protocol
      if ($ok -and $j.code_sha256) {
        foreach ($k in $j.code_sha256.PSObject.Properties) {
          if ($k.Name -eq "addenda53.py") {
            $v = $k.Value.ToString().ToUpper()
            if (-not ($ACC_ADD | Where-Object { $v.StartsWith($_) -or $_.StartsWith($v) })) { $ok = $false }
            continue
          }
          if ($refHash.ContainsKey($k.Name) -and $refHash[$k.Name] -ne $k.Value `
              -and -not ($k.Value.Length -ge 16 -and $refHash[$k.Name].StartsWith($k.Value, [StringComparison]::OrdinalIgnoreCase))) { $ok = $false }
        }
      }
      if (-not $ok) {
        $qd = "E:\n0r53\runs_quarantine\$(Split-Path $rel -Parent)"
        New-Item -ItemType Directory -Force $qd | Out-Null
        Move-Item $f.FullName "$qd\$(Split-Path $rel -Leaf)" -Force
        Add-Content $MAN "$($rel -replace ',',';'),,quarantine,$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        return
      }
      $dest = "$RUNS\$rel"
      $sha = (Get-FileHash $f.FullName -Algorithm SHA256).Hash
      if (-not (Test-Path $dest)) {
        New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
        Copy-Item $f.FullName $dest
        Add-Content $MAN "$($rel -replace ',',';'),$sha,server,$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
      } else {
        $dd = "$DUP\$(Split-Path $rel -Parent)"
        New-Item -ItemType Directory -Force $dd | Out-Null
        Move-Item $f.FullName "$dd\$(Split-Path $rel -Leaf)" -Force
        Add-Content $MAN "$($rel -replace ',',';'),$sha,local-dup,$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
      }
    }
    Add-Content E:\n0r53\logs\server_sync.log "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') cycle done"
  }
  Start-Sleep 900
}

