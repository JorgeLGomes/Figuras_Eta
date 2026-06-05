#!/usr/bin/env bash
# run.sh — Executa a geracao de figuras do modelo Eta com logging automatico
#
# Uso:
#   chmod +x run.sh
#   ./run.sh                              # tudo: campos PNG + acumulados 24h
#   ./run.sh --only-accum                 # so acumulados 24h
#   ./run.sh --only-fields                # so campos horarios
#   ./run.sh --vars "TP2M MAGV PREC"      # variaveis especificas
#   ./run.sh --workers 8                  # paralelo com 8 processos
#   ./run.sh --cog                        # exportar COG GeoTIFF
#   ./run.sh --cog-only                   # somente COG (sem PNG)
#   ./run.sh --sequential                 # arquivos com marcadores Fortran
#   ./run.sh --data-dir /dados/eta        # diretorio de dados alternativo

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
DATA_DIR=""
OUTPUT_DIR=""
ACCUM_DIR=""
COG_DIR=""
VARS=""
WORKERS=1
ONLY_ACCUM=0
ONLY_FIELDS=0
SEQUENTIAL=0
COG=0
COG_ONLY=0
QUIET=0

# ── Parse argumentos ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --data-dir)    DATA_DIR="$2";   shift 2 ;;
        --output-dir)  OUTPUT_DIR="$2"; shift 2 ;;
        --accum-dir)   ACCUM_DIR="$2";  shift 2 ;;
        --cog-dir)     COG_DIR="$2";    shift 2 ;;
        --vars)        VARS="$2";       shift 2 ;;
        --workers)     WORKERS="$2";    shift 2 ;;
        --only-accum)  ONLY_ACCUM=1;    shift ;;
        --only-fields) ONLY_FIELDS=1;   shift ;;
        --sequential)  SEQUENTIAL=1;    shift ;;
        --cog)         COG=1;           shift ;;
        --cog-only)    COG_ONLY=1;      shift ;;
        --quiet)       QUIET=1;         shift ;;
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

# ── Montar argumentos para main.py ───────────────────────────────────────────
PY_ARGS=()
[[ -n "$DATA_DIR"   ]] && PY_ARGS+=("--data_dir"   "$DATA_DIR")
[[ -n "$OUTPUT_DIR" ]] && PY_ARGS+=("--output_dir" "$OUTPUT_DIR")
[[ -n "$ACCUM_DIR"  ]] && PY_ARGS+=("--accum_dir"  "$ACCUM_DIR")
[[ -n "$COG_DIR"    ]] && PY_ARGS+=("--cog_dir"    "$COG_DIR")
[[ -n "$VARS"       ]] && PY_ARGS+=("--vars" $VARS)
[[ "$WORKERS"   -gt 1 ]] && PY_ARGS+=("--workers"    "$WORKERS")
[[ "$ONLY_ACCUM"  -eq 1 ]] && PY_ARGS+=("--only_accum")
[[ "$ONLY_FIELDS" -eq 1 ]] && PY_ARGS+=("--only_fields")
[[ "$SEQUENTIAL"  -eq 1 ]] && PY_ARGS+=("--sequential")
[[ "$COG"         -eq 1 ]] && PY_ARGS+=("--cog")
[[ "$COG_ONLY"    -eq 1 ]] && PY_ARGS+=("--cog_only")
[[ "$QUIET"       -eq 1 ]] && PY_ARGS+=("--quiet")

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
