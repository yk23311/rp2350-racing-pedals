# Export a manufacturer-specific set from the immutable, reviewed V0.1 board.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Push-Location $projectRoot
try {
    . ./deps/kicad/env.ps1
    $cli = './deps/kicad/bin/kicad-cli.exe'
    $stage = 'build/jlc-v0.1'
    $board = 'hardware/carrier/carrier.kicad_pcb'
    New-Item -ItemType Directory -Force -Path "$stage/gerber","$stage/checks" | Out-Null
    function Run-Native([string]$Exe, [string[]]$Arguments) {
        & $Exe @Arguments
        if ($LASTEXITCODE -ne 0) { throw "Native command failed ($LASTEXITCODE): $Exe $Arguments" }
    }
    Run-Native $cli @('sch','erc','hardware/carrier/carrier.kicad_sch',
        '--exit-code-violations','--format','json','-o',"$stage/checks/erc.json")
    Run-Native $cli @('pcb','drc',$board,'--schematic-parity','--exit-code-violations',
        '--format','json','-o',"$stage/checks/drc.json")
    Run-Native $cli @('pcb','export','gerbers',$board,'--no-x2','--no-netlist','--check-zones',
        '--layers','F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts',
        '-o',"$stage/gerber/")
    Run-Native $cli @('pcb','export','pos',$board,'--side','front','--format','csv',
        '--units','mm','--smd-only','--exclude-fp-th','--exclude-dnp','-o',"$stage/carrier-pos.csv")
    Run-Native './.venv/Scripts/python.exe' @('tools/hardware/package_jlc.py')
}
finally { Pop-Location }
