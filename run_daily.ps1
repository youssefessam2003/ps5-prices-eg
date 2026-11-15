# Daily PS5 price run: collect from every store, then publish the JSON for the phone app.
# Scheduled by Windows Task Scheduler (see README). Safe to run by hand too.
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$log = Join-Path $PSScriptRoot "logs\$(Get-Date -Format yyyy-MM-dd).log"
New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null

function Log($m) { "$(Get-Date -Format HH:mm:ss) $m" | Tee-Object -FilePath $log -Append }

Log "pull"
git pull --rebase --autostash 2>&1 | Out-File $log -Append

Log "collect"
python collector\collect.py --headed 2>&1 | Out-File $log -Append

# keep the app's built-in fallback data fresh too
Copy-Item data\latest.json, data\history.json app\assets\data\ -Force

Log "publish"
git add data app/assets/data 2>&1 | Out-File $log -Append
git commit -m "prices $(Get-Date -Format yyyy-MM-dd)" 2>&1 | Out-File $log -Append
for ($i = 0; $i -lt 3; $i++) {
    git push 2>&1 | Out-File $log -Append
    if ($LASTEXITCODE -eq 0) { Log "pushed"; break }
    git pull --rebase -X theirs 2>&1 | Out-File $log -Append
}
Log "done"
