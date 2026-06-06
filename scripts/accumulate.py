"""
accumulate.py -- Acumulados de precipitacao para PREC, PRCV e PRGE

Logica de acumulo:
------------------
O modelo tem saida HORARIA. A precipitacao NAO e definida na analise (hora 0),
portanto o acumulo NUNCA inclui o timestep 0.

Frequencia de acumulo configuravel via parametro accum_hours (padrao: 24).

Para accum_hours = 24 (convencao meteorologica):
  Duas janelas sao geradas em paralelo:
    ACUM00Z: acumula de 00Z a 00Z (validade em horario 00Z)
    ACUM12Z: acumula de 12Z a 12Z (validade em horario 12Z)

  Para run iniciando em 00Z (ex: 2026060400):
    ACUM00Z: soma FH 1-24  -> val. 2026060500 (00Z dia seguinte)
             soma FH 25-48 -> val. 2026060600
             ...
    ACUM12Z: soma FH 13-36 -> val. 2026060512
             soma FH 37-60 -> val. 2026060612
             ...
    Janela FH 109-132 seria o 5o ciclo, mas so ha FH ate 120
    -> janela incompleta -> DESCARTADA

  Para run iniciando em 12Z (ex: 2026060412):
    ACUM12Z: soma FH 1-24  -> val. 2026060512
    ACUM00Z: soma FH 13-36 -> val. 2026060600
             ...

Para outros periodos (ex: accum_hours = 6, 12, 48, 72):
  Janelas sequenciais comecando no FH dt_hours (primeiro FH disponivel):
    FH 1-6  -> val. YYYYMMDDHH   (accum_hours=6)
    FH 7-12 -> val. YYYYMMDDHH
    ...

Nomenclatura dos arquivos:
  PREC_ACUM24h_2026060500.tif   -- acumulo de 24h, validade 2026-06-05 00Z
  PREC_ACUM12h_2026060512.tif   -- acumulo de 12h, validade 2026-06-05 12Z
  PREC_ACUM6h_2026060506.tif    -- acumulo de  6h, validade 2026-06-05 06Z
"""

import os
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import config
import reader


# ──────────────────────────────────────────────────────────────────────────────
# JANELAS DE ACUMULO
# ──────────────────────────────────────────────────────────────────────────────

def get_accumulation_windows(
    t0: datetime = None,
    ntimes: int = None,
    dt_hours: int = None,
    accum_hours: int = 24,
) -> List[Dict]:
    """
    Determina todas as janelas de acumulo validas para o run.

    Para accum_hours=24: gera janelas ACUM00Z e ACUM12Z (convencao sinótica).
    Para outros periodos: gera janelas sequenciais comecando no FH dt_hours.

    Janelas incompletas (menos de accum_hours/dt_hours arquivos disponiveis)
    sao automaticamente descartadas.

    Parameters
    ----------
    t0          : inicio do run (padrao: config.T0)
    ntimes      : numero de timesteps disponiveis (padrao: config.NTIMES)
    dt_hours    : intervalo de saida do modelo em horas (padrao: config.DT_HOURS)
    accum_hours : periodo de acumulo em horas (padrao: 24)
                  Deve ser multiplo de dt_hours.
                  Exemplos: 6, 12, 24, 48, 72

    Returns
    -------
    Lista de dicts ordenada por (validade, tipo):
      {
        'type'       : str   -- 'ACUM00Z' | 'ACUM12Z' | 'ACUM{N}h'
        'start_fh'   : int   -- primeiro FH incluido (em horas)
        'end_fh'     : int   -- ultimo FH incluido (em horas)
        'validity'   : datetime
        'n_steps'    : int   -- numero de arquivos somados
        'accum_hours': int   -- periodo do acumulo em horas
      }
    """
    t0       = t0       if t0       is not None else config.T0
    ntimes   = ntimes   if ntimes   is not None else config.NTIMES
    dt_hours = dt_hours if dt_hours is not None else config.DT_HOURS

    if accum_hours % dt_hours != 0:
        raise ValueError(
            f"accum_hours={accum_hours} nao e multiplo de dt_hours={dt_hours}. "
            f"Escolha um valor multiplo de {dt_hours}h."
        )

    max_fh  = (ntimes - 1) * dt_hours   # ultimo FH disponivel
    n_steps = accum_hours // dt_hours    # arquivos somados por janela

    # ── Periodo de 24h: janelas ACUM00Z e ACUM12Z ─────────────────────────────
    if accum_hours == 24:
        run_hour = t0.hour
        if run_hour == 0:
            cycle_starts = [('ACUM00Z', dt_hours),
                            ('ACUM12Z', 12 + dt_hours)]
        elif run_hour == 12:
            cycle_starts = [('ACUM12Z', dt_hours),
                            ('ACUM00Z', 12 + dt_hours)]
        else:
            # Horario nao-padrao: usa 00Z e 12Z como referencia
            cycle_starts = [('ACUM00Z', dt_hours),
                            ('ACUM12Z', 12 + dt_hours)]

        windows = []
        for accum_type, start_fh in cycle_starts:
            fh = start_fh
            while fh + (n_steps - 1) * dt_hours <= max_fh:
                end_fh   = fh + (n_steps - 1) * dt_hours
                validity = t0 + timedelta(hours=end_fh)
                windows.append({
                    'type'       : accum_type,
                    'start_fh'   : fh,
                    'end_fh'     : end_fh,
                    'validity'   : validity,
                    'n_steps'    : n_steps,
                    'accum_hours': accum_hours,
                })
                fh += 24   # avanca 24h para o proximo ciclo 00Z ou 12Z

        windows.sort(key=lambda w: (w['validity'], w['type']))

    # ── Outros periodos: janelas sequenciais a partir do FH dt_hours ──────────
    else:
        label   = f"ACUM{accum_hours}h"
        windows = []
        fh      = dt_hours   # começa no primeiro FH disponivel (analise sem precip)

        while fh + (n_steps - 1) * dt_hours <= max_fh:
            end_fh   = fh + (n_steps - 1) * dt_hours
            validity = t0 + timedelta(hours=end_fh)
            windows.append({
                'type'       : label,
                'start_fh'   : fh,
                'end_fh'     : end_fh,
                'validity'   : validity,
                'n_steps'    : n_steps,
                'accum_hours': accum_hours,
            })
            fh += accum_hours   # avanca pelo periodo do acumulo

    return windows


# ──────────────────────────────────────────────────────────────────────────────
# CALCULO DO ACUMULADO
# ──────────────────────────────────────────────────────────────────────────────

def compute_accumulation(
    data_dir: str,
    var_name: str,
    window: Dict,
    sequential: bool = False,
) -> Optional[np.ndarray]:
    """
    Soma os campos de precipitacao de todos os FH dentro de uma janela.

    Parameters
    ----------
    data_dir   : diretorio com os arquivos .bin
    var_name   : nome da variavel (PREC, PRCV ou PRGE)
    window     : dict retornado por get_accumulation_windows()
    sequential : True se .bin usa marcadores Fortran

    Returns
    -------
    np.ndarray (NY, NX) em metros (unidade original), ou None se qualquer
    arquivo estiver ausente (janela incompleta -> descartada).
    """
    dt  = config.DT_HOURS
    acc = None

    for step in range(window['n_steps']):
        fh = window['start_fh'] + step * dt
        t  = config.T0 + timedelta(hours=fh)
        try:
            field = reader.read_field(data_dir, t, var_name, sequential=sequential)
        except FileNotFoundError:
            return None

        if acc is None:
            acc = np.zeros_like(field, dtype=np.float32)
        with np.errstate(invalid="ignore"):
            acc = np.where(np.isnan(field) | np.isnan(acc), np.nan, acc + field)

    return acc


# ──────────────────────────────────────────────────────────────────────────────
# NOMENCLATURA
# ──────────────────────────────────────────────────────────────────────────────

def accum_filename(
    var_name: str,
    validity: datetime,
    accum_hours: int = 24,
    ext: str = "tif",
) -> str:
    """
    Gera o nome do arquivo de acumulado.

    Exemplos:
      PREC_ACUM24h_2026060500.tif
      PREC_ACUM12h_2026060512.tif
      PREC_ACUM6h_2026060506.tif
    """
    return f"{var_name}_ACUM{accum_hours}h_{validity.strftime('%Y%m%d%H')}.{ext}"


# ──────────────────────────────────────────────────────────────────────────────
# EXPORTACAO COG
# ──────────────────────────────────────────────────────────────────────────────

def export_all_accumulations_as_cog(
    data_dir: str,
    cog_dir: str,
    accum_hours: int = 24,
    sequential: bool = False,
    overviews: bool = False,
    skip_existing: bool = False,
    verbose: bool = True,
) -> Dict[str, List[str]]:
    """
    Calcula e exporta todos os acumulados de PREC, PRCV e PRGE como COG GeoTIFF.

    Parameters
    ----------
    accum_hours : periodo do acumulo em horas (padrao: 24)
                  Para 24h: gera ACUM00Z e ACUM12Z.
                  Para outros valores: janelas sequenciais.
    """
    import export_cog as ecog

    os.makedirs(cog_dir, exist_ok=True)
    windows = get_accumulation_windows(accum_hours=accum_hours)
    saved   = {v: [] for v in config.PRECIP_VARS}

    if verbose:
        print(f"[accum] Periodo: {accum_hours}h | "
              f"{len(windows)} janelas x {len(config.PRECIP_VARS)} variaveis"
              f" = {len(windows) * len(config.PRECIP_VARS)} acumulados")
        for w in windows:
            print(f"  {w['type']:10s}  FH {w['start_fh']:3d}-{w['end_fh']:3d}"
                  f"  val. {w['validity'].strftime('%Y%m%d %HZ')}")

    for var in config.PRECIP_VARS:
        for win in windows:
            fname = accum_filename(var, win['validity'], accum_hours=accum_hours)
            fpath = os.path.join(cog_dir, fname)

            if skip_existing and os.path.exists(fpath):
                if verbose:
                    print(f"  SKIP  {fname}")
                saved[var].append(fpath)
                continue

            arr = compute_accumulation(data_dir, var, win, sequential)
            if arr is None:
                if verbose:
                    print(f"  [AVISO] {var} {win['type']} FH{win['start_fh']}-"
                          f"{win['end_fh']}: arquivo ausente -> descartado")
                continue

            try:
                # _prepare_array: m->mm, flipud, NaN->NODATA (nao multiplicar antes)
                ecog.write_cog(
                    ecog._prepare_array(arr, var),
                    fpath,
                    metadata={
                        "variable"   : var,
                        "description": config.VAR_DESC.get(var, var),
                        "units"      : "mm",
                        "accum_type" : win['type'],
                        "accum_hours": str(win['accum_hours']),
                        "start_fh"   : str(win['start_fh']),
                        "end_fh"     : str(win['end_fh']),
                        "validity"   : win['validity'].strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "model"      : f"Eta03/BESM run {config.RUN_TAG}",
                        "nodata"     : str(ecog.NODATA),
                    },
                    overviews=overviews,
                )
                saved[var].append(fpath)
                if verbose:
                    print(f"  OK  {fname}")
            except Exception as e:
                if verbose:
                    print(f"  [ERRO] {var} {win['type']}: {e}")

    return saved


# ──────────────────────────────────────────────────────────────────────────────
# EXPORTACAO PNG
# ──────────────────────────────────────────────────────────────────────────────

def plot_all_accumulations(
    data_dir: str,
    output_dir: str,
    accum_hours: int = 24,
    sequential: bool = False,
    verbose: bool = True,
) -> Dict[str, List[str]]:
    """
    Gera figuras PNG dos acumulados de precipitacao.

    Parameters
    ----------
    accum_hours : periodo do acumulo em horas (padrao: 24)
    """
    import plot_utils as pu

    os.makedirs(output_dir, exist_ok=True)
    windows = get_accumulation_windows(accum_hours=accum_hours)
    saved   = {v: [] for v in config.PRECIP_VARS}

    # Limites de colorbar por variavel e periodo (mm)
    vmax_table = {
        "PREC" : {6: 80,  12: 120, 24: 200, 48: 300, 72: 400},
        "PRCV" : {6: 60,  12: 80,  24: 150, 48: 200, 72: 300},
        "PRGE" : {6: 30,  12: 40,  24: 80,  48: 120, 72: 160},
    }

    for var in config.PRECIP_VARS:
        vmax = vmax_table.get(var, {}).get(accum_hours, accum_hours * 8)

        for win in windows:
            arr = compute_accumulation(data_dir, var, win, sequential)
            if arr is None:
                continue

            fname = accum_filename(var, win['validity'], accum_hours=accum_hours,
                                   ext=config.FIG_EXT)
            fpath = os.path.join(output_dir, fname)

            title_extra = (
                f"Acum. {accum_hours}h ({win['type']})  "
                f"[FH {win['start_fh']:03d}-{win['end_fh']:03d}  "
                f"val. {win['validity'].strftime('%d/%m %HZ')}]"
            )
            try:
                pu.plot_field(
                    arr, var, win['validity'], output_dir,
                    title_extra=title_extra,
                    convert_fn=pu.m_to_mm,
                    units_override="mm",
                    vmin_override=0,
                    vmax_override=vmax,
                )
                # plot_field salva com nome automatico; renomeia para padrao
                auto = os.path.join(
                    output_dir,
                    f"{var}_{win['validity'].strftime('%Y%m%d%H')}.{config.FIG_EXT}"
                )
                if os.path.exists(auto) and auto != fpath:
                    os.rename(auto, fpath)

                if os.path.exists(fpath):
                    saved[var].append(fpath)
                    if verbose:
                        print(f"  [PNG accum] {fname}")
            except Exception as e:
                if verbose:
                    print(f"  [ERRO PNG accum] {var} {win['type']}: {e}")

    return saved


# ── alias de compatibilidade ──────────────────────────────────────────────────
def plot_all_24h_accumulations(
    data_dir: str,
    output_dir: str,
    sequential: bool = False,
    verbose: bool = True,
) -> Dict[str, List[str]]:
    """Alias de compatibilidade -- chama plot_all_accumulations(accum_hours=24)."""
    return plot_all_accumulations(
        data_dir=data_dir, output_dir=output_dir,
        accum_hours=24, sequential=sequential, verbose=verbose,
    )


# ──────────────────────────────────────────────────────────────────────────────
# COMPATIBILIDADE -- funcao legada
# ──────────────────────────────────────────────────────────────────────────────

def compute_24h_accumulation(
    data_dir: str,
    var_name: str,
    t_end: datetime,
    sequential: bool = False,
) -> np.ndarray:
    """Legado: acumulado 24h terminando em t_end (4 x 6h). Mantido para compat."""
    windows_4x6 = [t_end - timedelta(hours=h) for h in (18, 12, 6, 0)]
    acc = None
    for t in windows_4x6:
        field = reader.read_field(data_dir, t, var_name, sequential=sequential)
        if acc is None:
            acc = np.zeros_like(field)
        with np.errstate(invalid="ignore"):
            acc = np.where(np.isnan(field) | np.isnan(acc), np.nan, acc + field)
    return acc
