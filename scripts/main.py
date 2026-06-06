"""
main.py -- Orquestrador principal de geracao de figuras do modelo Eta

Uso:
    python main.py --data_dir /caminho/para/bins
    python main.py --data_dir . --vars TP2M MAGV PREC --sequential
    python main.py --data_dir . --only_accum        # somente acumulados 24h
    python main.py --data_dir . --workers 4         # paralelo (multiprocessing)
    python main.py --data_dir . --cog               # exportar COG GeoTIFF
    python main.py --data_dir . --cog --only_accum  # somente acumulados 24h como COG

Estrutura de saida:
    figuras/campos/    -- PNG por variavel/timestep
    figuras/acumulados_24h/ -- PNG acumulados
    cog/               -- COG GeoTIFF (quando --cog ativado)
"""

import os
import sys
import argparse
import time
import logging
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

import config
import reader
import accumulate
import export_cog

# plot_variables / plot_utils (matplotlib) so sao importados quando necessario
# Evita erro de ModuleNotFoundError em modo --cog-only sem matplotlib instalado
pv = None
def _load_plot_modules():
    global pv
    if pv is None:
        import plot_variables as _pv
        pv = _pv


# ──────────────────────────────────────────────────────────────────────────────
# WORKER OTIMIZADO — lê o arquivo UMA vez e gera TODAS as variáveis
# Reduz I/O em 46x comparado ao worker por variável individual
# ──────────────────────────────────────────────────────────────────────────────

def _worker_timestep(args):
    """
    Worker por timestep: lê todos os campos do arquivo de uma vez
    e gera as figuras de todas as variáveis solicitadas.

    Estrategia:
      - 1 leitura de arquivo .bin por timestep (read_all_fields)
      - N plots em sequencia (sem I/O adicional)

    Returns list of (var_name, fpath, error)
    """
    data_dir, timestamp, vars_to_plot, output_dir, sequential, skip_existing = args
    _load_plot_modules()
    results = []

    try:
        fields = reader.read_all_fields(data_dir, timestamp, sequential=sequential)
    except Exception as e:
        return [(v, None, f"Leitura falhou: {e}") for v in vars_to_plot]

    for var_name in vars_to_plot:
        out_dir = os.path.join(output_dir, var_name)
        ts_str  = timestamp.strftime('%Y%m%d%H')

        # Pula se arquivo ja existe (--skip_existing)
        expected = os.path.join(out_dir, f"{var_name}_{ts_str}.{config.FIG_EXT}")
        if skip_existing and os.path.exists(expected):
            results.append((var_name, expected, None))
            continue

        try:
            data  = fields[var_name]
            fpath = pv.plot_variable(var_name, data, timestamp, out_dir)
            results.append((var_name, fpath, None))
        except Exception as e:
            results.append((var_name, None, str(e)))

    return results


# ──────────────────────────────────────────────────────────────────────────────
# GERAÇÃO DE FIGURAS HORÁRIAS / POR PASSO
# ──────────────────────────────────────────────────────────────────────────────

def generate_all_fields(
    data_dir: str,
    output_dir: str,
    vars_to_plot: list = None,
    sequential: bool = False,
    workers: int = 1,
    verbose: bool = True,
    skip_existing: bool = False,
):
    """
    Itera sobre todos os timesteps disponíveis e gera figuras para todas as
    variáveis. Usa leitura por timestep (1 I/O por arquivo) para maximo desempenho.

    Parameters
    ----------
    data_dir       : diretório com os arquivos .bin
    output_dir     : raiz das figuras de saída (subpasta por variável)
    vars_to_plot   : lista de variáveis (None = todas)
    sequential     : True se .bin usa marcadores Fortran
    workers        : processos paralelos — cada processo processa 1 timestep
    verbose        : imprime progresso
    skip_existing  : pula figuras já geradas
    """
    vars_to_plot = vars_to_plot or config.VAR_NAMES
    timestamps   = reader.list_available_timestamps(data_dir)

    if not timestamps:
        print(f"[main] AVISO: nenhum .bin encontrado em '{data_dir}'.")
        print(f"[main] Padrao: {config.FILE_PREFIX}YYYYMMDDHH{config.FILE_SUFFIX}")
        return

    n_total = len(timestamps) * len(vars_to_plot)
    if verbose:
        print(
            f"[main] {len(timestamps)} timesteps x {len(vars_to_plot)} variaveis"
            f" = {n_total} figuras | workers={workers}"
            + (" | skip_existing=True" if skip_existing else "")
        )

    # Cria subpastas de saida
    for var in vars_to_plot:
        os.makedirs(os.path.join(output_dir, var), exist_ok=True)

    # Tarefas por timestep (1 leitura = todas as variáveis)
    tasks = [
        (data_dir, t, vars_to_plot, output_dir, sequential, skip_existing)
        for t in timestamps
    ]

    t0    = time.time()
    n_ok  = 0
    n_skip = 0
    n_err = 0
    done  = 0

    def _process_results(res_list, ts):
        nonlocal n_ok, n_skip, n_err, done
        done += 1
        pct = done / len(tasks) * 100
        for var_name, fpath, err in res_list:
            if err:
                n_err += 1
                logging.warning(f"ERRO {var_name} {ts.strftime('%Y%m%d%H')}: {err}")
                if verbose:
                    print(f"  [ERRO] {var_name} {ts.strftime('%Y%m%d%H')}: {err}")
            elif fpath and "skip" not in str(fpath).lower():
                n_ok += 1
            else:
                n_skip += 1
        if verbose:
            elapsed = time.time() - t0
            eta = (elapsed / done) * (len(tasks) - done) if done > 0 else 0
            print(
                f"  [{done:3d}/{len(tasks)}  {pct:5.1f}%]"
                f"  ok={n_ok}  skip={n_skip}  err={n_err}"
                f"  t={elapsed:.0f}s  ETA={eta:.0f}s"
                f"  {ts.strftime('%Y%m%d%H')}",
                end="\r" if not verbose else "\n",
                flush=True,
            )

    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futs = {pool.submit(_worker_timestep, task): task for task in tasks}
            for fut in as_completed(futs):
                task = futs[fut]
                ts   = task[1]
                try:
                    results = fut.result()
                    _process_results(results, ts)
                except Exception as e:
                    n_err += len(vars_to_plot)
                    done  += 1
                    logging.error(f"Worker crash {ts.strftime('%Y%m%d%H')}: {e}")
    else:
        for task in tasks:
            ts      = task[1]
            results = _worker_timestep(task)
            _process_results(results, ts)

    if verbose:
        print()  # nova linha apos \r
    elapsed = time.time() - t0
    speed   = n_ok / elapsed if elapsed > 0 else 0
    print(
        f"\n[main] PNG: {n_ok} geradas, {n_skip} ignoradas, {n_err} erros"
        f" | {elapsed:.1f}s ({speed:.1f} fig/s)"
    )


# ──────────────────────────────────────────────────────────────────────────────
# GERAÇÃO DE ACUMULADOS 24H
# ──────────────────────────────────────────────────────────────────────────────

def generate_24h_accumulations(
    data_dir: str,
    output_dir: str,
    sequential: bool = False,
    verbose: bool = True,
):
    """Gera figuras de acumulado 24h para PREC, PRCV e PRGE."""
    if verbose:
        print(f"\n[main] Gerando acumulados 24h para: {config.PRECIP_VARS}")
    saved = accumulate.plot_all_24h_accumulations(data_dir, output_dir, sequential)
    total = sum(len(v) for v in saved.values())
    if verbose:
        print(f"[main] {total} figuras de acumulado 24h geradas.")
    return saved


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Gera figuras do modelo Eta para todas as variáveis 2D."
    )
    parser.add_argument(
        "--data_base", default="",
        help=(
            "Diretorio base dos dados SisMOM no servidor. "
            "Ex: /dados/sismom/SisMOM/sismom_forecast  "
            "O caminho completo sera: <data_base>/<run>/regional/eta/2D. "
            "Tambem configuravel via env SISMOM_DATA_BASE."
        )
    )
    parser.add_argument(
        "--data_dir", default="",
        help="Caminho direto para os arquivos .bin (substitui --data_base)"
    )
    parser.add_argument(
        "--output_dir", default=config.OUTPUT_DIR,
        help=f"Diretório de saída dos campos (padrão: {config.OUTPUT_DIR})"
    )
    parser.add_argument(
        "--accum_dir", default=config.ACCUM_DIR,
        help=f"Diretório de saída dos acumulados 24h (padrão: {config.ACCUM_DIR})"
    )
    parser.add_argument(
        "--vars", nargs="+", default=None,
        help="Variáveis a processar (padrão: todas). Ex: --vars TP2M PREC MAGV"
    )
    parser.add_argument(
        "--sequential", action="store_true",
        help="Ativa leitura com marcadores Fortran (OPTIONS SEQUENTIAL)"
    )
    parser.add_argument(
        "--only_accum", action="store_true",
        help="Gera somente os acumulados de 24h (PREC, PRCV, PRGE)"
    )
    parser.add_argument(
        "--only_fields", action="store_true",
        help="Gera somente os campos horários (sem acumulados 24h)"
    )
    parser.add_argument(
        "--workers", type=int, default=os.cpu_count() or 4,
        help=f"Processos paralelos (padrao: {os.cpu_count() or 4} = todos os CPUs)"
    )
    parser.add_argument(
        "--skip_existing", action="store_true",
        help="Pula figuras/COGs ja gerados (util para retomada)"
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suprime saida de progresso"
    )
    # ── COG GeoTIFF ──────────────────────────────────────────────────────────
    parser.add_argument(
        "--cog", action="store_true",
        help="Exportar campos como Cloud Optimized GeoTIFF (requer rasterio)"
    )
    parser.add_argument(
        "--cog_dir", default=config.COG_DIR,
        help=f"Diretorio de saida dos COGs (padrao: {config.COG_DIR})"
    )
    parser.add_argument(
        "--cog_overviews", action="store_true",
        help="Embutir overviews (piramides) nos COGs — pode causar multiplas "
             "camadas em alguns visualizadores (ex: SisMOM). Padrao: desativado."
    )
    parser.add_argument(
        "--cog_only", action="store_true",
        help="Exportar SOMENTE COGs, sem gerar figuras PNG"
    )
    return parser.parse_args()


def _setup_logging(log_dir: str, run_tag: str) -> str:
    """Configura logging para arquivo e stdout simultaneamente."""
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(
        log_dir, f"run_{run_tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return log_file


def main():
    args    = parse_args()
    verbose = not args.quiet

    # ── Resolver caminho dos dados ────────────────────────────────────────────
    # Prioridade: --data_dir > --data_base > SISMOM_DATA_BASE env > local data/
    if args.data_dir:
        data_dir = args.data_dir
    else:
        data_dir = config.build_data_dir(config.RUN_TAG, base=args.data_base)

    # ── COG: estrutura cog/{run}/ (flat, sem subpasta por variavel) ───────────
    cog_run_dir = os.path.join(args.cog_dir, config.RUN_TAG)

    log_file = _setup_logging(config.LOG_DIR, config.RUN_TAG)

    generate_png = not args.cog_only
    generate_cog = args.cog or args.cog_only

    if verbose:
        print("=" * 60)
        print("  Geracao de figuras -- Modelo Eta / BESM")
        print(f"  Run    : {config.RUN_TAG}")
        print(f"  T0     : {config.T0.strftime('%d/%m/%Y %HZ')}")
        print(f"  Passos : {config.NTIMES}  ({config.DT_HOURS}h)")
        print(f"  Dados  : {os.path.abspath(data_dir)}")
        print(f"  CPUs   : {os.cpu_count()}  |  workers={args.workers}")
        if args.skip_existing:
            print(f"  Modo   : skip_existing (retomada)")
        if generate_png:
            print(f"  Campos : {os.path.abspath(args.output_dir)}")
            print(f"  Acum.  : {os.path.abspath(args.accum_dir)}")
        if generate_cog:
            print(f"  COG    : {os.path.abspath(cog_run_dir)}")
        print(f"  Log    : {log_file}")
        print("=" * 60)

    if args.vars:
        invalid = [v for v in args.vars if v not in config.VAR_NAMES]
        if invalid:
            print(f"[main] ERRO: variaveis invalidas: {invalid}")
            print(f"[main] Disponiveis: {config.VAR_NAMES}")
            sys.exit(1)

    # ── Figuras PNG ───────────────────────────────────────────────────────────
    if generate_png:
        _load_plot_modules()
        if not args.only_accum:
            generate_all_fields(
                data_dir       = data_dir,
                output_dir     = args.output_dir,
                vars_to_plot   = args.vars,
                sequential     = args.sequential,
                workers        = args.workers,
                verbose        = verbose,
                skip_existing  = args.skip_existing,
            )

        if not args.only_fields:
            generate_24h_accumulations(
                data_dir   = data_dir,
                output_dir = args.accum_dir,
                sequential = args.sequential,
                verbose    = verbose,
            )

    # ── COG GeoTIFF ───────────────────────────────────────────────────────────
    if generate_cog:
        if not export_cog.HAS_RASTERIO:
            print("[main] ERRO: rasterio nao instalado. Execute:")
            print("       pip install rasterio")
            sys.exit(1)

        ovr = getattr(args, "cog_overviews", False)

        if not args.only_accum:
            if verbose:
                print("\n[main] Exportando COG GeoTIFF -- campos por timestep...")
            export_cog.export_all_fields_as_cog(
                data_dir       = data_dir,
                cog_base_dir   = cog_run_dir,
                vars_to_export = args.vars,
                sequential     = args.sequential,
                workers        = args.workers,
                verbose        = verbose,
                overviews      = ovr,
                skip_existing  = args.skip_existing,
            )

        if not args.only_fields:
            if verbose:
                print("\n[main] Exportando COG GeoTIFF -- acumulados 24h...")
            accumulate.export_all_accumulations_as_cog(
                data_dir      = data_dir,
                cog_dir       = cog_run_dir,
                sequential    = args.sequential,
                overviews     = ovr,
                skip_existing = args.skip_existing,
                verbose       = verbose,
            )


if __name__ == "__main__":
    main()
