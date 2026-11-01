$stg='E:\n0r53\delta_ingest'
Remove-Item $stg -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive 'E:\n0r53\delta2.zip' -DestinationPath $stg -Force
$man=@{}
Get-Content 'E:\n0r53\delta_manifest.csv' | ForEach-Object {
  $p = $_ -split ',', 2
  if ($p.Length -eq 2 -and $p[0]) { $man[$p[0].Trim()] = $p[1].Trim().ToLower() }
}
$new=0;$skip=0;$bad=0;$badlist=@();$missing=0
Get-ChildItem $stg -Recurse -File | ForEach-Object {
  $rel=$_.FullName.Substring($stg.Length+1)
  $dst='E:\n0r53\runs\'+$rel
  if(Test-Path $dst){$skip++;return}
  $h=(Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLower()
  if(-not $man.ContainsKey($rel)){$missing++;return}
  if($man[$rel] -ne $h){$bad++;$badlist+=$rel;return}
  New-Item -ItemType Directory -Force (Split-Path $dst) | Out-Null
  Copy-Item $_.FullName $dst
  $new++
}
Write-Output "new=$new skip=$skip hashbad=$bad nomanifest=$missing"
if($badlist){$badlist | Select-Object -First 10}
