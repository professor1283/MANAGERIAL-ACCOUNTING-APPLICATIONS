$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runtime = Join-Path $Root "runtime"
$Zip = Join-Path $Root "python-portable.zip"
$Url = "https://www.python.org/ftp/python/3.13.5/python-3.13.5-embed-amd64.zip"

if (Test-Path (Join-Path $Runtime "python.exe")) {
    Write-Host "Portable Python runtime is already present."
    exit 0
}

New-Item -ItemType Directory -Force -Path $Runtime | Out-Null
Write-Host "Downloading the official 64-bit Python 3.13.5 embeddable package..."
Invoke-WebRequest -Uri $Url -OutFile $Zip -UseBasicParsing
Expand-Archive -Path $Zip -DestinationPath $Runtime -Force
Remove-Item $Zip -Force

$Pth = Get-ChildItem $Runtime -Filter "python*._pth" | Select-Object -First 1
if ($null -ne $Pth) {
    $Lines = Get-Content $Pth.FullName
    if ($Lines -notcontains "..") { Add-Content -Path $Pth.FullName -Value ".." }
}
Write-Host "Portable runtime prepared successfully."
