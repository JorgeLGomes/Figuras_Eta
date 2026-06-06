"""
accumulate.py -- Acumulados de precipitacao de 24h para PREC, PRCV e PRGE

Logica de acumulo:
------------------
O modelo tem saida HORARIA. A precipitacao NAO e definida na analise (hora 0),
portanto o acumulo NUNCA inclui o timestep 0.

Duas janelas de acumulo sao geradas:

  ACUM00Z: acumula de 00Z a 00Z (validade em horario 00Z)
  ACUM12Z: acumula de 12Z a 12Z (validade em horario 12Z)

Para run iniciando em 00Z (ex: 2026060400):
  ACUM00Z: soma FH 1-24  -> validade 2026060500 (00Z dia seguinte)
           soma FH 25-48 -> validade 2026060600
           ...
  ACUM12Z: soma FH 13-36 -> validade 2026060512 (12Z dia seguinte)
           soma FH 37-60 -> validade 2026060612
           ...
           FH 109-132 seria o 5o ciclo, mas so ha FH ate 120
           -> janela incompleta -> DESCARTADO

Para run iniciando em 12Z (ex: 2026060412):
  ACUM12Z: soma FH 1-24  -> validade 2026060512 (12Z dia seguinte)
  ACUM00Z: soma FH 13-36 -> validade 2026060600 (00Z dois dias depois)
           ...
           FH 1-12 do ciclo ACUM00Z nao estao disponiveis
           -> primeiro ciclo ACUM00Z descartado

Nomenclatura dos arquivos:
  PREC_ACUM24h_2026060500.tif   -- validade 2026-06-05 00Z
  PREC_ACUM24h_2026060512.tif   -- validade 2026-06-05 12Z
"""

import os
import glob
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

import config
import reader


# ──────────────────────────────────────────────────────────────────────────────
# JANELAS DE ACUMULO
# ──────────────────────────────────────────────────────────────────────────────

def get_accumulation_windows(
    t0: datetime = None,
    ntimes: int = None,
    dt_hours: int = None,
) -> List[Dict]:
    """
    Determina todas as janelas de acumulo de 24h validas para o run.

    Regras:
      Run 00Z -> ACUM00Z comeca no FH dt_hours (1h)
              -> ACUM12Z comeca no FH 12+dt_hours (13h)
      Run 12Z -> ACUM12Z comeca no FH dt_hours (1h)
              -> ACUM00Z comeca no FH 12+dt_hours (13h)
      Janelas com menos de 24h disponiveis sao descartadas.

    Returns
    -------
    Lista de dicts ordenada por (validade, tipo):
      {
        'type'    : 'ACUM00Z' | 'ACUM12Z',
        'start_fh': int  -- primeiro FH de previsao incluido (em horas)
        'end_fh'  : int  -- ultimo FH incluido (em horas)
        'validity': datetime
        'n_steps' : int  -- numero de arquivos somados (= 24 / dt_hours)
      }
    """
    t0       = t0       if t0       is not None else config.T0
    ntimes   = ntimes   if ntimes   is not None else config.NTIMES
    dt_hours = dt_hours if dt_hours is not None else config.DT_HOURS

    run_hour = t0.hour
    max_fh   = (ntimes - 1) * dt_hours   # ultimo FH disponivel (em horas)
    n_steps  = 24 // dt_hours             # passos por janela de 24h

    # Define qual ciclo comeca no FH 1 e qual comeca no FH 13
    if run_hour == 0:
        cycle_starts = [('ACUM00Z', dt_hours),
                        ('ACUM12Z', 12 + dt_hours)]
    elif run_hour == 12:
        cycle_starts = [('ACUM12Z', dt_hours),
                        ('ACUM00Z', 12 + dt_hours)]
    else:
        # Horario nao-padrao: inferir pelos horarios de validade
        cycle_starts = [('ACUM00Z', dt_hours),
                        ('ACUM12Z', 12 + dt_hours)]

    windows = []
    for accum_type, start_fh in cycle_starts:
        fh = start_fh
        while fh + (n_steps - 1) * dt_hours <= max_fh:
            end_fh   = fh + (n_steps - 1) * dt_hours
            validity = t0 + timedelta(hours=end_fh)
            windows.append({
                'type'    : accum_type,
                'start_fh': fh,
                'end_fh'  : end_fh,
                'validity': validity,
                'n_steps' : n_steps,
            })
            fh += 24

    windows.sort(key=lambda w: (w['validity'], w['type']))
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
    Soma os campos de precipitacao dos FH dentro de uma janela de 24h.

    Returns
    -------
    np.ndarray (NY, NX) em metros (unidade original), ou None se algum
    arquivo estiver ausente (janela incompleta -> descartada).
    """
    t0  = config.T0
    dt  = config.DT_HOURS
    acc = None

    for step in range(window['n_steps']):
        fh = window['start_fh'] + step * dt
        t  = t0 + timedelta(hours=fh)
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

def accum_filename(var_name: str, validity: datetime, ext: str = "tif") -> str:
    """
    Gera o nome do arquivo de acumulado.
    Exemplo: PREC_ACUM24h_2026060500.tif
    """
    return f"{var_name}_ACUM24h_{validity.strftime('%Y%m%d%H')}.{ext}"


# ──────────────────────────────────────────────────────────────────────────────
# EXPORTACAO COG
# ──────────────────────────────────────────────────────────────────────────────

def export_all_accumulations_as_cog(
    data_dir: str,
    cog_dir: str,
    sequential: bool = False,
    overviews: bool = False,
    skip_existing: bool = False,
    verbose: bool = True,
) -> Dict[str, List[str]]:
    """
    Calcula e exporta todos os acumulados de 24h de PREC, PRCV e PRGE
    como COG GeoTIFF com a nomenclatura VARNAME_ACUM24h_YYYYMMDDHH.tif.
    """
    import export_cog as ecog

    os.makedirs(cog_dir, exist_ok=True)
    windows = get_accumulation_windows()
    saved   = {v: [] for v in config.PRECIP_VARS}

    if verbose:
        print(f"[accum] {len(windows)} janelas x {len(config.PRECIP_VARS)} variaveis"
              f" = {len(windows) * len(config.PRECIP_VARS)} acumulados")
        for w in windows:
            print(f"  {w['type']:8s}  FH {w['start_fh']:3d}-{w['end_fh']:3d}"
                  f"  val. {w['validity'].strftime('%Y%m%d %HZ')}")

    for var in config.PRECIP_VARS:
        for win in windows:
            fname = accum_filename(var, win['validity'])
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
                # Escreve diretamente no caminho correto
                ecog.write_cog(
                    ecog._prepare_array(arr * 1000.0, var),   # m -> mm, flip
                    fpath,
                    metadata={
                        "variable"   : var,
                        "description": config.VAR_DESC.get(var, var),
                        "units"      : "mm",
                        "accum_type" : win['type'],
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
# EXPORTACAO PNG (compatibilidade com main.py)
# ──────────────────────────────────────────────────────────────────────────────

def plot_all_24h_accumulations(
    data_dir: str,
    output_dir: str,
    sequential: bool = False,
    verbose: bool = True,
) -> Dict[str, List[str]]:
    """Gera figuras PNG dos acumulados de 24h."""
    import plot_utils as pu

    os.makedirs(output_dir, exist_ok=True)
    windows = get_accumulation_windows()
    saved   = {v: [] for v in config.PRECIP_VARS}

    for var in config.PRECIP_VARS:
        for win in windows:
            arr = compute_accumulation(data_dir, var, win, sequential)
            if arr is None:
                continue

            fname = accum_filename(var, win['validity'], ext=config.FIG_EXT)
            fpath = os.path.join(output_dir, fname)

            title_extra = (
                f"Acum. 24h {win['type']}  "
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
                    vmax_override={"PREC": 200, "PRCV": 150, "PRGE": 80}.get(var, 200),
                )
                # plot_field salva com nome diferente; renomeia para padrao
                auto = os.path.join(
                    output_dir,
                    f"{var}_{win['validity'].strftime('%Y%m%d%H')}_"
                    f"acum._24h_{win['type'].lower()}.{config.FIG_EXT}"
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


# ──────────────────────────────────────────────────────────────────────────────
# COMPATIBILIDADE -- funcoes legadas usadas por export_cog.py antigo
# ──────────────────────────────────────────────────────────────────────────────

def compute_24h_accumulation(
    data_dir: str,
    var_name: str,
    t_end: datetime,
    sequential: bool = False,
) -> np.ndarray:
    """
    Legado: calcula acumulado 24h terminando em t_end.
    Usado por export_cog.export_24h_accumulation_as_cog().
    Soma os 4 campos de 6h anteriores a t_end.
    """
    from datetime import timedelta
    windows_4x6 = [t_end - timedelta(hours=h) for h in (18, 12, 6, 0)]
    acc = None
    for t in windows_4x6:
        field = reader.read_field(data_dir, t, var_name, sequential=sequential)
        if acc is None:
            acc = np.zeros_like(field)
        with np.errstate(invalid="ignore"):
            acc = np.where(np.isnan(field) | np.isnan(acc), np.nan, acc + field)
    return acc
