# Reconstruye el visor de punta a punta.
#
# Uso:
#   .\build.ps1             verifica, renderiza y prueba (usa la base ya consolidada)
#   .\build.ps1 -Fuentes    ademas vuelve a leer 1_Input/fuentes/ y rearma la base
#
# Se detiene en el primer paso que falle.
#
# Quarto y R no necesitan estar en el PATH: si no estan, se buscan donde los
# instalan RStudio, Positron y los instaladores oficiales.

param([switch]$Fuentes)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Find-Quarto {
    $cmd = Get-Command quarto -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $candidatos = @(
        "$env:ProgramFiles\Quarto\bin\quarto.exe",
        "$env:LOCALAPPDATA\Programs\Quarto\bin\quarto.exe",
        "$env:ProgramFiles\RStudio\resources\app\bin\quarto\bin\quarto.exe",
        "$env:LOCALAPPDATA\Programs\Positron\resources\app\quarto\bin\quarto.exe",
        "$env:ProgramFiles\Positron\resources\app\quarto\bin\quarto.exe"
    )
    foreach ($p in $candidatos) { if (Test-Path $p) { return $p } }
    throw "No se encontro Quarto. Instalalo desde https://quarto.org o abre el proyecto en RStudio."
}

# Quarto busca R por su cuenta, pero sin R en el PATH puede no hallarlo.
# Se usa la version mas reciente instalada, salvo que QUARTO_R ya este definida.
function Set-QuartoR {
    if ($env:QUARTO_R) { return }
    if (Get-Command Rscript -ErrorAction SilentlyContinue) { return }
    $r = Get-ChildItem "$env:ProgramFiles\R" -Directory -Filter "R-*" -ErrorAction SilentlyContinue |
        Where-Object { Test-Path (Join-Path $_.FullName "bin\Rscript.exe") } |
        Sort-Object { [version]($_.Name -replace '^R-', '') } -Descending |
        Select-Object -First 1
    if (-not $r) { throw "No se encontro R en $env:ProgramFiles\R." }
    $env:QUARTO_R = Join-Path $r.FullName "bin"
}

# -Omitible: el paso puede devolver 2 cuando le falta una herramienta opcional
# (probar_buscador.py sin Node). Se avisa y se sigue en vez de detenerse.
function Invoke-Paso($titulo, [scriptblock]$comando, [switch]$Omitible) {
    Write-Host "`n== $titulo" -ForegroundColor Cyan
    & $comando
    if ($Omitible -and $LASTEXITCODE -eq 2) {
        Write-Host "   (omitido: falta una herramienta opcional)" -ForegroundColor Yellow
        return
    }
    if ($LASTEXITCODE -ne 0) { throw "Fallo: $titulo" }
}

$quarto = Find-Quarto
Set-QuartoR
Write-Host "Quarto: $quarto"
if ($env:QUARTO_R) { Write-Host "R:      $env:QUARTO_R" }

if ($Fuentes) {
    Invoke-Paso "Extraer fuentes"   { python 2_Process/00_extraer_fuentes.py }
    Invoke-Paso "Consolidar base"   { python 2_Process/01_consolidar_base.py }
}
Invoke-Paso "Verificar logica"      { python tests/verificar_logica.py }
Invoke-Paso "Renderizar"            { & $quarto render }
Invoke-Paso "Verificar salida"      { python tests/verificar_salida.py }
Invoke-Paso "Probar buscador"       { python tests/probar_buscador.py } -Omitible

Write-Host "`nListo: 3_Output/index.html" -ForegroundColor Green
