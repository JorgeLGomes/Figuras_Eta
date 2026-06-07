"""
main.py -- Orquestrador principal de geracao de figuras do modelo Eta

Uso:
    python main.py                                      # usa config.yaml padrao
    python main.py --config meu_config.yaml             # config alternativa
    python main.py --vars-file minhas_vars.yaml         # variaveis alternativas
    python main.py --data_dir /caminho/para/bins
    python main.py --vars TP2M MAGV PREC --sequential
    python main.py --only_accum --accum_hours 6
    python main.py --cog --workers 8
    python main.py --cog_only

Estrutura de saida:
    figuras/campos/    -- PNG por variavel/timestep
    figuras/acumulados/ -- PNG acumulados
    cog/               -- COG GeoTIFF (quando --cog ativado)
"""

import os
import sys
import argparse
import time
import logging
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

# ── Pre-parse --config e --vars-file ANTES de inicializar config ──────────────
# config.py inicializa na importacao; para usar arquivos alternativos precisamos
# chamar init_config() com os caminhos corretos logo no inicio.
def _preparse_config_args():
    """
    Extrai --config, --vars-file e --run do argv sem processar os outros args.
    Necessario porque config.init_config() deve ser chamado antes de qualquer
    uso das constantes do modulo (reader, export_cog etc. las em importacao).
    """
    import argparse as _ap
    p = _ap.ArgumentParser(add_help=False)
    p.add_argument("--config",    default=None)
    p.add_argument("--vars-file", "--vars_file", dest="vars_file", default=None)
    p.add_argument("--run",       default=None)
    known, _ = p.parse_known_args()
    return known.config, known.vars_file, known.run

_cfg_file, _vars_file_pre, _run_pre = _preparse_config_args()

import config as config   # noqa: E402
config.init_config(_cfg_file, _vars_file_pre, run_tag=_run_pre)

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

def generate_accumulations(
    data_dir: str,
    output_dir: str,
    accum_hours: int = 24,
    sequential: bool = False,
    verbose: bool = True,
):
    """Gera figuras de acumulado de precipitacao para PREC, PRCV e PRGE."""
    if verbose:
        print(f"\n[main] Gerando acumulados {accum_hours}h para: {config.PRECIP_VARS}")
    saved = accumulate.plot_all_accumulations(
        data_dir, output_dir, accum_hours=accum_hours, sequential=sequential, verbose=verbose
    )
    total = sum(len(v) for v in saved.values())
    if verbose:
        print(f"[main] {total} figuras de acumulado {accum_hours}h geradas.")
    return saved


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Gera figuras do modelo Eta para todas as variaveis 2D.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # ── Rodada ────────────────────────────────────────────────────────────────
    parser.add_argument(
        "--run", default=None,
        help=(
            "Tag da rodada: YYYYMMDDHH ou HH (usa data do sistema para a data). "
            "Ex: --run 2026060600  ou  --run 00  (00Z de hoje)  ou  --run 12. "
            "Fallback: variavel de ambiente RUN_TAG."
        )
    )
    # ── Arquivos de configuracao ──────────────────────────────────────────────
    parser.add_argument(
        "--config", default=None,
        help=(
            "Arquivo de configuracao YAML do run "
            f"(padrao: {config._DEFAULT_CONFIG}). "
            "Ex: --config /rodadas/2026060412/config.yaml"
        )
    )
    parser.add_argument(
        "--vars-file", "--vars_file", dest="vars_file", default=None,
        help=(
            "Arquivo YAML com definicao das variaveis "
            f"(padrao: {config._DEFAULT_VARIABLES}). "
            "Permite trocar colormaps, limites e lista de variaveis sem editar o codigo."
        )
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
        help=(
            "Variaveis a processar. Padrao: todas com enabled=true em variables.yaml. "
            "Ex: --vars TP2M PREC MAGV"
        )
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
        help="Gera somente os campos horários (sem acumulados)"
    )
    parser.add_argument(
        "--accum_hours", type=int, default=24,
        help=(
            "Periodo de acumulo de precipitacao em horas (padrao: 24). "
            "Deve ser multiplo do intervalo de saida do modelo (DT_HOURS). "
            "Para 24h: gera ACUM00Z e ACUM12Z (convencao sinótica). "
            "Para outros valores (6, 12, 48, 72...): janelas sequenciais. "
            "Exemplos: --accum_hours 6  --accum_hours 48"
        )
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

    # ── Estrutura de saida: {base}/{run_tag}/{var}/  ──────────────────────────
    # Campos horarios: output_dir/RUN_TAG/VARNAME/
    # Acumulados:      accum_dir/RUN_TAG/VARNAME_ACUMNNh/
    # COG:             cog_dir/RUN_TAG/VARNAME/ (flat ja era assim)
    run_output_dir = os.path.join(args.output_dir, config.RUN_TAG)
    run_accum_dir  = os.path.join(args.accum_dir,  config.RUN_TAG)
    cog_run_dir    = os.path.join(args.cog_dir,    config.RUN_TAG)

    log_file = _setup_logging(config.LOG_DIR, config.RUN_TAG)

    generate_png = not args.cog_only
    generate_cog = args.cog or args.cog_only

    if verbose:
        print("=" * 60)
        print("  Geracao de figuras -- Modelo Eta / BESM")
        print(f"  Config : {config._CONFIG_FILE}")
        print(f"  Vars   : {config._VARS_FILE}")
        print(f"  Run    : {config.RUN_TAG}")
        print(f"  T0     : {config.T0.strftime('%d/%m/%Y %HZ')}")
        print(f"  Passos : {config.NTIMES}  ({config.DT_HOURS}h)")
        print(f"  Dados  : {os.path.abspath(data_dir)}")
        print(f"  CPUs   : {os.cpu_count()}  |  workers={args.workers}")
        if args.skip_existing:
            print(f"  Modo   : skip_existing (retomada)")
        print(f"  Acum.  : {args.accum_hours}h"
              + (" (ACUM00Z + ACUM12Z)" if args.accum_hours == 24 else " (sequencial)"))
        if generate_png:
            print(f"  Campos : {os.path.abspath(run_output_dir)}")
            print(f"  Acum.  : {os.path.abspath(run_accum_dir)}")
        if generate_cog:
            print(f"  COG    : {os.path.abspath(cog_run_dir)}")
        print(f"  Log    : {log_file}")
        print("=" * 60)

    # Variaveis a processar: CLI > enabled no YAML > todas
    vars_to_use = args.vars or config.enabled_vars()
    invalid = [v for v in vars_to_use if v not in config.VAR_NAMES]
    if invalid:
        print(f"[main] ERRO: variaveis invalidas: {invalid}")
        print(f"[main] Disponiveis: {config.VAR_NAMES}")
        sys.exit(1)
    if verbose:
        print(f"[main] Variaveis: {len(vars_to_use)} — {vars_to_use}")

    # ── Figuras PNG ───────────────────────────────────────────────────────────
    if generate_png:
        _load_plot_modules()
        if not args.only_accum:
            generate_all_fields(
                data_dir       = data_dir,
                output_dir     = run_output_dir,
                vars_to_plot   = vars_to_use,
                sequential     = args.sequential,
                workers        = args.workers,
                verbose        = verbose,
                skip_existing  = args.skip_existing,
            )

        if not args.only_fields:
            generate_accumulations(
                data_dir    = data_dir,
                output_dir  = run_accum_dir,
                accum_hours = args.accum_hours,
                sequential  = args.sequential,
                verbose     = verbose,
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
                vars_to_export = vars_to_use,
                sequential     = args.sequential,
                workers        = args.workers,
                verbose        = verbose,
                overviews      = ovr,
                skip_existing  = args.skip_existing,
            )

        if not args.only_fields:
            if verbose:
                print(f"\n[main] Exportando COG GeoTIFF -- acumulados {args.accum_hours}h...")
            accumulate.export_all_accumulations_as_cog(
                data_dir      = data_dir,
                cog_dir       = cog_run_dir,
                accum_hours   = args.accum_hours,
                sequential    = args.sequential,
                overviews     = ovr,
                skip_existing = args.skip_existing,
                verbose       = verbose,
            )


if __name__ == "__main__":
    main()
