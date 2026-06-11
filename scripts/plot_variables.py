"""
plot_variables.py — Uma função de plot por variável do modelo Eta (46 variáveis)

Cada função:
  plot_<VAR>(data, timestamp, output_dir, **kwargs) -> str

  - data       : np.ndarray (NY, NX) já lido pelo reader.py
  - timestamp  : datetime do campo
  - output_dir : diretório de saída das figuras
  - retorna    : caminho da figura salva

Uso típico:
    from reader import read_field
    from plot_variables import plot_TP2M
    from config import TIMESTAMPS

    arr   = read_field(data_dir, TIMESTAMPS[6], "TP2M")
    fpath = plot_TP2M(arr, TIMESTAMPS[6], "figuras/TP2M")
"""

import numpy as np
from datetime import datetime

import plot_utils as pu


# ──────────────────────────────────────────────────────────────────────────────
# PRESSÃO / GEOPOTENCIAL
# ──────────────────────────────────────────────────────────────────────────────

def plot_PSLM(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Pressão ao Nível do Mar — Mesinger (hPa)."""
    return pu.plot_field(data, "PSLM", timestamp, output_dir, **kw)


def plot_PSLC(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Pressão de Superfície (hPa)."""
    return pu.plot_field(data, "PSLC", timestamp, output_dir, **kw)


# ──────────────────────────────────────────────────────────────────────────────
# TEMPERATURA
# ──────────────────────────────────────────────────────────────────────────────

def plot_TP2M(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Temperatura a 2 m (K)."""
    return pu.plot_field(data, "TP2M", timestamp, output_dir, **kw)


def plot_MXTP(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Temperatura Máxima (K)."""
    return pu.plot_field(data, "MXTP", timestamp, output_dir, **kw)


def plot_MNTP(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Temperatura Mínima (K)."""
    return pu.plot_field(data, "MNTP", timestamp, output_dir, **kw)


def plot_DP2M(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Temperatura de Orvalho a 2 m (K)."""
    return pu.plot_field(data, "DP2M", timestamp, output_dir, **kw)


# ──────────────────────────────────────────────────────────────────────────────
# UMIDADE
# ──────────────────────────────────────────────────────────────────────────────

def plot_US2M(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Umidade Específica a 2 m (%)."""
    return pu.plot_field(data, "US2M", timestamp, output_dir, **kw)


def plot_UR2M(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Umidade Relativa a 2 m (kg/kg)."""
    return pu.plot_field(data, "UR2M", timestamp, output_dir, **kw)


# ──────────────────────────────────────────────────────────────────────────────
# VENTO
# ──────────────────────────────────────────────────────────────────────────────

def plot_U10M(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Componente Zonal do Vento a 10 m (m/s)."""
    return pu.plot_field(data, "U10M", timestamp, output_dir, **kw)


def plot_V10M(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Componente Meridional do Vento a 10 m (m/s)."""
    return pu.plot_field(data, "V10M", timestamp, output_dir, **kw)


def plot_MAGV(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Magnitude do Vento a 10 m (m/s)."""
    return pu.plot_field(data, "MAGV", timestamp, output_dir, **kw)


def plot_U100(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Componente Zonal do Vento a 100 m (m/s)."""
    return pu.plot_field(data, "U100", timestamp, output_dir, **kw)


def plot_V100(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Componente Meridional do Vento a 100 m (m/s)."""
    return pu.plot_field(data, "V100", timestamp, output_dir, **kw)


# ──────────────────────────────────────────────────────────────────────────────
# PRECIPITAÇÃO
# ──────────────────────────────────────────────────────────────────────────────

def plot_PREC(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Precipitação Total Acumulada em 6h (mm). Converte m → mm."""
    kw.setdefault("convert_fn", pu.m_to_mm)
    kw.setdefault("units_override", "mm")
    return pu.plot_field(data, "PREC", timestamp, output_dir, **kw)


def plot_PRCV(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Precipitação Convectiva Acumulada em 6h (mm). Converte m → mm."""
    kw.setdefault("convert_fn", pu.m_to_mm)
    kw.setdefault("units_override", "mm")
    return pu.plot_field(data, "PRCV", timestamp, output_dir, **kw)


def plot_PRGE(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Precipitação Estratiforme Acumulada em 6h (mm). Converte m → mm."""
    kw.setdefault("convert_fn", pu.m_to_mm)
    kw.setdefault("units_override", "mm")
    return pu.plot_field(data, "PRGE", timestamp, output_dir, **kw)


def plot_NEVE(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Neve Acumulada em 6h (mm). Converte m → mm."""
    kw.setdefault("convert_fn", pu.m_to_mm)
    kw.setdefault("units_override", "mm")
    return pu.plot_field(data, "NEVE", timestamp, output_dir, **kw)


# ──────────────────────────────────────────────────────────────────────────────
# FLUXOS DE SUPERFÍCIE
# ──────────────────────────────────────────────────────────────────────────────

def plot_CLSF(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Fluxo de Calor Latente de Superfície — média temporal (W/m²)."""
    return pu.plot_field(data, "CLSF", timestamp, output_dir, **kw)


def plot_CSSF(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Fluxo de Calor Sensível de Superfície — média temporal (W/m²)."""
    return pu.plot_field(data, "CSSF", timestamp, output_dir, **kw)


def plot_GHFL(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Fluxo de Calor no Solo — média temporal (W/m²)."""
    return pu.plot_field(data, "GHFL", timestamp, output_dir, **kw)


# ──────────────────────────────────────────────────────────────────────────────
# TEMPERATURA / UMIDADE DO SOLO
# ──────────────────────────────────────────────────────────────────────────────

def plot_TSFC(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Temperatura de Superfície — skin (K)."""
    return pu.plot_field(data, "TSFC", timestamp, output_dir, **kw)


def plot_TSOIL(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Temperatura do Solo (K)."""
    return pu.plot_field(data, "TSOIL", timestamp, output_dir, **kw)


def plot_USOIL(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Umidade do Solo (0-1)."""
    return pu.plot_field(data, "USOIL", timestamp, output_dir, **kw)


def plot_SMAV(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Disponibilidade de Água no Solo (adimensional)."""
    return pu.plot_field(data, "SMAV", timestamp, output_dir, **kw)


# ──────────────────────────────────────────────────────────────────────────────
# ESCOAMENTO SUPERFICIAL
# ──────────────────────────────────────────────────────────────────────────────

def plot_RNOF(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Escoamento Superficial 6h."""
    return pu.plot_field(data, "RNOF", timestamp, output_dir, **kw)


def plot_RNSG(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Escoamento Subsuperficial 6h."""
    return pu.plot_field(data, "RNSG", timestamp, output_dir, **kw)


# ──────────────────────────────────────────────────────────────────────────────
# TENSÃO DE CISALHAMENTO
# ──────────────────────────────────────────────────────────────────────────────

def plot_USST(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Tensão de Cisalhamento U de Superfície (N/m²)."""
    return pu.plot_field(data, "USST", timestamp, output_dir, **kw)


def plot_VSST(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Tensão de Cisalhamento V de Superfície (N/m²)."""
    return pu.plot_field(data, "VSST", timestamp, output_dir, **kw)


# ──────────────────────────────────────────────────────────────────────────────
# NUVENS
# ──────────────────────────────────────────────────────────────────────────────

def plot_LWNV(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Fração de Nuvens Baixas (0-1)."""
    return pu.plot_field(data, "LWNV", timestamp, output_dir, **kw)


def plot_MDNV(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Fração de Nuvens Médias (0-1)."""
    return pu.plot_field(data, "MDNV", timestamp, output_dir, **kw)


def plot_HINV(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Fração de Nuvens Altas (0-1)."""
    return pu.plot_field(data, "HINV", timestamp, output_dir, **kw)


def plot_CLD(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Nebulosidade Total (0-1)."""
    return pu.plot_field(data, "CLD", timestamp, output_dir, **kw)


# ──────────────────────────────────────────────────────────────────────────────
# RADIAÇÃO
# ──────────────────────────────────────────────────────────────────────────────

def plot_OCIS(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Radiação SW Incidente de Superfície — média temporal (W/m²)."""
    return pu.plot_field(data, "OCIS", timestamp, output_dir, **kw)


def plot_OLIS(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Radiação LW Incidente de Superfície — média temporal (W/m²)."""
    return pu.plot_field(data, "OLIS", timestamp, output_dir, **kw)


def plot_OCES(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Radiação SW Sainte de Superfície — média temporal (W/m²)."""
    return pu.plot_field(data, "OCES", timestamp, output_dir, **kw)


def plot_OLES(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Radiação LW Sainte de Superfície — média temporal (W/m²)."""
    return pu.plot_field(data, "OLES", timestamp, output_dir, **kw)


def plot_ROCE(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Radiação SW Sainte no TOA — média temporal (W/m²)."""
    return pu.plot_field(data, "ROCE", timestamp, output_dir, **kw)


def plot_ROLE(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Radiação LW Sainte no TOA — média temporal (W/m²)."""
    return pu.plot_field(data, "ROLE", timestamp, output_dir, **kw)


def plot_ALBE(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Albedo de Superfície (adimensional)."""
    return pu.plot_field(data, "ALBE", timestamp, output_dir, **kw)


# ──────────────────────────────────────────────────────────────────────────────
# CAPE / ÁGUA PRECIPITÁVEL / TRANSPORTES
# ──────────────────────────────────────────────────────────────────────────────

def plot_CAPE(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """CAPE — Energia Potencial Convectiva Disponível (J/kg)."""
    return pu.plot_field(data, "CAPE", timestamp, output_dir, **kw)


def plot_AGPL(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Água Precipitável Integrada na Coluna (kg/m²)."""
    return pu.plot_field(data, "AGPL", timestamp, output_dir, **kw)


def plot_QUINT(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Transporte Zonal de Vapor Integrado na Coluna (Q×U, kg/m/s)."""
    return pu.plot_field(data, "QUINT", timestamp, output_dir, **kw)


def plot_QVINT(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Transporte Meridional de Vapor Integrado na Coluna (Q×V, kg/m/s)."""
    return pu.plot_field(data, "QVINT", timestamp, output_dir, **kw)


def plot_CWINT(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Água Líquida de Nuvem Integrada na Coluna (kg/m²)."""
    return pu.plot_field(data, "CWINT", timestamp, output_dir, **kw)


def plot_CIINT(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Gelo de Nuvem Integrado na Coluna (kg/m²)."""
    return pu.plot_field(data, "CIINT", timestamp, output_dir, **kw)


# ──────────────────────────────────────────────────────────────────────────────
# CAMADA LIMITE PLANETÁRIA
# ──────────────────────────────────────────────────────────────────────────────

def plot_HPBL(data: np.ndarray, timestamp: datetime, output_dir: str, **kw) -> str:
    """Altura da Camada Limite Planetária (m)."""
    return pu.plot_field(data, "HPBL", timestamp, output_dir, **kw)


# ──────────────────────────────────────────────────────────────────────────────
# DISPATCHER — mapeia nome da variável → função de plot
# ──────────────────────────────────────────────────────────────────────────────

PLOT_FUNCTIONS = {
    "PSLM" : plot_PSLM,
    "PSLC" : plot_PSLC,
    "TP2M" : plot_TP2M,
    "MXTP" : plot_MXTP,
    "MNTP" : plot_MNTP,
    "DP2M" : plot_DP2M,
    "US2M" : plot_US2M,
    "UR2M" : plot_UR2M,
    "U10M" : plot_U10M,
    "V10M" : plot_V10M,
    "MAGV" : plot_MAGV,
    "U100" : plot_U100,
    "V100" : plot_V100,
    "PREC" : plot_PREC,
    "PRCV" : plot_PRCV,
    "PRGE" : plot_PRGE,
    "NEVE" : plot_NEVE,
    "CLSF" : plot_CLSF,
    "CSSF" : plot_CSSF,
    "GHFL" : plot_GHFL,
    "TSFC" : plot_TSFC,
    "TSOIL": plot_TSOIL,
    "USOIL": plot_USOIL,
    "SMAV" : plot_SMAV,
    "RNOF" : plot_RNOF,
    "RNSG" : plot_RNSG,
    "USST" : plot_USST,
    "VSST" : plot_VSST,
    "LWNV" : plot_LWNV,
    "MDNV" : plot_MDNV,
    "HINV" : plot_HINV,
    "CLD"  : plot_CLD,
    "OCIS" : plot_OCIS,
    "OLIS" : plot_OLIS,
    "OCES" : plot_OCES,
    "OLES" : plot_OLES,
    "ROCE" : plot_ROCE,
    "ROLE" : plot_ROLE,
    "ALBE" : plot_ALBE,
    "CAPE" : plot_CAPE,
    "AGPL" : plot_AGPL,
    "QUINT": plot_QUINT,
    "QVINT": plot_QVINT,
    "CWINT": plot_CWINT,
    "CIINT": plot_CIINT,
    "HPBL" : plot_HPBL,
}


def _plot_generic(var_name, data, timestamp, output_dir, **kwargs):
    """Fallback generico para variaveis sem funcao de plot dedicada.

    Usa descricao/unidades/cmap/vmin/vmax de variables.yaml (via config).
      - 2D (NY, NX)       : 1 figura
      - 3D (nlev, NY, NX) : 1 figura por nivel de plot_levels
                            (ou todos os niveis, se plot_levels vazio)
    """
    import config
    if data.ndim == 2:
        return pu.plot_field(data, var_name, timestamp, output_dir, **kwargs)

    # 3D: plota os niveis solicitados
    all_lvls  = config.VAR_LEVELS.get(var_name, [])
    plot_lvls = config.VAR_PLOT_LEVELS.get(var_name, []) or all_lvls
    fpath = None
    for lev in plot_lvls:
        if lev not in all_lvls:
            continue
        k = all_lvls.index(lev)
        if k >= data.shape[0]:
            continue
        fpath = pu.plot_field(
            data[k], var_name, timestamp, output_dir,
            title_extra=f"{lev} hPa", **kwargs,
        )
    if fpath is None:
        raise ValueError(
            f"'{var_name}': nenhum nivel valido para plotar "
            f"(levels={all_lvls}, plot_levels={plot_lvls}, shape={data.shape})"
        )
    return fpath


def plot_variable(
    var_name: str,
    data: np.ndarray,
    timestamp: datetime,
    output_dir: str,
    **kwargs,
) -> str:
    """
    Dispatcher: chama a função de plot correta para a variável.
    Variaveis sem funcao dedicada usam o plot generico (2D ou 3D por nivel),
    com cmap/vmin/vmax/descricao vindos de variables.yaml.

    Exemplo:
        fpath = plot_variable("TP2M", arr, timestamp, "figuras/TP2M")
    """
    fn = PLOT_FUNCTIONS.get(var_name)
    if fn is None:
        return _plot_generic(var_name, data, timestamp, output_dir, **kwargs)
    return fn(data, timestamp, output_dir, **kwargs)
