"""
download_data.py — Download paralelo dos dados do modelo Eta/BESM do FTP CPTEC

Fonte: https://ftp1.cptec.inpe.br/pesquisa/SisMOM/sismom_forecast/<RUN>/regional/eta/2D/

Funcionalidades:
  - Download paralelo (--workers)
  - Retomada automatica de downloads interrompidos (HTTP Range / arquivo parcial)
  - Verifica tamanho do arquivo ja baixado (pula se completo)
  - Barra de progresso por arquivo e total
  - Log de erros em logs/download_<run>.log
  - Suporta _2D (default) e/ou _SOIL

Uso:
    python scripts/download_data.py
    python scripts/download_data.py --run 2026060400 --workers 4
    python scripts/download_data.py --run 2026060400 --soil       # inclui SOIL
    python scripts/download_data.py --run 2026060400 --only-ctl   # so .ctl
    python scripts/download_data.py --list                        # lista sem baixar

Dependencias (stdlib apenas — sem pip):
    urllib.request, concurrent.futures, argparse, logging
"""

import os
import sys
import argparse
import logging
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

# ── Configuracao ──────────────────────────────────────────────────────────────

BASE_URL_TEMPLATE = (
    "https://ftp1.cptec.inpe.br/pesquisa/SisMOM/sismom_forecast"
    "/{run}/regional/eta/2D/"
)

# Modelo de nome de arquivo
# Eta03_BESM_{RUN}+{TIMESTAMP}_2D.bin
FILE_TEMPLATE = "Eta03_BESM_{run}+{ts}_{suffix}.{ext}"

RUN_DEFAULT    = "2026060400"
T0_DEFAULT     = datetime(2026, 6, 4, 0)
NTIMES_DEFAULT = 121
DT_HOURS       = 1

CHUNK_SIZE     = 8 * 1024 * 1024   # 8 MB por chunk
MAX_RETRIES    = 5
RETRY_WAIT     = 10                 # segundos entre tentativas

# ── Helpers ───────────────────────────────────────────────────────────────────

def _run_to_t0(run: str) -> datetime:
    """Converte string de run 'YYYYMMDDHH' para datetime."""
    return datetime.strptime(run, "%Y%m%d%H")


def build_file_list(run: str, ntimes: int, include_soil: bool = False,
                    only_ctl: bool = False) -> list:
    """
    Retorna lista de (url, filename) para todos os timesteps do run.

    Parameters
    ----------
    run         : tag do run (ex: '2026060400')
    ntimes      : numero de passos de tempo
    include_soil: incluir arquivos _SOIL
    only_ctl    : baixar apenas .ctl (sem .bin)
    """
    base_url = BASE_URL_TEMPLATE.format(run=run)
    t0       = _run_to_t0(run)
    files    = []

    suffixes = ["2D"]
    if include_soil:
        suffixes.append("SOIL")

    exts = ["ctl"] if only_ctl else ["bin", "ctl"]

    for i in range(ntimes):
        ts = (t0 + timedelta(hours=i)).strftime("%Y%m%d%H")
        for suffix in suffixes:
            for ext in exts:
                fname = FILE_TEMPLATE.format(run=run, ts=ts, suffix=suffix, ext=ext)
                url   = base_url + fname
                files.append((url, fname))

    return files


def get_remote_size(url: str, timeout: int = 30) -> int:
    """Retorna o Content-Length do arquivo remoto via HEAD request. -1 se desconhecido."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return int(resp.headers.get("Content-Length", -1))
    except Exception:
        return -1


def download_file(url: str, dest: Path, logger: logging.Logger,
                  chunk_size: int = CHUNK_SIZE,
                  max_retries: int = MAX_RETRIES) -> tuple:
    """
    Baixa um arquivo com suporte a retomada (HTTP Range).

    Returns
    -------
    (filename, status, bytes_downloaded, elapsed_s)
    status: 'ok' | 'skipped' | 'error'
    """
    fname   = dest.name
    t_start = time.time()

    for attempt in range(1, max_retries + 1):
        try:
            # Verifica tamanho remoto
            remote_size = get_remote_size(url)

            # Verifica se arquivo ja esta completo
            if dest.exists() and remote_size > 0 and dest.stat().st_size == remote_size:
                logger.info(f"SKIP (completo): {fname}")
                return (fname, "skipped", 0, 0.0)

            # Calcula bytes ja baixados (retomada)
            local_size = dest.stat().st_size if dest.exists() else 0
            headers    = {}
            mode       = "ab" if local_size > 0 else "wb"

            if local_size > 0 and remote_size > 0 and local_size < remote_size:
                headers["Range"] = f"bytes={local_size}-"
                logger.info(f"RESUME {fname} ({local_size/1e6:.1f}/{remote_size/1e6:.1f} MB)")
            else:
                if local_size > 0:
                    dest.unlink()       # arquivo corrompido ou maior que remoto
                    mode = "wb"
                logger.info(f"START {fname} ({remote_size/1e6:.1f} MB)")

            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp, \
                 open(dest, mode) as fout:
                downloaded = 0
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    fout.write(chunk)
                    downloaded += len(chunk)

            elapsed = time.time() - t_start
            total   = dest.stat().st_size
            speed   = total / elapsed / 1e6 if elapsed > 0 else 0
            logger.info(
                f"OK {fname} | {total/1e6:.1f} MB | {elapsed:.1f}s | {speed:.1f} MB/s"
            )
            return (fname, "ok", downloaded, elapsed)

        except urllib.error.HTTPError as e:
            if e.code == 404:
                logger.warning(f"NAO ENCONTRADO (404): {fname}")
                return (fname, "skipped", 0, 0.0)
            logger.warning(f"HTTP {e.code} em {fname} (tentativa {attempt}/{max_retries})")
        except Exception as e:
            logger.warning(f"ERRO em {fname} tentativa {attempt}/{max_retries}: {e}")

        if attempt < max_retries:
            time.sleep(RETRY_WAIT * attempt)

    logger.error(f"FALHOU apos {max_retries} tentativas: {fname}")
    return (fname, "error", 0, time.time() - t_start)


# ── Orquestrador ──────────────────────────────────────────────────────────────

def download_run(
    run: str,
    dest_dir: Path,
    log_dir: Path,
    workers: int = 4,
    ntimes: int = NTIMES_DEFAULT,
    include_soil: bool = False,
    only_ctl: bool = False,
    dry_run: bool = False,
):
    dest_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Logger
    log_file = log_dir / f"download_{run}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    logger = logging.getLogger("download")

    # Lista de arquivos
    file_list = build_file_list(run, ntimes, include_soil, only_ctl)
    n_total   = len(file_list)

    logger.info("=" * 60)
    logger.info(f"Run       : {run}")
    logger.info(f"Arquivos  : {n_total}")
    logger.info(f"Destino   : {dest_dir}")
    logger.info(f"Workers   : {workers}")
    logger.info(f"Log       : {log_file}")
    logger.info("=" * 60)

    if dry_run:
        for url, fname in file_list:
            size = get_remote_size(url)
            print(f"  {fname}  ({size/1e6:.1f} MB)" if size > 0 else f"  {fname}")
        return

    # Download paralelo
    t0       = time.time()
    n_ok     = 0
    n_skip   = 0
    n_err    = 0
    total_mb = 0.0

    tasks = [(url, dest_dir / fname, logger) for url, fname in file_list]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(download_file, url, dest, logger): fname
            for url, dest, logger in [(u, d, logger) for u, d in file_list
                                       for _ in [None]]
        }
        # Reconstroi corretamente
        futures = {}
        for url, fname in file_list:
            dest = dest_dir / fname
            fut  = pool.submit(download_file, url, dest, logger)
            futures[fut] = fname

        done = 0
        for fut in as_completed(futures):
            fname, status, dl_bytes, elapsed = fut.result()
            done += 1
            pct   = done / n_total * 100
            total_mb += dl_bytes / 1e6

            if status == "ok":
                n_ok   += 1
            elif status == "skipped":
                n_skip += 1
            else:
                n_err  += 1

            logger.info(
                f"[{done:3d}/{n_total}  {pct:5.1f}%]  {status.upper():7s}  {fname}"
            )

    elapsed_total = time.time() - t0
    logger.info("=" * 60)
    logger.info(
        f"Concluido: {n_ok} baixados, {n_skip} ignorados, {n_err} erros"
        f" | {total_mb:.1f} MB em {elapsed_total:.1f}s"
    )
    logger.info("=" * 60)

    if n_err > 0:
        logger.warning(f"Verifique os erros em: {log_file}")
        sys.exit(1)


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Download dos dados do modelo Eta/BESM do FTP CPTEC"
    )
    p.add_argument("--run",     default=RUN_DEFAULT,
                   help=f"Tag do run YYYYMMDDHH (padrao: {RUN_DEFAULT})")
    p.add_argument("--dest",    default=None,
                   help="Diretorio de destino (padrao: data/ relativo ao script)")
    p.add_argument("--workers", type=int, default=4,
                   help="Downloads em paralelo (padrao: 4)")
    p.add_argument("--ntimes",  type=int, default=NTIMES_DEFAULT,
                   help=f"Numero de passos de tempo (padrao: {NTIMES_DEFAULT})")
    p.add_argument("--soil",    action="store_true",
                   help="Incluir arquivos _SOIL (default: so _2D)")
    p.add_argument("--only-ctl", action="store_true",
                   help="Baixar apenas arquivos .ctl (sem .bin)")
    p.add_argument("--list",    action="store_true",
                   help="Listar arquivos sem baixar (dry-run)")
    return p.parse_args()


def main():
    args = parse_args()

    scripts_dir = Path(__file__).parent.resolve()
    project_root = scripts_dir.parent

    dest_dir = Path(args.dest) if args.dest else project_root / "data"
    log_dir  = project_root / "logs"

    download_run(
        run          = args.run,
        dest_dir     = dest_dir,
        log_dir      = log_dir,
        workers      = args.workers,
        ntimes       = args.ntimes,
        include_soil = args.soil,
        only_ctl     = args.only_ctl,
        dry_run      = args.list,
    )


if __name__ == "__main__":
    main()
