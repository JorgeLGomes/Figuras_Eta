<#
.SYNOPSIS
    Inicializa o repositorio git para o projeto Figuras_Eta.

.DESCRIPTION
    - Inicializa o repositorio git no diretorio do projeto
    - Cria as branches principais: main, develop
    - Faz o commit inicial dos scripts (dados e figuras sao ignorados)
    - Configura tag de versao semantica

.USO
    cd "C:\Users\jorge\Claude\Projects\Figuras Eta"
    PowerShell -ExecutionPolicy Bypass -File setup_git.ps1

    # Com parametros:
    .\setup_git.ps1 -Remote "https://github.com/usuario/Figuras_Eta.git"
#>

param(
    [string]$Remote     = "",
    [string]$UserName   = "",
    [string]$UserEmail  = "",
    [string]$Version    = "0.1.0"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Log-Info  ($msg) { Write-Host "[INFO]  $msg" -ForegroundColor Cyan   }
function Log-Ok    ($msg) { Write-Host "[ OK ]  $msg" -ForegroundColor Green  }
function Log-Warn  ($msg) { Write-Host "[WARN]  $msg" -ForegroundColor Yellow }
function Log-Error ($msg) { Write-Host "[ERRO]  $msg" -ForegroundColor Red    }

# Verificar git instalado
if (-not (Get-Command "git" -ErrorAction SilentlyContinue)) {
    Log-Error "git nao encontrado. Instale em https://git-scm.com/downloads"
    exit 1
}
Log-Info "Usando: $(git --version)"

# Diretorio raiz do projeto
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot
Log-Info "Projeto: $ProjectRoot"

# Configuracoes de usuario (opcionais)
if ($UserName)  { git config user.name  $UserName  }
if ($UserEmail) { git config user.email $UserEmail }

# Inicializar repositorio
if (Test-Path ".git") {
    Log-Warn "Repositorio git ja existe em $ProjectRoot -- pulando git init."
} else {
    git init -b main
    Log-Ok "Repositorio inicializado (branch: main)"
}

# Criar .gitkeep nos diretorios vazios (git nao versiona pastas vazias)
foreach ($dir in @("data", "figuras\campos", "figuras\acumulados_24h", "logs")) {
    $keepFile = Join-Path $dir ".gitkeep"
    if (-not (Test-Path $keepFile)) {
        New-Item -ItemType File -Path $keepFile -Force | Out-Null
        Log-Info "Criado: $keepFile"
    }
}

# Adicionar arquivos ao staging
git add scripts\
git add .gitignore
git add setup_git.ps1

if (Test-Path "run.ps1")          { git add run.ps1 }
if (Test-Path "requirements.txt") { git add requirements.txt }

git add data\.gitkeep
git add "figuras\campos\.gitkeep"
git add "figuras\acumulados_24h\.gitkeep"
git add logs\.gitkeep

# Commit inicial
$CommitMsg = "chore: estrutura inicial do projeto Figuras_Eta v$Version - Scripts: config, reader, plot_utils, plot_variables, accumulate, main - 46 variaveis 2D - Eta03/BESM"
git commit -m $CommitMsg
Log-Ok "Commit inicial realizado"

# Criar branch develop
git checkout -b develop
Log-Ok "Branch 'develop' criada"
git checkout main
Log-Ok "Voltando para 'main'"

# Tag de versao
git tag -a "v$Version" -m "Versao inicial $Version"
Log-Ok "Tag criada: v$Version"

# Remote (opcional)
if ($Remote -ne "") {
    git remote add origin $Remote
    Log-Ok "Remote adicionado: $Remote"
    Log-Info "Para enviar: git push -u origin main --tags"
} else {
    Log-Info "Remote nao configurado. Para adicionar:"
    Log-Info "  git remote add origin <URL>"
    Log-Info "  git push -u origin main --tags"
}

# Resumo
Write-Host ""
Write-Host "-------------------------------------------------------"
Log-Ok "Repositorio configurado com sucesso!"
Write-Host ""
Write-Host "  Branches : main, develop"
Write-Host "  Tag      : v$Version"
Write-Host ""
Write-Host "  Fluxo sugerido:"
Write-Host "    git checkout develop"
Write-Host "    # edite scripts..."
Write-Host "    git add scripts\<arquivo>.py"
Write-Host "    git commit -m 'feat: <descricao>'"
Write-Host "    git checkout main && git merge develop"
Write-Host "    git tag -a v<nova_versao> -m '<msg>'"
Write-Host "-------------------------------------------------------"
