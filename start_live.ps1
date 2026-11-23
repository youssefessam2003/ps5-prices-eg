# Keep the private phone refresh companion running on this computer.
param([string]$Device)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$ps5ConfigPath = Join-Path $PSScriptRoot 'logs\live_config.json'
New-Item -ItemType Directory -Force (Split-Path $ps5ConfigPath) | Out-Null
if (-not (Test-Path -LiteralPath $ps5ConfigPath)) {
    $ps5Rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $ps5TokenBytes = New-Object byte[] 40
    $ps5Rng.GetBytes($ps5TokenBytes)
    $ps5Rng.Dispose()
    $ps5ConfigJson = @{
        COLLECTOR_URL = 'http://127.0.0.1:8765'
        PRICE_DATA_URL = 'http://127.0.0.1:8765/data'
        COLLECTOR_TOKEN = [Convert]::ToBase64String($ps5TokenBytes)
    } | ConvertTo-Json
    [IO.File]::WriteAllText($ps5ConfigPath, $ps5ConfigJson, (New-Object Text.UTF8Encoding $false))
}
$ps5Config = Get-Content -Raw -LiteralPath $ps5ConfigPath | ConvertFrom-Json
$ps5Headers = @{ Authorization = 'Bearer ' + $ps5Config.COLLECTOR_TOKEN }
if (-not $Device) {
    $ps5Devices = @(adb devices | Select-String '^([^\s]+)\s+device$' | ForEach-Object { $_.Matches[0].Groups[1].Value })
    if ($ps5Devices.Count -ne 1) { throw 'Connect one authorized Android phone, or specify -Device <adb-serial>.' }
    $Device = $ps5Devices[0]
}
$ps5Port = ([uri]$ps5Config.COLLECTOR_URL).Port
adb -s $Device reverse "tcp:$ps5Port" "tcp:$ps5Port"
if ($LASTEXITCODE -ne 0) { throw 'The phone is not connected to ADB.' }
$ps5Ready = $false
try { $ps5Ready = (Invoke-RestMethod ($ps5Config.COLLECTOR_URL + '/api/health') -Headers $ps5Headers -TimeoutSec 2).status -eq 'ok' } catch {}
if (-not $ps5Ready) {
    $ps5Python = (Get-Command python).Source
    Start-Process -FilePath $ps5Python -ArgumentList @('collector/serve.py', '--config', 'logs/live_config.json', '--device', $Device) -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $PSScriptRoot 'logs\companion.out.log') -RedirectStandardError (Join-Path $PSScriptRoot 'logs\companion.err.log')
    for ($ps5Attempt = 0; $ps5Attempt -lt 20; $ps5Attempt++) {
        try {
            $ps5Ready = (Invoke-RestMethod ($ps5Config.COLLECTOR_URL + '/api/health') -Headers $ps5Headers -TimeoutSec 2).status -eq 'ok'
            if ($ps5Ready) { break }
        } catch {}
        Start-Sleep -Milliseconds 250
    }
}
if (-not $ps5Ready) { throw 'The price companion did not start; see logs/companion.err.log.' }
Write-Output 'Live Refresh is ready. Keep this computer on and the phone connected.'
