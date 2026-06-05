"""
accumulate.py — Acumulado de 24h para PREC, PRCV e PRGE

As variáveis de precipitação no CTL representam acumulados de 6h cada.
Para obter o acumulado de 24h, somam-se os 4 campos correspondentes
ao período de 24h desejado.

Lógica de seleção dos timesteps para acumulado de 24h
------------------------------------------------------
O CTL tem TDEF 121 LINEAR 00Z04Jun2026 1hr.
Como PREC/PRCV/PRGE são "6h precip", o campo em um dado timestep T
representa a precipitação acumulada entre T-6h e T.
Portanto os timesteps relevantes são: T=6h, 12h, 18h, 24h, 30h, ...
(índices 0-based: 5, 11, 17, 23, ..., ou seja i % 6 == 5)

Para cada janela de 24h terminando em T_end (múltiplo de 24h após T0):
  soma = campo(T_end-18h) + campo(T_end-12h) + campo(T_end-6h) + campo(T_end)

Exemplo: acumulado 24h de 00Z04Jun a 00Z05Jun
  T_end = 00Z05Jun (índice 24)
  Soma dos índices 6, 12, 18, 24 (1-based) = índices 5, 11, 17, 23 (0-based)
"""

import os
import numpy as np
from datetime import datetime, timedelta
from typing import List, Optional

import config
import reader
import plot_utils as pu
import plot_variables as pv


# ──────────────────────────────────────────────────────────────────────────────
# NÚCLEO DO ACUMULADO
# ──────────────────────────────────────────────────────────────────────────────

def compute_24h_accumulation(
    data_dir: str,
    var_name: str,
    t_end: datetime,
    sequential: bool = False,
) -> np.ndarray:
    """
    Calcula o acumulado de 24h de uma variável de precipitação.

    Parameters
    ----------
    data_dir  : diretório com os arquivos .bin
    var_name  : "PREC", "PRCV" ou "PRGE"
    t_end     : datetime do final do período de 24h (deve ser múltiplo de 6h)
    sequential: passar True se os arquivos têm marcadores Fortran

    Returns
    -------
    np.ndarray (NY, NX) em metros (unidade original do CTL)
    NaN onde algum dos 4 campos é NaN ou indisponível.

    Raises
    ------
    ValueError  : se t_end não for múltiplo de 6h
    FileNotFoundError : se algum dos 4 arquivos não existir
    """
    if var_name not in config.PRECIP_VARS:
        raise ValueError(
            f"'{var_name}' não é variável de precipitação. "
            f"Use uma de: {config.PRECIP_VARS}"
        )

    # t_end deve ser múltiplo de 6h a partir de T0
    delta_h = int((t_end - config.T0).total_seconds() / 3600)
    if delta_h % 6 != 0:
        raise ValueError(
            f"t_end={t_end} não é múltiplo de 6h a partir de T0={config.T0}. "
            f"delta_h={delta_h}"
        )

    # Os 4 timesteps que compõem as 24h
    windows = [t_end - timedelta(hours=h) for h in (18, 12, 6, 0)]

    accumulation = None
    for t in windows:
        field = reader.read_field(data_dir, t, var_name, sequential=sequential)
        if accumulation is None:
            accumulation = np.zeros_like(field)
        # NaN propagante: onde qualquer campo é NaN, o acumulado é NaN
        with np.errstate(invalid="ignore"):
            accumulation = np.where(
                np.isnan(field) | np.isnan(accumulation),
                np.nan,
                accumulation + field,
            )

    return accumulation


def compute_all_24h_windows(
    data_dir: str,
    var_name: str,
    sequential: bool = False,
) -> List[tuple]:
    """
    Calcula os acumulados de 24h para TODOS os períodos disponíveis
    dentro da janela do forecast (NTIMES = 121h).

    Retorna lista de (t_end, np.ndarray) para cada janela completa de 24h.
    Período mínimo necessário: 24h (t_end >= T0 + 24h, i.e., t_end >= índice 24).
    Janelas disponíveis (t_end múltiplo de 24h): +24h, +48h, +72h, +96h, +120h
    """
    results = []
    # t_end máximo: T0 + (NTIMES-1) horas
    t_max = config.T0 + timedelta(hours=config.NTIMES - 1)

    t_end = config.T0 + timedelta(hours=24)
    while t_end <= t_max:
        try:
            arr = compute_24h_accumulation(data_dir, var_name, t_end, sequential)
            results.append((t_end, arr))
        except FileNotFoundError as e:
            print(f"[accumulate] Arquivo ausente para {t_end}: {e}")
        t_end += timedelta(hours=24)

    return results


# ──────────────────────────────────────────────────────────────────────────────
# PLOT DO ACUMULADO
# ──────────────────────────────────────────────────────────────────────────────

# Limites do colormap para acumulado 24h (valores maiores que o 6h)
_ACUM24_VMAX = {
    "PREC": 200,
    "PRCV": 150,
    "PRGE":  80,
}


def plot_24h_accumulation(
    data_dir: str,
    var_name: str,
    t_end: datetime,
    output_dir: str,
    sequential: bool = False,
) -> str:
    """
    Calcula e plota o acumulado de 24h para uma variável de precipitação.

    Parameters
    ----------
    data_dir   : diretório com os arquivos .bin
    var_name   : "PREC", "PRCV" ou "PRGE"
    t_end      : datetime do final do período (múltiplo de 6h)
    output_dir : diretório de saída das figuras
    sequential : True se arquivos têm marcadores Fortran

    Returns
    -------
    Caminho da figura salva.
    """
    arr_m = compute_24h_accumulation(data_dir, var_name, t_end, sequential)

    t_start  = t_end - timedelta(hours=24)
    title_ex = (
        f"Acum. 24h  "
        f"[{t_start.strftime('%d/%m %HZ')} → {t_end.strftime('%d/%m %HZ')}]"
    )

    # Gera a figura usando a função da variável com override de limites e conversão
    fpath = pu.plot_field(
        arr_m,
        var_name,
        t_end,
        output_dir,
        title_extra=title_ex,
        convert_fn=pu.m_to_mm,
        units_override="mm",
        vmin_override=0,
        vmax_override=_ACUM24_VMAX.get(var_name, 200),
    )
    return fpath


def plot_all_24h_accumulations(
    data_dir: str,
    output_base_dir: str,
    sequential: bool = False,
) -> dict:
    """
    Gera figuras de acumulado 24h para PREC, PRCV e PRGE
    em todos os períodos disponíveis no forecast.

    Parameters
    ----------
    data_dir       : diretório com os .bin
    output_base_dir: diretório raiz de saída (subpastas por variável serão criadas)
    sequential     : True se arquivos têm marcadores Fortran

    Returns
    -------
    dict {var_name: [lista de caminhos de figuras geradas]}
    """
    saved = {}
    for var in config.PRECIP_VARS:
        out_dir = os.path.join(output_base_dir, var, "acumulado_24h")
        os.makedirs(out_dir, exist_ok=True)
        saved[var] = []

        t_max  = config.T0 + timedelta(hours=config.NTIMES - 1)
        t_end  = config.T0 + timedelta(hours=24)

        while t_end <= t_max:
            try:
                fpath = plot_24h_accumulation(
                    data_dir, var, t_end, out_dir, sequential
                )
                saved[var].append(fpath)
                print(f"[acumulado 24h] {var} {t_end.strftime('%Y%m%d%H')} → {fpath}")
            except FileNotFoundError as e:
                print(f"[acumulado 24h] AVISO — arquivo ausente: {e}")
            except Exception as e:
                print(f"[acumulado 24h] ERRO em {var} {t_end}: {e}")
            t_end += timedelta(hours=24)

    return saved
