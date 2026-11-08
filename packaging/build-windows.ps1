param(
    [string]$Python = "",
    [string]$InnoCompiler = "",
    [ValidateSet('msi', 'inno')][string]$InstallerFormat = 'msi',
    [switch]$SkipInstaller
)
$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $repoRoot
if (-not $Python) { $Python = Join-Path $repoRoot ".venv\Scripts\python.exe" }
if (-not (Test-Path -LiteralPath $Python)) { throw "Create .venv and install packaging/requirements-build.txt first." }
New-Item -ItemType Directory -Force -Path (Join-Path $repoRoot "build\tmp") | Out-Null
$env:TEMP = (Resolve-Path (Join-Path $repoRoot "build\tmp")).Path
$env:TMP = $env:TEMP
& $Python "packaging\collect_licenses.py"
if ($LASTEXITCODE -ne 0) { throw "License collection failed." }
& $Python -m PyInstaller --noconfirm "packaging\windows.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }
$exePath = Join-Path $repoRoot "dist\AntigravityZhCN\AntigravityZhCN.exe"
$smokeData = Join-Path $repoRoot "build\packaged-smoke-data"
$smoke = Start-Process -FilePath $exePath -ArgumentList @("--smoke-test", "--data-dir", ('"' + $smokeData + '"')) -PassThru -WindowStyle Hidden
if (-not $smoke.WaitForExit(45000)) {
    $smoke.Kill()
    throw "Frozen application smoke test timed out after 45 seconds."
}
if ($smoke.ExitCode -ne 0) { throw "Frozen application smoke test failed (exit $($smoke.ExitCode))." }
$zipPath = Join-Path $repoRoot "dist\AntigravityZhCN-0.1.0-windows-x64.zip"
Compress-Archive -LiteralPath (Join-Path $repoRoot "dist\AntigravityZhCN") -DestinationPath $zipPath -Force
if (-not $SkipInstaller -and $InstallerFormat -eq 'msi') {
    & $Python "packaging\build_msi.py"
    if ($LASTEXITCODE -ne 0) { throw "MSI compilation or database/cabinet validation failed." }
}
if (-not $SkipInstaller -and $InstallerFormat -eq 'inno') {
    if (-not $InnoCompiler) {
        $candidates = @(
            (Join-Path $repoRoot "build\inno\ISCC.exe"),
            "${env:ProgramFiles}\Inno Setup 7\ISCC.exe",
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
        )
        $InnoCompiler = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    }
    if (-not $InnoCompiler) { throw "ZIP built. Inno compiler missing; supply -InnoCompiler or choose -SkipInstaller." }
    & $InnoCompiler "packaging\windows.iss"
    if ($LASTEXITCODE -ne 0) { throw "Installer compilation failed." }
}
Get-ChildItem -LiteralPath (Join-Path $repoRoot "dist") -File | Where-Object { $_.Extension -in @(".zip", ".exe", ".msi") } | ForEach-Object {
    $hash = Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256
    "$($hash.Hash.ToLower())  $($_.Name)"
} | Set-Content -LiteralPath (Join-Path $repoRoot "dist\SHA256SUMS.txt") -Encoding ascii
Write-Output "Build and frozen smoke test completed. Artifacts: $repoRoot\dist"
