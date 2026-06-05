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
import plot_variables as pv
import accumulate
import export_cog


# ──────────────────────────────────────────────────────────────────────────────
# WORKER — uma variável, um timestep (usado no pool)
# ──────────────────────────────────────────────────────────────────────────────

def _worker(args):
    """Função auxiliar para execução paralela."""
    data_dir, var_name, timestamp, out_dir, sequential = args
    try:
        data  = reader.read_field(data_dir, timestamp, var_name, sequential=sequential)
        fpath = pv.plot_variable(var_name, data, timestamp, out_dir)
        return (var_name, timestamp, fpath, None)
    except Exception as e:
        return (var_name, timestamp, None, str(e))


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
):
    """
    Itera sobre todos os timesteps disponíveis e gera uma figura por
    (variável, timestep).

    Parameters
    ----------
    data_dir     : diretório com os arquivos .bin
    output_dir   : raiz das figuras de saída
    vars_to_plot : lista de variáveis a processar (None = todas)
    sequential   : True se .bin tem marcadores Fortran
    workers      : número de processos paralelos (1 = serial)
    verbose      : imprime progresso
    """
    vars_to_plot   = vars_to_plot or config.VAR_NAMES
    timestamps     = reader.list_available_timestamps(data_dir)

    if not timestamps:
        print(f"[main] AVISO: nenhum arquivo .bin encontrado em '{data_dir}'.")
        print(f"[main] Padrão esperado: {config.FILE_PREFIX}YYYYMMDDHH{config.FILE_SUFFIX}")
        return

    if verbose:
        print(
            f"[main] {len(timestamps)} timesteps × {len(vars_to_plot)} variáveis "
            f"= {len(timestamps) * len(vars_to_plot)} figuras a gerar."
        )

    # Monta lista de tarefas
    tasks = []
    for var in vars_to_plot:
        out_dir = os.path.join(output_dir, var)
        for t in timestamps:
            tasks.append((data_dir, var, t, out_dir, sequential))

    t0      = time.time()
    n_ok    = 0
    n_err   = 0

    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_worker, task): task for task in tasks}
            for fut in as_completed(futures):
                var_name, ts, fpath, err = fut.result()
                if err:
                    n_err += 1
                    if verbose:
                        print(f"  [ERRO] {var_name} {ts.strftime('%Y%m%d%H')}: {err}")
                else:
                    n_ok += 1
                    if verbose:
                        print(f"  OK  {fpath}")
    else:
        for task in tasks:
            var_name, ts, fpath, err = _worker(task)
            if err:
                n_err += 1
                if verbose:
                    print(f"  [ERRO] {var_name} {ts.strftime('%Y%m%d%H')}: {err}")
            else:
                n_ok += 1
                if verbose:
                    print(f"  OK  {fpath}")

    elapsed = time.time() - t0
    print(
        f"\n[main] Concluído: {n_ok} figuras geradas, {n_err} erros "
        f"em {elapsed:.1f}s."
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
        "--data_dir", default=config.DATA_DIR,
        help=f"Diretório dos arquivos .bin (padrão: {config.DATA_DIR})"
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
        "--workers", type=int, default=1,
        help="Numero de processos paralelos (padrao: 1)"
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

    log_file = _setup_logging(config.LOG_DIR, config.RUN_TAG)

    generate_png = not args.cog_only
    generate_cog = args.cog or args.cog_only

    if verbose:
        print("=" * 60)
        print("  Geracao de figuras -- Modelo Eta / BESM")
        print(f"  Run    : {config.RUN_TAG}")
        print(f"  T0     : {config.T0.strftime('%d/%m/%Y %HZ')}")
        print(f"  Passos : {config.NTIMES}  ({config.DT_HOURS}h)")
        print(f"  Dados  : {os.path.abspath(args.data_dir)}")
        if generate_png:
            print(f"  Campos : {os.path.abspath(args.output_dir)}")
            print(f"  Acum.  : {os.path.abspath(args.accum_dir)}")
        if generate_cog:
            print(f"  COG    : {os.path.abspath(args.cog_dir)}")
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
        if not args.only_accum:
            generate_all_fields(
                data_dir     = args.data_dir,
                output_dir   = args.output_dir,
                vars_to_plot = args.vars,
                sequential   = args.sequential,
                workers      = args.workers,
                verbose      = verbose,
            )

        if not args.only_fields:
            generate_24h_accumulations(
                data_dir   = args.data_dir,
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

        if not args.only_accum:
            if verbose:
                print("\n[main] Exportando COG GeoTIFF -- campos por timestep...")
            export_cog.export_all_fields_as_cog(
                data_dir      = args.data_dir,
                cog_base_dir  = args.cog_dir,
                vars_to_export= args.vars,
                sequential    = args.sequential,
                workers       = args.workers,
                verbose       = verbose,
            )

        if not args.only_fields:
            if verbose:
                print("\n[main] Exportando COG GeoTIFF -- acumulados 24h...")
            export_cog.export_all_24h_accumulations_as_cog(
                data_dir     = args.data_dir,
                cog_base_dir = args.cog_dir,
                sequential   = args.sequential,
                verbose      = verbose,
            )


if __name__ == "__main__":
    main()
