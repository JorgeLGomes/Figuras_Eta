<#
.SYNOPSIS
    Executa a geracao de figuras do modelo Eta com logging automatico.

.USO
    cd C:\Projetos\Figuras_Eta
    .\run.ps1                          # tudo: campos + acumulados 24h
    .\run.ps1 -OnlyAccum               # so acumulados 24h
    .\run.ps1 -OnlyFields              # so campos horarios
    .\run.ps1 -Vars "TP2M MAGV PREC"   # variaveis especificas
    .\run.ps1 -Workers 4               # paralelo com 4 processos
    .\run.ps1 -Sequential              # arquivos com marcadores Fortran
    .\run.ps1 -DataDir "D:\dados\eta"  # diretorio de dados alternativo
#>

param(
    [string] $DataDir    = "",
    [string] $OutputDir  = "",
    [string] $AccumDir   = "",
    [string] $Vars       = "",
    [int]    $Workers    = 1,
    [switch] $OnlyAccum,
    [switch] $OnlyFields,
    [switch] $Sequential,
    [switch] $Quiet
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ScriptsDir  = Join-Path $ProjectRoot "scripts"
$LogDir      = Join-Path $ProjectRoot "logs"

# Verificar Python
$PythonCmd = $null
foreach ($candidate in @("python", "python3", "py")) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        $PythonCmd = $candidate
        break
    }
}
if (-not $PythonCmd) {
    Write-Host "[ERRO] Python nao encontrado no PATH." -ForegroundColor Red
    exit 1
}
$PyVersion = & $PythonCmd --version 2>&1
Write-Host "[INFO] $PyVersion" -ForegroundColor Cyan

# Montar argumentos para main.py
$CmdArgs = @()

if ($DataDir   -ne "") { $CmdArgs += "--data_dir";   $CmdArgs += $DataDir   }
if ($OutputDir -ne "") { $CmdArgs += "--output_dir"; $CmdArgs += $OutputDir }
if ($AccumDir  -ne "") { $CmdArgs += "--accum_dir";  $CmdArgs += $AccumDir  }
if ($Vars      -ne "") { $CmdArgs += "--vars";        $CmdArgs += $Vars.Split(" ") }
if ($Workers    -gt 1) { $CmdArgs += "--workers";    $CmdArgs += $Workers   }
if ($OnlyAccum)        { $CmdArgs += "--only_accum"  }
if ($OnlyFields)       { $CmdArgs += "--only_fields" }
if ($Sequential)       { $CmdArgs += "--sequential"  }
if ($Quiet)            { $CmdArgs += "--quiet"        }

# Log de execucao
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile   = Join-Path $LogDir "run_ps_$Timestamp.log"

Write-Host "----------------------------------------------------" -ForegroundColor DarkGray
Write-Host "  Figuras_Eta - Inicio: $(Get-Date -Format 'dd/MM/yyyy HH:mm:ss')"
Write-Host "  Scripts : $ScriptsDir"
Write-Host "  Log     : $LogFile"
Write-Host "----------------------------------------------------" -ForegroundColor DarkGray

# Executar
$Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

& $PythonCmd (Join-Path $ScriptsDir "main.py") @CmdArgs 2>&1 | Tee-Object -FilePath $LogFile

$Stopwatch.Stop()
$Elapsed = $Stopwatch.Elapsed.ToString("hh\:mm\:ss")

Write-Host "----------------------------------------------------" -ForegroundColor DarkGray
if ($LASTEXITCODE -eq 0) {
    Write-Host "  [ OK ] Concluido em $Elapsed" -ForegroundColor Green
} else {
    Write-Host "  [ERRO] Falha (codigo $LASTEXITCODE) apos $Elapsed" -ForegroundColor Red
    Write-Host "  Verifique: $LogFile" -ForegroundColor Yellow
}
Write-Host "----------------------------------------------------" -ForegroundColor DarkGray

exit $LASTEXITCODE
