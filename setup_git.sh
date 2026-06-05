#!/usr/bin/env bash
# setup_git.sh — Inicializa repositorio git local para o projeto Figuras_Eta
#
# Uso:
#   chmod +x setup_git.sh
#   ./setup_git.sh
#   ./setup_git.sh --user "Jorge Luis Gomes" --email "jorgeluisgomes@gmail.com"
#   ./setup_git.sh --user "Jorge Luis Gomes" --email "jorgeluisgomes@gmail.com" --version "0.1.0"

set -euo pipefail

# ── Defaults ────────────────────────────────────────────────────────────────
GIT_USER=""
GIT_EMAIL=""
VERSION="0.1.0"

# ── Parse argumentos ────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --user)    GIT_USER="$2";  shift 2 ;;
        --email)   GIT_EMAIL="$2"; shift 2 ;;
        --version) VERSION="$2";   shift 2 ;;
        *) echo "Argumento desconhecido: $1"; exit 1 ;;
    esac
done

# ── Cores ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log_info()  { echo -e "${CYAN}[INFO]  $*${NC}"; }
log_ok()    { echo -e "${GREEN}[ OK ]  $*${NC}"; }
log_warn()  { echo -e "${YELLOW}[WARN]  $*${NC}"; }
log_error() { echo -e "${RED}[ERRO]  $*${NC}"; }

# ── Verificar git ─────────────────────────────────────────────────────────
if ! command -v git &>/dev/null; then
    log_error "git nao encontrado. Instale com: sudo apt install git"
    exit 1
fi
log_info "Usando: $(git --version)"

# ── Diretorio raiz do projeto ─────────────────────────────────────────────
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"
log_info "Projeto: $PROJECT_ROOT"

# ── Configuracoes de usuario ──────────────────────────────────────────────
[[ -n "$GIT_USER"  ]] && git config user.name  "$GIT_USER"
[[ -n "$GIT_EMAIL" ]] && git config user.email "$GIT_EMAIL"

# ── Inicializar repositorio ───────────────────────────────────────────────
if [[ -d ".git" ]]; then
    log_warn "Repositorio git ja existe -- pulando git init."
else
    git init -b main
    log_ok "Repositorio inicializado (branch: main)"
fi

# ── Criar .gitkeep nos diretorios vazios ──────────────────────────────────
for dir in data "figuras/campos" "figuras/acumulados_24h" cog logs; do
    mkdir -p "$dir"
    touch "$dir/.gitkeep"
    log_info "Criado: $dir/.gitkeep"
done

# ── Adicionar arquivos ao staging ─────────────────────────────────────────
git add scripts/
git add .gitignore
git add setup_git.sh
[[ -f "setup_github.sh" ]]  && git add setup_github.sh
[[ -f "run.sh" ]]            && git add run.sh
[[ -f "requirements.txt" ]] && git add scripts/requirements.txt 2>/dev/null || true

for keep in data/.gitkeep figuras/campos/.gitkeep \
            figuras/acumulados_24h/.gitkeep cog/.gitkeep logs/.gitkeep; do
    git add "$keep" 2>/dev/null || true
done

# ── Commit inicial ────────────────────────────────────────────────────────
COMMIT_MSG="chore: estrutura inicial do projeto Figuras_Eta v${VERSION}

Scripts: config, reader, plot_utils, plot_variables, accumulate, main, export_cog
46 variaveis 2D - Eta03/BESM - COG GeoTIFF + PNG"

git commit -m "$COMMIT_MSG"
log_ok "Commit inicial realizado"

# ── Branches ──────────────────────────────────────────────────────────────
git checkout -b develop
log_ok "Branch 'develop' criada"
git checkout main
log_ok "Voltando para 'main'"

# ── Tag de versao ─────────────────────────────────────────────────────────
git tag -a "v${VERSION}" -m "Versao inicial ${VERSION}"
log_ok "Tag criada: v${VERSION}"

# ── Resumo ────────────────────────────────────────────────────────────────
echo ""
echo "-------------------------------------------------------"
log_ok "Repositorio configurado com sucesso!"
echo ""
echo "  Branches : main, develop"
echo "  Tag      : v${VERSION}"
echo ""
echo "  Para publicar no GitHub:"
echo "    ./setup_github.sh --repo Figuras_Eta --private"
echo ""
echo "  Fluxo de trabalho:"
echo "    git checkout develop"
echo "    # edite scripts..."
echo "    git add scripts/<arquivo>.py"
echo "    git commit -m 'feat: <descricao>'"
echo "    git checkout main && git merge develop"
echo "    git tag -a v0.2.0 -m 'v0.2.0'"
echo "-------------------------------------------------------"
