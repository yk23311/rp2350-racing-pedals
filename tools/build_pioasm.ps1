$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$vswhere = 'C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe'
if (-not (Test-Path -LiteralPath $vswhere)) { throw 'vswhere.exe not found; Visual Studio C++ build tools are required.' }
$vsRoot = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vsRoot) { throw 'Visual Studio C++ build tools are required.' }
$vcvars = Join-Path $vsRoot 'VC\Auxiliary\Build\vcvars64.bat'
$clang = Join-Path $vsRoot 'VC\Tools\Llvm\x64\bin\clang-cl.exe'
$lld = Join-Path $vsRoot 'VC\Tools\Llvm\x64\bin\lld-link.exe'
$ninja = (Get-Command ninja -ErrorAction Stop).Source
$config = Join-Path $projectRoot 'build\pioasm-install\lib\cmake\pioasm\pioasmConfig.cmake'
if (Test-Path -LiteralPath $config) {
    Write-Host 'pioasm already installed.'
    exit 0
}
$source = Join-Path $projectRoot 'deps\pico-sdk-2.2.0\tools\pioasm'
$binary = Join-Path $projectRoot 'build\pioasm'
$install = Join-Path $projectRoot 'build\pioasm-install'
$cmd = "`"$vcvars`" && cmake -S `"$source`" -B `"$binary`" -G Ninja " +
       "`"-DCMAKE_MAKE_PROGRAM=$ninja`" `"-DCMAKE_BUILD_TYPE=Release`" " +
       "`"-DCMAKE_CXX_COMPILER=$clang`" `"-DCMAKE_LINKER=$lld`" " +
       "`"-DPIOASM_VERSION_STRING=2.2.0`" && " +
       "cmake --build `"$binary`" && cmake --install `"$binary`" --prefix `"$install`""
cmd /d /c $cmd
if ($LASTEXITCODE -ne 0) { throw 'pioasm build/install failed.' }
if (-not (Test-Path -LiteralPath $config)) { throw 'pioasm install did not produce pioasmConfig.cmake.' }
Write-Host "pioasm installed at $install"
