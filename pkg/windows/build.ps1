# Builds the folder MSS installs, uv's own build of Python with the dependencies uv.lock pins and
# MSS's wheel installed into it, and the dashboard's build, as pkg/build.sh does elsewhere, and
# packages it as an MSI: run from the repository root after building the dashboard in ui\, with
# $env:VERSION set and WiX 5 installed (`dotnet tool install --global wix --version 5.0.2`)

$ErrorActionPreference = "Stop"

if (-not (Test-Path ui\dist\index.html) -or (Test-Path ui\dist\dev-login.html)) {
    throw "ui\dist has no dashboard, or npm run dev's stub: run npm ci and npm run build in ui\ first"
}

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
Remove-Item -Recurse -Force "$binDir\app", "$binDir\python", "$binDir\wheel" -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force "$binDir\app" | Out-Null

# uv's build of Python finds its own files from wherever it is, so it is copied whole
$env:UV_PYTHON_INSTALL_DIR = (Resolve-Path $binDir).Path + "\python"
uv python install --no-bin 3.13
if ($LASTEXITCODE -ne 0) { throw "uv python install failed" }
# the versioned folder, cpython-3.13.N-..., not the link of its minor version uv adds beside it
$pythonDir = Get-ChildItem $env:UV_PYTHON_INSTALL_DIR -Directory -Filter "cpython-3.13.*" |
    Select-Object -First 1
Copy-Item -Recurse $pythonDir.FullName "$binDir\app\python"
Remove-Item Env:UV_PYTHON_INSTALL_DIR

uv export --frozen --no-dev --no-emit-project --no-hashes -o "$binDir\requirements.txt"
uv build --out-dir "$binDir\wheel"
$wheel = (Get-ChildItem "$binDir\wheel\*.whl").FullName
uv pip install --python "$binDir\app\python\python.exe" --break-system-packages --no-deps `
    --link-mode copy -r "$binDir\requirements.txt" $wheel
if ($LASTEXITCODE -ne 0) { throw "uv pip install failed" }
# compiled with the folder the MSI installs it in, so that a traceback shows the source's lines
& "$binDir\app\python\python.exe" -m compileall -q -j 0 `
    -s (Resolve-Path "$binDir\app").Path -p "$env:ProgramFiles\Tergite MSS" `
    (Resolve-Path "$binDir\app\python\Lib").Path
Copy-Item -Recurse ui\dist "$binDir\app\dashboard"

wix build pkg\windows\tergite-mss.wxs -arch x64 `
    -d MsiVersion=$msiVersion -d BinDir=$binDir `
    -o "dist\tergite-mss-$env:VERSION-windows-x64.msi"
if ($LASTEXITCODE -ne 0) { throw "wix build failed" }
