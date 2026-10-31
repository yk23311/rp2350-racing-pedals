param([ValidatePattern('^[R-Z]$')][string]$DriveLetter = 'R', [ValidateSet('xinput','hid')][string]$UsbMode = 'xinput')
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$toolchainName = 'arm-gnu-toolchain-14.3.rel1-mingw-w64-x86_64-arm-none-eabi'
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot "deps\$toolchainName\bin\arm-none-eabi-gcc.exe"))) {
    throw 'Run python tools/fetch_deps.py first.'
}
# Arm's Windows linker cannot resolve its libraries in this Unicode path.
# Map only this project for this build; never replace an existing drive.
$drive = $DriveLetter + ':'
$mappedRoot = $drive + '/'
$subst = Join-Path $env:SystemRoot 'System32\subst.exe'
if (Test-Path ($drive + '\')) { throw "$drive is occupied. Select another free letter with -DriveLetter S." }
& $subst $drive $projectRoot
if ($LASTEXITCODE -ne 0) { throw 'Temporary SUBST mapping failed; run in a normal local PowerShell session.' }
$build = "build/firmware-$UsbMode-$DriveLetter"
$native = if ($UsbMode -eq 'xinput') { 'ON' } else { 'OFF' }
$output = "dist/$UsbMode"
$artifact = "pedals-$UsbMode"
try {
    cmake -S $mappedRoot -B ($mappedRoot + $build) -G Ninja -DPEDAL_FIRMWARE=ON "-DPEDAL_USB_XINPUT=$native" "-DPICO_SDK_PATH=${mappedRoot}deps/pico-sdk-2.2.0" "-DPICO_TOOLCHAIN_PATH=${mappedRoot}deps/$toolchainName" -DPICO_BOARD=waveshare_rp2350_usb_a -DPICO_PLATFORM=rp2350-arm-s -DPICO_NO_PICOTOOL=1 -DCMAKE_BUILD_TYPE=Release
    if ($LASTEXITCODE -ne 0) { throw 'Firmware configure failed.' }
    cmake --build ($mappedRoot + $build) --parallel 4
    if ($LASTEXITCODE -ne 0) { throw 'Firmware build failed.' }
    New-Item -ItemType Directory -Path (Join-Path $projectRoot $output) -Force | Out-Null
    foreach ($extension in @('elf','bin','elf.map')) {
        Copy-Item -LiteralPath (Join-Path $projectRoot "$build/firmware/pedals.$extension") -Destination (Join-Path $projectRoot "$output/$artifact.$extension")
    }
    python tools/bin_to_uf2.py "$output/$artifact.bin" "$output/$artifact.uf2"
    if ($LASTEXITCODE -ne 0) { throw 'UF2 packaging failed.' }
    & "${mappedRoot}deps/$toolchainName/bin/arm-none-eabi-size.exe" "$output/$artifact.elf"
    if ($LASTEXITCODE -ne 0) { throw 'ELF size inspection failed.' }
} finally {
    & $subst $drive /D
}
