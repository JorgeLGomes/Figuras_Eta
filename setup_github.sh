#!/usr/bin/env bash
# setup_github.sh — Cria repositorio no GitHub e faz push inicial
#
# Pre-requisitos:
#   1. GitHub CLI:  sudo apt install gh   ou   https://cli.github.com
#   2. Autenticado: gh auth login
#
# Uso:
#   chmod +x setup_github.sh
#   ./setup_github.sh
#   ./setup_github.sh --repo Figuras_Eta --private
#   ./setup_github.sh --repo eta-besm --org minha-org --private

set -euo pipefail

# ── Defaults ─────────────────────────────────────────────────────────────────
REPO_NAME="Figuras_Eta"
REPO_DESC="Scripts Python para geracao de figuras 2D do modelo Eta/BESM - 46 variaveis, COG GeoTIFF, acumulados 24h"
ORG=""
VISIBILITY="--public"

# ── Parse argumentos ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --repo)    REPO_NAME="$2"; shift 2 ;;
        --org)     ORG="$2";       shift 2 ;;
        --private) VISIBILITY="--private"; shift ;;
        --public)  VISIBILITY="--public";  shift ;;
        *) echo "Argumento desconhecido: $1"; exit 1 ;;
    esac
done

# ── Cores ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log_info()  { echo -e "${CYAN}[INFO]  $*${NC}"; }
log_ok()    { echo -e "${GREEN}[ OK ]  $*${NC}"; }
log_warn()  { echo -e "${YELLOW}[WARN]  $*${NC}"; }
log_error() { echo -e "${RED}[ERRO]  $*${NC}"; }

# ── Verificar gh CLI ──────────────────────────────────────────────────────────
if ! command -v gh &>/dev/null; then
    log_error "GitHub CLI (gh) nao encontrado."
    echo ""
    echo "  Instale com:"
    echo "    # Ubuntu/Debian:"
    echo "    sudo apt install gh"
    echo "    # ou via snap:"
    echo "    sudo snap install gh"
    echo "    # ou via curl:"
    echo "    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg"
    echo ""
    echo "  Depois autentique:"
    echo "    gh auth login"
    exit 1
fi
log_info "gh CLI: $(gh --version | head -1)"

# ── Verificar autenticacao ────────────────────────────────────────────────────
if ! gh auth status &>/dev/null; then
    log_error "Nao autenticado no GitHub. Execute:"
    echo "    gh auth login"
    exit 1
fi
log_ok "Autenticado no GitHub"

# ── Diretorio raiz do projeto ─────────────────────────────────────────────────
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"
log_info "Projeto: $PROJECT_ROOT"

# ── Verificar repositorio git local ──────────────────────────────────────────
if [[ ! -d ".git" ]]; then
    log_warn "Repositorio git local nao encontrado."
    if [[ -f "setup_git.sh" ]]; then
        log_info "Executando setup_git.sh primeiro..."
        bash setup_git.sh
    else
        log_error "setup_git.sh nao encontrado. Execute-o primeiro."
        exit 1
    fi
fi

# ── Montar flags do gh ────────────────────────────────────────────────────────
GH_FLAGS=("repo" "create" "$REPO_NAME"
    "--description" "$REPO_DESC"
    "--source" "."
    "--push"
    "$VISIBILITY"
)
[[ -n "$ORG" ]] && GH_FLAGS+=("--owner" "$ORG")

# ── Criar repositorio e fazer push ───────────────────────────────────────────
echo ""
log_info "Criando repositorio '$REPO_NAME' no GitHub..."
gh "${GH_FLAGS[@]}"

# ── Obter URL do repositorio ──────────────────────────────────────────────────
REPO_REF="$REPO_NAME"
[[ -n "$ORG" ]] && REPO_REF="$ORG/$REPO_NAME"
REPO_URL=$(gh repo view "$REPO_REF" --json url -q ".url" 2>/dev/null || echo "")

echo ""
echo "-------------------------------------------------------"
log_ok "Repositorio criado e push realizado!"
[[ -n "$REPO_URL" ]] && echo "  URL: $REPO_URL"
echo ""
echo "  Proximos passos:"
echo "    git checkout develop"
echo "    # edite scripts..."
echo "    git add scripts/<arquivo>.py"
echo "    git commit -m 'feat: <descricao>'"
echo "    git push origin develop"
echo ""
echo "    # Merge e nova tag:"
echo "    git checkout main && git merge develop"
echo "    git tag -a v0.2.0 -m 'v0.2.0'"
echo "    git push origin main --tags"
echo "-------------------------------------------------------"
