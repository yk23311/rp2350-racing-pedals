$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$vswhere = 'C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe'
$vsRoot = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vsRoot) { throw 'Visual Studio C++ build tools are required.' }
$vcvars = Join-Path $vsRoot 'VC\Auxiliary\Build\vcvars64.bat'
$clangPath = Join-Path $vsRoot 'VC\Tools\Llvm\x64\bin\clang-cl.exe'
$linkerPath = Join-Path $vsRoot 'VC\Tools\Llvm\x64\bin\lld-link.exe'
# clang-cl + LLD avoid the installed MSVC debug-linker MSPDB140 mismatch.
& cmd /d /c "`"$vcvars`" && cmake -S . -B build/clang -G Ninja -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=`"$clangPath`" -DCMAKE_LINKER=`"$linkerPath`" && cmake --build build/clang && ctest --test-dir build/clang --output-on-failure"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$testPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $testPython)) { $testPython = 'python' }
$env:QT_QPA_PLATFORM = 'offscreen'
& $testPython -m unittest discover -s tests -p 'test_*.py' -v
exit $LASTEXITCODE
