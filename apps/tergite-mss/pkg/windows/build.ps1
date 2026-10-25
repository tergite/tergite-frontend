# Packages Nuitka's standalone build as an MSI: run from apps/tergite-mss after the Nuitka build, with
# $env:VERSION set and WiX 5 installed (`dotnet tool install --global wix --version 5.0.2`)

$ErrorActionPreference = "Stop"

$winswUrl = "https://github.com/winsw/winsw/releases/download/v2.12.0/WinSW-x64.exe"
$winswSha256 = "05B82D46AD331CC16BDC00DE5C6332C1EF818DF8CEEFCD49C726553209B3A0DA"

$year, $month, $patch = $env:VERSION.Split(".")
# an MSI's major version is at most 255
$msiVersion = "$([int]$year - 2000).$month.$patch"
$binDir = "build\windows"

New-Item -ItemType Directory -Force $binDir, dist | Out-Null
Invoke-WebRequest $winswUrl -OutFile "$binDir\WinSW-x64.exe"
if ((Get-FileHash "$binDir\WinSW-x64.exe" -Algorithm SHA256).Hash -ne $winswSha256) {
    throw "WinSW-x64.exe does not match its checksum"
}
Remove-Item -Recurse -Force "$binDir\app" -ErrorAction SilentlyContinue
Copy-Item -Recurse main.dist "$binDir\app"

wix build pkg\windows\tergite-mss.wxs -arch x64 `
    -d MsiVersion=$msiVersion -d BinDir=$binDir `
    -o "dist\tergite-mss-$env:VERSION-windows-x64.msi"
if ($LASTEXITCODE -ne 0) { throw "wix build failed" }
