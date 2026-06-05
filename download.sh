#!/usr/bin/env bash
# download.sh — Download paralelo dos dados Eta/BESM do FTP CPTEC
#
# Uso:
#   chmod +x download.sh
#   ./download.sh                          # run padrao 2026060400
#   ./download.sh --run 2026060400         # run especifico
#   ./download.sh --run 2026060400 --jobs 8
#   ./download.sh --run 2026060400 --soil  # inclui _SOIL
#   ./download.sh --run 2026060400 --list  # listar sem baixar

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
RUN="2026060400"
JOBS=4
NTIMES=121
INCLUDE_SOIL=0
ONLY_CTL=0
DRY_RUN=0
DEST_DIR=""

# ── Parse argumentos ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --run)   RUN="$2";      shift 2 ;;
        --jobs)  JOBS="$2";     shift 2 ;;
        --ntimes) NTIMES="$2";  shift 2 ;;
        --dest)  DEST_DIR="$2"; shift 2 ;;
        --soil)  INCLUDE_SOIL=1; shift ;;
        --only-ctl) ONLY_CTL=1; shift ;;
        --list)  DRY_RUN=1;     shift ;;
        *) echo "Argumento desconhecido: $1"; exit 1 ;;
    esac
done

# ── Caminhos ──────────────────────────────────────────────────────────────────
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -z "$DEST_DIR" ]] && DEST_DIR="$PROJECT_ROOT/data"
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$DEST_DIR" "$LOG_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE="$LOG_DIR/download_${RUN}_${TIMESTAMP}.log"

BASE_URL="https://ftp1.cptec.inpe.br/pesquisa/SisMOM/sismom_forecast/${RUN}/regional/eta/2D"

# ── Cores ─────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log_info()  { local msg="$(date '+%H:%M:%S') [INFO]  $*"; echo -e "${CYAN}${msg}${NC}"; echo "$msg" >> "$LOG_FILE"; }
log_ok()    { local msg="$(date '+%H:%M:%S') [ OK ]  $*"; echo -e "${GREEN}${msg}${NC}"; echo "$msg" >> "$LOG_FILE"; }
log_warn()  { local msg="$(date '+%H:%M:%S') [WARN]  $*"; echo -e "${YELLOW}${msg}${NC}"; echo "$msg" >> "$LOG_FILE"; }
log_error() { local msg="$(date '+%H:%M:%S') [ERRO]  $*"; echo -e "${RED}${msg}${NC}"; echo "$msg" >> "$LOG_FILE"; }

# ── Verificar wget ────────────────────────────────────────────────────────────
if ! command -v wget &>/dev/null; then
    log_error "wget nao encontrado. Instale: sudo apt install wget"
    exit 1
fi

# ── Gerar lista de arquivos ───────────────────────────────────────────────────
generate_file_list() {
    local run="$1"
    local ntimes="$2"

    # Extrai componentes do run: YYYYMMDDHH
    local year="${run:0:4}"
    local month="${run:4:2}"
    local day="${run:6:2}"
    local hour="${run:8:2}"

    # Converte para epoch
    local epoch
    epoch=$(date -d "${year}-${month}-${day} ${hour}:00:00 UTC" +%s 2>/dev/null || \
            python3 -c "from datetime import datetime,timezone; \
                        t=datetime(${year},${month},${day},${hour},tzinfo=timezone.utc); \
                        print(int(t.timestamp()))")

    local suffixes=("2D")
    [[ "$INCLUDE_SOIL" -eq 1 ]] && suffixes+=("SOIL")

    local exts=("bin" "ctl")
    [[ "$ONLY_CTL" -eq 1 ]] && exts=("ctl")

    for (( i=0; i<ntimes; i++ )); do
        local ts_epoch=$(( epoch + i * 3600 ))
        local ts
        ts=$(date -u -d "@${ts_epoch}" +"%Y%m%d%H" 2>/dev/null || \
             python3 -c "from datetime import datetime,timezone,timedelta; \
                         t=datetime(${year},${month},${day},${hour},tzinfo=timezone.utc)+timedelta(hours=${i}); \
                         print(t.strftime('%Y%m%d%H'))")

        for suffix in "${suffixes[@]}"; do
            for ext in "${exts[@]}"; do
                echo "Eta03_BESM_${run}+${ts}_${suffix}.${ext}"
            done
        done
    done
}

# ── Download de um arquivo ────────────────────────────────────────────────────
download_one() {
    local fname="$1"
    local url="${BASE_URL}/${fname}"
    local dest="${DEST_DIR}/${fname}"

    # Verifica tamanho remoto
    local remote_size
    remote_size=$(wget --spider --server-response "$url" 2>&1 | \
                  grep -i "Content-Length" | tail -1 | awk '{print $2}' | tr -d '\r' || echo -1)

    # Pula se ja completo
    if [[ -f "$dest" ]] && [[ "$remote_size" -gt 0 ]] && \
       [[ "$(stat -c%s "$dest" 2>/dev/null || echo 0)" -eq "$remote_size" ]]; then
        log_info "SKIP (completo): $fname"
        return 0
    fi

    # wget -c: retoma download interrompido
    local t_start=$SECONDS
    if wget -c -q --show-progress --timeout=60 --tries=5 --waitretry=10 \
            -O "$dest" "$url" 2>>"$LOG_FILE"; then
        local elapsed=$(( SECONDS - t_start ))
        local size_mb
        size_mb=$(awk "BEGIN {printf \"%.1f\", $(stat -c%s "$dest")/1000000}")
        log_ok "OK  $fname  ${size_mb} MB  ${elapsed}s"
    else
        log_error "FALHA: $fname"
        return 1
    fi
}
export -f download_one log_info log_ok log_warn log_error
export BASE_URL DEST_DIR LOG_FILE

# ── Main ──────────────────────────────────────────────────────────────────────
echo ""
log_info "=========================================="
log_info "Run    : $RUN"
log_info "Dest   : $DEST_DIR"
log_info "Jobs   : $JOBS"
log_info "Log    : $LOG_FILE"
log_info "=========================================="
echo ""

FILE_LIST=()
while IFS= read -r line; do
    FILE_LIST+=("$line")
done < <(generate_file_list "$RUN" "$NTIMES")

log_info "Total de arquivos: ${#FILE_LIST[@]}"

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo ""
    echo "Lista de arquivos (dry-run):"
    for fname in "${FILE_LIST[@]}"; do
        echo "  ${BASE_URL}/${fname}"
    done
    exit 0
fi

# Verifica se parallel esta disponivel
if command -v parallel &>/dev/null; then
    log_info "Usando GNU parallel com $JOBS jobs"
    printf '%s\n' "${FILE_LIST[@]}" | \
        parallel -j "$JOBS" --bar download_one {}
else
    # Fallback: xargs -P
    log_warn "GNU parallel nao encontrado — usando xargs -P ${JOBS}"
    printf '%s\n' "${FILE_LIST[@]}" | \
        xargs -P "$JOBS" -I{} bash -c 'download_one "$@"' _ {}
fi

echo ""
log_ok "Download concluido. Verifique: $LOG_FILE"
