$errs = $null
[void][System.Management.Automation.PSParser]::Tokenize((Get-Content E:\n0r53\watch_queue.ps1 -Raw), [ref]$errs)
"parse errors: " + $errs.Count
$errs | ForEach-Object { $_.Message + " @line " + $_.Token.StartLine }
