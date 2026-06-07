#!/usr/bin/env bash
# run.sh -- Executa a geracao de figuras do modelo Eta com logging automatico
#
# Uso:
#   ./run.sh                                     # tudo: PNG + acumulados
#   ./run.sh --cog-only                          # somente COG GeoTIFF
#   ./run.sh --cog --workers 8                   # PNG + COG paralelo
#   ./run.sh --accum-hours 6                     # acumulado de  6h
#   ./run.sh --accum-hours 24                    # acumulado de 24h (padrao)
#
# Rodada:
#   ./run.sh --run 2026060600          # tag completo YYYYMMDDHH
#   ./run.sh --run 00                  # 00Z de hoje (data do sistema)
#   export RUN_TAG=2026060600          # ou via variavel de ambiente
#
# Saida: {output_dir}/{run_tag}/{var[_ACUMNNh]}/   (campos e acumulados sob o mesmo base)

set -euo pipefail

# ---------------------------------------------------------------------------- #
# Diretorio raiz do projeto
# ---------------------------------------------------------------------------- #
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$PROJECT_ROOT/scripts"
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

# ---------------------------------------------------------------------------- #
# Cores e helpers de log
# ---------------------------------------------------------------------------- #
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log_info()  { echo -e "${CYAN}[INFO]  $*${NC}"; }
log_ok()    { echo -e "${GREEN}[ OK ]  $*${NC}"; }
log_error() { echo -e "${RED}[ERRO]  $*${NC}"; }

# ---------------------------------------------------------------------------- #
# Defaults
# ---------------------------------------------------------------------------- #
RUN_ARG=""
CONFIG_FILE=""
VARS_FILE=""
DATA_BASE=""
DATA_DIR=""
OUTPUT_DIR=""
COG_DIR=""
VARS=""
WORKERS=$(nproc 2>/dev/null || echo 4)
ACCUM_HOURS=24
ONLY_ACCUM=0
ONLY_FIELDS=0
SEQUENTIAL=0
COG=0
COG_ONLY=0
COG_OVERVIEWS=0
SKIP_EXISTING=0
QUIET=0

# ---------------------------------------------------------------------------- #
# Parse argumentos
# ---------------------------------------------------------------------------- #
while [[ $# -gt 0 ]]; do
    case "$1" in
        --run)           RUN_ARG="${2:?'--run requer um valor'}";        shift 2 ;;
        --config)        CONFIG_FILE="${2:?'--config requer um valor'}"; shift 2 ;;
        --vars-file)     VARS_FILE="${2:?'--vars-file requer um valor'}"; shift 2 ;;
        --data-base)
            if [[ $# -lt 2 || "${2:-}" == --* || -z "${2:-}" ]]; then
                log_info "--data-base sem valor: usando SISMOM_DATA_BASE do ambiente"
                shift
            else
                DATA_BASE="$2"; shift 2
            fi ;;
        --data-dir)      DATA_DIR="${2:?'--data-dir requer um valor'}";    shift 2 ;;
        --output-dir)    OUTPUT_DIR="${2:?'--output-dir requer um valor'}"; shift 2 ;;
        --cog-dir)       COG_DIR="${2:?'--cog-dir requer um valor'}";       shift 2 ;;
        --vars)          VARS="${2:?'--vars requer um valor'}";             shift 2 ;;
        --workers)       WORKERS="${2:?'--workers requer um valor'}";       shift 2 ;;
        --accum-hours)   ACCUM_HOURS="${2:?'--accum-hours requer um valor'}"; shift 2 ;;
        --only-accum)    ONLY_ACCUM=1;    shift ;;
        --only-fields)   ONLY_FIELDS=1;   shift ;;
        --sequential)    SEQUENTIAL=1;    shift ;;
        --cog)           COG=1;           shift ;;
        --cog-only)      COG_ONLY=1;      shift ;;
        --cog-overviews) COG_OVERVIEWS=1; shift ;;
        --skip-existing) SKIP_EXISTING=1; shift ;;
        --quiet)         QUIET=1;         shift ;;
        *) echo "Argumento desconhecido: $1"; exit 1 ;;
    esac
done

# ---------------------------------------------------------------------------- #
# Verificar Python
# ---------------------------------------------------------------------------- #
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

# ---------------------------------------------------------------------------- #
# Instalar dependencias automaticamente se necessario
# ---------------------------------------------------------------------------- #
REQ_FILE="$SCRIPTS_DIR/requirements.txt"
if [[ -f "$REQ_FILE" ]]; then
    MISSING=0
    for pkg in numpy rasterio; do
        if ! "$PYTHON_CMD" -c "import $pkg" 2>/dev/null; then
            MISSING=1
            break
        fi
    done
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

# ---------------------------------------------------------------------------- #
# Montar argumentos para main.py
# Usa if/fi em vez de [[ ]] && para compatibilidade com set -e
# ---------------------------------------------------------------------------- #
PY_ARGS=()
if [[ -n "$RUN_ARG"     ]]; then PY_ARGS+=("--run"          "$RUN_ARG");     fi
if [[ -n "$CONFIG_FILE" ]]; then PY_ARGS+=("--config"       "$CONFIG_FILE"); fi
if [[ -n "$VARS_FILE"   ]]; then PY_ARGS+=("--vars-file"    "$VARS_FILE");   fi
if [[ -n "$DATA_BASE"   ]]; then PY_ARGS+=("--data_base"    "$DATA_BASE");   fi
if [[ -n "$DATA_DIR"    ]]; then PY_ARGS+=("--data_dir"     "$DATA_DIR");    fi
if [[ -n "$OUTPUT_DIR"  ]]; then PY_ARGS+=("--output_dir"   "$OUTPUT_DIR");  fi
if [[ -n "$COG_DIR"     ]]; then PY_ARGS+=("--cog_dir"      "$COG_DIR");     fi
if [[ -n "$VARS"        ]]; then PY_ARGS+=("--vars"         $VARS);          fi
if [[ "$ACCUM_HOURS"  -ne 24 ]]; then PY_ARGS+=("--accum_hours"  "$ACCUM_HOURS"); fi
if [[ "$WORKERS"      -gt 1  ]]; then PY_ARGS+=("--workers"      "$WORKERS");     fi
if [[ "$ONLY_ACCUM"   -eq 1  ]]; then PY_ARGS+=("--only_accum");   fi
if [[ "$ONLY_FIELDS"  -eq 1  ]]; then PY_ARGS+=("--only_fields");  fi
if [[ "$SEQUENTIAL"   -eq 1  ]]; then PY_ARGS+=("--sequential");   fi
if [[ "$COG"          -eq 1  ]]; then PY_ARGS+=("--cog");          fi
if [[ "$COG_ONLY"     -eq 1  ]]; then PY_ARGS+=("--cog_only");     fi
if [[ "$COG_OVERVIEWS" -eq 1 ]]; then PY_ARGS+=("--cog_overviews"); fi
if [[ "$SKIP_EXISTING" -eq 1 ]]; then PY_ARGS+=("--skip_existing"); fi
if [[ "$QUIET"        -eq 1  ]]; then PY_ARGS+=("--quiet");         fi

# ---------------------------------------------------------------------------- #
# Log de execucao
# ---------------------------------------------------------------------------- #
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/run_${TIMESTAMP}.log"

echo "----------------------------------------------------"
log_info "Figuras_Eta - Inicio: $(date '+%d/%m/%Y %H:%M:%S')"
log_info "Scripts : $SCRIPTS_DIR"
log_info "Log     : $LOG_FILE"
echo "----------------------------------------------------"

# ---------------------------------------------------------------------------- #
# Executar
# ---------------------------------------------------------------------------- #
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
                                                                                                                                                                          