#!/usr/bin/env bash
# run.sh — Executa a geracao de figuras do modelo Eta com logging automatico
#
# Uso:
#   ./run.sh                                     # tudo: PNG + acumulados
#   ./run.sh --cog-only                          # somente COG GeoTIFF
#   ./run.sh --cog --workers 8                   # PNG + COG paralelo
#
# Configuracao do caminho dos dados (escolha uma das opcoes):
#   # 1. Via variavel de ambiente (persistente):
#   export SISMOM_DATA_BASE=/dados/sismom/SisMOM/sismom_forecast
#   ./run.sh --cog-only
#
#   # 2. Via argumento --data-base:
#   ./run.sh --cog-only --data-base /dados/sismom/SisMOM/sismom_forecast
#   # -> usa automaticamente <base>/2026060400/regional/eta/2D/
#
#   # 3. Via --data-dir (caminho completo):
#   ./run.sh --cog-only --data-dir /dados/sismom/SisMOM/sismom_forecast/2026060400/regional/eta/2D
#
# Saida COG: cog/{run}/VARNAME_TIMESTAMP.tif  (flat, sem subpasta por variavel)

set -euo pipefail

# ── Diretorio raiz do projeto ─────────────────────────────────────────────────
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$PROJECT_ROOT/scripts"
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

# ── Cores ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log_info()  { echo -e "${CYAN}[INFO]  $*${NC}"; }
log_ok()    { echo -e "${GREEN}[ OK ]  $*${NC}"; }
log_error() { echo -e "${RED}[ERRO]  $*${NC}"; }

# ── Defaults ──────────────────────────────────────────────────────────────────
DATA_BASE=""    # base SisMOM: /dados/sismom/SisMOM/sismom_forecast
DATA_DIR=""     # caminho direto (substitui DATA_BASE)
OUTPUT_DIR=""
ACCUM_DIR=""
COG_DIR=""
VARS=""
WORKERS=$(nproc 2>/dev/null || echo 4)   # padrao: todos os CPUs
ONLY_ACCUM=0
ONLY_FIELDS=0
SEQUENTIAL=0
COG=0
COG_ONLY=0
COG_OVERVIEWS=0
SKIP_EXISTING=0
QUIET=0

# ── Parse argumentos ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        # Argumentos com valor obrigatorio: verifica se $2 existe
        --data-base)
            [[ $# -lt 2 || "${2:-}" == --* || -z "${2:-}" ]] \
                && { log_info "--data-base sem valor: usando SISMOM_DATA_BASE do ambiente"; shift; } \
                || { DATA_BASE="$2"; shift 2; } ;;
        --data-dir)    DATA_DIR="${2:?'--data-dir requer um valor'}";   shift 2 ;;
        --output-dir)  OUTPUT_DIR="${2:?'--output-dir requer um valor'}"; shift 2 ;;
        --accum-dir)   ACCUM_DIR="${2:?'--accum-dir requer um valor'}";  shift 2 ;;
        --cog-dir)     COG_DIR="${2:?'--cog-dir requer um valor'}";      shift 2 ;;
        --vars)        VARS="${2:?'--vars requer um valor'}";            shift 2 ;;
        --workers)     WORKERS="${2:?'--workers requer um valor'}";      shift 2 ;;
        --only-accum)  ONLY_ACCUM=1;    shift ;;
        --only-fields) ONLY_FIELDS=1;   shift ;;
        --sequential)  SEQUENTIAL=1;    shift ;;
        --cog)         COG=1;           shift ;;
        --cog-only)    COG_ONLY=1;      shift ;;
        --cog-overviews)  COG_OVERVIEWS=1;  shift ;;
        --skip-existing)  SKIP_EXISTING=1; shift ;;
        --quiet)          QUIET=1;         shift ;;
        *) echo "Argumento desconhecido: $1"; exit 1 ;;
    esac
done

# ── Verificar Python ──────────────────────────────────────────────────────────
PYTHON_CMD=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON_CMD="$candidate"
        break
    fi
done
if [[ -z "$PYTHON_CMD" ]]; then
    log_error "Python nao encontrado no PATH."
    exit 1
fi
log_info "$($PYTHON_CMD --version)"

# ── Instalar dependencias automaticamente ────────────────────────────────────
REQ_FILE="$SCRIPTS_DIR/requirements.txt"
if [[ -f "$REQ_FILE" ]]; then
    # Verifica se as dependencias obrigatorias estao instaladas
    MISSING=0
    for pkg in numpy rasterio; do
        if ! "$PYTHON_CMD" -c "import $pkg" 2>/dev/null; then
            MISSING=1
            break
        fi
    done
    # Se --cog-only nao foi passado, verifica matplotlib tambem
    if [[ "$COG_ONLY" -eq 0 ]]; then
        if ! "$PYTHON_CMD" -c "import matplotlib" 2>/dev/null; then
            MISSING=1
        fi
    fi

    if [[ "$MISSING" -eq 1 ]]; then
        log_info "Instalando dependencias de $REQ_FILE ..."
        "$PYTHON_CMD" -m pip install -r "$REQ_FILE" --quiet \
            || { log_error "Falha ao instalar dependencias. Verifique: $REQ_FILE"; exit 1; }
        log_info "Dependencias instaladas."
    fi
fi

# ── Montar argumentos para main.py ───────────────────────────────────────────
PY_ARGS=()
[[ -n "$DATA_BASE"  ]] && PY_ARGS+=("--data_base"  "$DATA_BASE")
[[ -n "$DATA_DIR"   ]] && PY_ARGS+=("--data_dir"   "$DATA_DIR")
[[ -n "$OUTPUT_DIR" ]] && PY_ARGS+=("--output_dir" "$OUTPUT_DIR")
[[ -n "$ACCUM_DIR"  ]] && PY_ARGS+=("--accum_dir"  "$ACCUM_DIR")
[[ -n "$COG_DIR"    ]] && PY_ARGS+=("--cog_dir"    "$COG_DIR")
[[ -n "$VARS"       ]] && PY_ARGS+=("--vars" $VARS)
[[ "$WORKERS"       -gt 1 ]] && PY_ARGS+=("--workers"    "$WORKERS")
[[ "$ONLY_ACCUM"    -eq 1 ]] && PY_ARGS+=("--only_accum")
[[ "$ONLY_FIELDS"   -eq 1 ]] && PY_ARGS+=("--only_fields")
[[ "$SEQUENTIAL"  -eq 1 ]] && PY_ARGS+=("--sequential")
[[ "$COG"           -eq 1 ]] && PY_ARGS+=("--cog")
[[ "$COG_ONLY"      -eq 1 ]] && PY_ARGS+=("--cog_only")
[[ "$COG_OVERVIEWS" -eq 1 ]] && PY_ARGS+=("--cog_overviews")
[[ "$SKIP_EXISTING" -eq 1 ]] && PY_ARGS+=("--skip_existing")
[[ "$QUIET"         -eq 1 ]] && PY_ARGS+=("--quiet")

# ── Log de execucao ───────────────────────────────────────────────────────────
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/run_${TIMESTAMP}.log"

echo "----------------------------------------------------"
log_info "Figuras_Eta - Inicio: $(date '+%d/%m/%Y %H:%M:%S')"
log_info "Scripts : $SCRIPTS_DIR"
log_info "Log     : $LOG_FILE"
echo "----------------------------------------------------"

# ── Executar ──────────────────────────────────────────────────────────────────
START_TIME=$SECONDS

"$PYTHON_CMD" "$SCRIPTS_DIR/main.py" "${PY_ARGS[@]}" 2>&1 | tee "$LOG_FILE"
EXIT_CODE="${PIPESTATUS[0]}"

ELAPSED=$(( SECONDS - START_TIME ))
ELAPSED_FMT=$(printf "%02d:%02d:%02d" $((ELAPSED/3600)) $((ELAPSED%3600/60)) $((ELAPSED%60)))

echo "----------------------------------------------------"
if [[ "$EXIT_CODE" -eq 0 ]]; then
    log_ok "Concluido em $ELAPSED_FMT"
else
    log_error "Falha (codigo $EXIT_CODE) apos $ELAPSED_FMT"
    log_error "Verifique: $LOG_FILE"
fi
echo "----------------------------------------------------"

exit "$EXIT_CODE"
