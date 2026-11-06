param(
    [switch]$Route,
    [switch]$Rebuild,
    [string]$JavaExe = 'C:/Program Files/Microsoft/jdk-21.0.12.8-hotspot/bin/java.exe'
)

# Run from any directory. Default: verify/export the current editable board.
# -Rebuild: regenerate placement and re-import the retained SES.
# -Route: regenerate DSN, run the verified offline Java router, then import SES.
# Official JAR: https://github.com/freerouting/freerouting/releases/download/v2.1.0/freerouting-2.1.0.jar
# GitHub release asset size: 66,978,394 bytes. No release digest was published;
# the SHA256 below records the exact official asset downloaded for this design.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Push-Location $projectRoot
try {
    . ./deps/kicad/env.ps1
    $cli = './deps/kicad/bin/kicad-cli.exe'
    $python = './deps/kicad/bin/python.exe'
    $board = 'hardware/carrier/carrier.kicad_pcb'
    $preview = 'hardware/carrier/previews'
    $reports = 'hardware/carrier/reports'
    $fab = 'hardware/carrier/fabrication/'
    New-Item -ItemType Directory -Force -Path $preview,$reports,$fab | Out-Null

    function Run-Native([string]$Exe, [string[]]$Arguments) {
        & $Exe @Arguments
        if ($LASTEXITCODE -ne 0) { throw "Native command failed ($LASTEXITCODE): $Exe $Arguments" }
    }

    if ($Route) {
        $jar = 'deps/freerouting/freerouting-2.1.0.jar'
        $sha256 = '2C07D58F75DAC03782664081E7A58B41C25400D871A9FCF166A2EA6FE60D5DEF'
        if ((Get-Item -LiteralPath $jar).Length -ne 66978394 -or
            (Get-FileHash -LiteralPath $jar -Algorithm SHA256).Hash -ne $sha256) {
            throw 'Freerouting JAR differs from the retained official asset.'
        }
        Run-Native $python @('-I','tools/hardware/build_pcb.py')
        # Disable GUI/API/analytics. The local refusal proxy also prevents the
        # unconditional background version checker from reaching the internet.
        & $JavaExe '-Djava.awt.headless=true' '-Dhttps.proxyHost=127.0.0.1' '-Dhttps.proxyPort=9' `
            '-Dhttp.proxyHost=127.0.0.1' '-Dhttp.proxyPort=9' -jar $jar `
            -de "$reports/carrier-unrouted.dsn" -do "$reports/carrier-routed.ses" `
            -da '--gui.enabled=false' '--api_server.enabled=false' `
            '--user_data_path=deps/freerouting/java21-user-data' -mp 40 -mt 1 *> "$reports/autoroute.log"
        if ($LASTEXITCODE -ne 0) { throw 'Freerouting failed; inspect reports/autoroute.log.' }
    }
    if ($Route -or $Rebuild) {
        Run-Native $python @('-I','tools/hardware/build_pcb.py','--import-session',"$reports/carrier-routed.ses")
    }

    # Gate all manufacturing and preview exports on native ERC, DRC and parity.
    Run-Native $cli @('sch','erc','hardware/carrier/carrier.kicad_sch','--exit-code-violations',
        '-o',"$reports/erc.rpt")
    Run-Native $cli @('sch','erc','hardware/carrier/carrier.kicad_sch','--exit-code-violations',
        '--format','json','-o',"$reports/erc.json")
    Run-Native $cli @('pcb','drc',$board,'--schematic-parity','--refill-zones','--save-board',
        '--exit-code-violations','-o',"$reports/drc.rpt")
    Run-Native $cli @('pcb','drc',$board,'--schematic-parity','--exit-code-violations',
        '--format','json','-o',"$reports/drc.json")
    Run-Native $cli @('pcb','export','svg',$board,'--layers','F.Cu,F.Silkscreen,Edge.Cuts',
        '--mode-single','--page-size-mode','2','--exclude-drawing-sheet','--check-zones',
        '-o',"$preview/carrier-pcb-top.svg")
    Run-Native $cli @('pcb','export','svg',$board,'--layers','F.Silkscreen,F.Fab,Edge.Cuts,Dwgs.User',
        '--mode-single','--page-size-mode','2','--exclude-drawing-sheet','--black-and-white',
        '-o',"$preview/carrier-assembly-top.svg")
    # Five pages at 1:1: front copper, back copper, silk, fabrication, clearance.
    Run-Native $cli @('pcb','export','pdf',$board,'--layers','F.Cu,B.Cu,F.Silkscreen,F.Fab,Dwgs.User',
        '--common-layers','Edge.Cuts','--mode-multipage','--check-zones','--black-and-white',
        '--no-property-popups','-o',"$preview/carrier-pcb.pdf")
    Run-Native $cli @('pcb','export','gerbers',$board,
        '--layers','F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts',
        '--check-zones','-o',$fab)
    Run-Native $cli @('pcb','export','drill',$board,'--format','excellon','--excellon-units','mm',
        '--excellon-separate-th','--generate-map','--map-format','pdf','--generate-report',
        '--report-path',"$reports/drill.rpt",'-o',$fab)
    Run-Native $cli @('pcb','render',$board,'--output',"$preview/carrier-3d-top.png",'--side','top',
        '--width','2000','--height','1600','--background','opaque','--quality','high','--zoom','1.15')
    # 325 degrees is -35 degrees; positive notation avoids CLI option parsing.
    Run-Native $cli @('pcb','render',$board,'--output',"$preview/carrier-3d-isometric.png",'--side','top',
        '--width','2000','--height','1600','--background','opaque','--quality','high',
        '--rotate','325,0,30','--perspective','--zoom','0.72')
    # Optional Poppler page previews: 254 dpi = 10 pixels/mm. The crop only
    # removes the unused A4 area; the five-page PDF retains its native 1:1 scale.
    if (Get-Command pdftoppm -ErrorAction SilentlyContinue) {
        Run-Native 'pdftoppm' @('-png','-r','254','-x','0','-y','0','-W','1002','-H','802',
            "$preview/carrier-pcb.pdf","$preview/carrier-pcb-page")
    }
}
finally {
    Pop-Location
}
