<#
.SYNOPSIS
    Cria repositorio no GitHub e faz o push inicial do projeto Figuras_Eta.

.PRE-REQUISITOS
    1. GitHub CLI instalado: https://cli.github.com
       winget install --id GitHub.cli
    2. Autenticado:
       gh auth login

.USO
    cd "C:\Projetos\Figuras_Eta"
    PowerShell -ExecutionPolicy Bypass -File setup_github.ps1

    # Opcoes:
    .\setup_github.ps1 -RepoName "Figuras_Eta" -Private
    .\setup_github.ps1 -RepoName "eta-besm-figuras" -Org "nome-da-org"
#>

param(
    [string] $RepoName   = "Figuras_Eta",
    [string] $Org        = "",           # vazio = repositorio pessoal
    [switch] $Private,                   # repositorio privado (padrao: publico)
    [string] $Description = "Scripts Python para geracao de figuras 2D do modelo Eta/BESM - 46 variaveis, COG GeoTIFF, acumulados 24h"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Log-Info  ($msg) { Write-Host "[INFO]  $msg" -ForegroundColor Cyan   }
function Log-Ok    ($msg) { Write-Host "[ OK ]  $msg" -ForegroundColor Green  }
function Log-Warn  ($msg) { Write-Host "[WARN]  $msg" -ForegroundColor Yellow }
function Log-Error ($msg) { Write-Host "[ERRO]  $msg" -ForegroundColor Red    }

# Diretorio do projeto
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
Log-Info "Projeto: $ProjectRoot"

# Verificar gh CLI
if (-not (Get-Command "gh" -ErrorAction SilentlyContinue)) {
    Log-Error "GitHub CLI (gh) nao encontrado."
    Write-Host ""
    Write-Host "  Instale com:"
    Write-Host "    winget install --id GitHub.cli"
    Write-Host "  Depois autentique:"
    Write-Host "    gh auth login"
    exit 1
}
Log-Info "gh CLI: $(gh --version | Select-Object -First 1)"

# Verificar autenticacao
$AuthStatus = gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Log-Error "Nao autenticado no GitHub. Execute:"
    Write-Host "    gh auth login"
    exit 1
}
Log-Ok "Autenticado no GitHub"

# Verificar se repositorio local existe
if (-not (Test-Path ".git")) {
    Log-Warn "Repositorio git local nao encontrado."
    Log-Info "Executando setup_git.ps1 primeiro..."
    if (Test-Path "setup_git.ps1") {
        & PowerShell -ExecutionPolicy Bypass -File "setup_git.ps1"
    } else {
        Log-Error "setup_git.ps1 nao encontrado. Execute-o primeiro."
        exit 1
    }
}

# Montar flags do gh
$GhFlags = @("repo", "create", $RepoName, "--description", $Description, "--source", ".", "--push")
if ($Private)      { $GhFlags += "--private"  }
else               { $GhFlags += "--public"   }
if ($Org -ne "")   { $GhFlags += "--owner"; $GhFlags += $Org }

# Criar repositorio e fazer push
Write-Host ""
Log-Info "Criando repositorio '$RepoName' no GitHub..."
& gh @GhFlags

if ($LASTEXITCODE -ne 0) {
    Log-Error "Falha ao criar repositorio. Verifique o erro acima."
    exit 1
}

# Obter URL do repositorio
$RepoUrl = (gh repo view $RepoName --json url -q ".url") 2>$null
if (-not $RepoUrl -and $Org -ne "") {
    $RepoUrl = (gh repo view "$Org/$RepoName" --json url -q ".url") 2>$null
}

Log-Ok "Repositorio criado e push realizado com sucesso!"
Write-Host ""
Write-Host "-------------------------------------------------------"
Write-Host "  Repositorio : $RepoUrl"
Write-Host ""
Write-Host "  Proximos passos:"
Write-Host "    # Trabalhar em nova feature:"
Write-Host "    git checkout develop"
Write-Host "    # ... editar scripts ..."
Write-Host "    git add scripts\<arquivo>.py"
Write-Host "    git commit -m 'feat: <descricao>'"
Write-Host "    git push origin develop"
Write-Host ""
Write-Host "    # Merge para main e nova tag:"
Write-Host "    git checkout main"
Write-Host "    git merge develop"
Write-Host "    git tag -a v0.2.0 -m 'v0.2.0'"
Write-Host "    git push origin main --tags"
Write-Host "-------------------------------------------------------"
