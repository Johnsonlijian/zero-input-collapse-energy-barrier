$ErrorActionPreference = 'Continue'
$dst = 'W:\01_PROJECTS\NAS_DRIVE\IMUT\1-Research_Output\1-Papers\1_In_Preparation\ai_civil_slate_codex_goal_gate\rounds\R53_N0_TOPTIER_REBUILD_2026-10-21'
New-Item -ItemType Directory -Force -Path (Join-Path $dst 'pilot') | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $dst 'lit') | Out-Null
$pilot = @('E:\n0r53\pilot\pilotA_shape_summary.md','E:\n0r53\pilot\pilotA_shape_table.csv',
           'E:\n0r53\pilot\pilotA_shape_fig.png','E:\n0r53\pilot\pilotB_quasistatic_validation.md',
           'E:\n0r53\pilot\pilotB_quasistatic_summary.md','E:\n0r53\pilot\pilotA_shape.py',
           'E:\n0r53\pilot\pilotA_shape_analyze.py','E:\n0r53\pilot\pilotB_quasistatic.py')
foreach ($f in $pilot) { if (Test-Path $f) { Copy-Item $f -Destination (Join-Path $dst 'pilot') -Force } }
$lit = @('E:\n0r53\lit\refcheck_R53.csv','E:\n0r53\lit\refcheck_R53.md','E:\n0r53\lit\refcheck_R53.py')
foreach ($f in $lit) { if (Test-Path $f) { Copy-Item $f -Destination (Join-Path $dst 'lit') -Force } }
Get-ChildItem (Join-Path $dst 'pilot'), (Join-Path $dst 'lit') | Select-Object Name, Length | Format-Table -AutoSize
