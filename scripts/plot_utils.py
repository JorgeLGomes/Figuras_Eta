"""
plot_utils.py — Utilitários comuns de plot para o modelo Eta
"""

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.ticker as mticker
from datetime import datetime

# Tenta usar cartopy; se não disponível, usa matplotlib puro
try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    HAS_CARTOPY = True
except ImportError:
    HAS_CARTOPY = False
    print("[plot_utils] cartopy não encontrado — usando matplotlib puro.")

import config


# ──────────────────────────────────────────────────────────────────────────────
# COLORMAPS POR VARIÁVEL
# ──────────────────────────────────────────────────────────────────────────────

def _precip_cmap():
    """Colormap branco→azul escuro para precipitação."""
    colors = [
        (1.00, 1.00, 1.00),   # 0  branco
        (0.75, 0.93, 1.00),   # leve
        (0.38, 0.75, 1.00),
        (0.00, 0.56, 0.94),
        (0.00, 0.39, 0.75),
        (0.00, 0.20, 0.60),   # intenso
        (0.30, 0.00, 0.50),   # extremo
    ]
    return mcolors.LinearSegmentedColormap.from_list("precip", colors)


# Colormap especial "precip" referenciado no variables.yaml
_PRECIP_CMAP = _precip_cmap()

# Nomes reservados de colormaps proprios (mapeados de string para objeto)
_CUSTOM_CMAPS = {
    "precip": _PRECIP_CMAP,
}


def _resolve_cmap(cmap_name):
    """Converte string de colormap (incluindo nomes proprios) para objeto matplotlib."""
    if isinstance(cmap_name, str):
        return _CUSTOM_CMAPS.get(cmap_name, cmap_name)
    return cmap_name   # ja e um objeto colormap


def get_cmap_config(var_name: str):
    """
    Retorna (cmap, vmin, vmax) para a variavel a partir de config.CMAP_CONFIG
    (carregado de variables.yaml).

    O cmap retornado pode ser string ou objeto matplotlib colormap.
    """
    raw_cmap, vmin, vmax = config.CMAP_CONFIG.get(var_name, ("viridis", None, None))
    return _resolve_cmap(raw_cmap), vmin, vmax


# ──────────────────────────────────────────────────────────────────────────────
# SETUP DO MAPA
# ──────────────────────────────────────────────────────────────────────────────

def _setup_axes_cartopy(fig, rect=111):
    """Cria eixo com projeção PlateCarree (cartopy)."""
    proj = ccrs.PlateCarree()
    ax   = fig.add_subplot(rect, projection=proj)
    ax.add_feature(cfeature.COASTLINE.with_scale("50m"), linewidth=0.6, color="k")
    ax.add_feature(cfeature.BORDERS.with_scale("50m"),   linewidth=0.4, color="0.4")
    ax.add_feature(cfeature.STATES.with_scale("50m"),    linewidth=0.2, color="0.6")
    gl = ax.gridlines(draw_labels=True, linewidth=0.3, color="0.7",
                      alpha=0.7, linestyle="--")
    gl.top_labels   = False
    gl.right_labels = False
    gl.xlocator = mticker.MaxNLocator(5)
    gl.ylocator = mticker.MaxNLocator(5)
    return ax


def _setup_axes_plain(fig, rect=111):
    """Cria eixo simples sem cartopy."""
    ax = fig.add_subplot(rect)
    ax.set_aspect("equal")
    ax.grid(True, linewidth=0.3, color="0.7", linestyle="--")
    return ax


def setup_axes(fig, rect=111):
    if HAS_CARTOPY:
        return _setup_axes_cartopy(fig, rect)
    return _setup_axes_plain(fig, rect)


# ──────────────────────────────────────────────────────────────────────────────
# PLOT GENÉRICO DE CAMPO 2D
# ──────────────────────────────────────────────────────────────────────────────

def plot_field(
    data: np.ndarray,
    var_name: str,
    timestamp: datetime,
    output_dir: str,
    title_extra: str = "",
    units_override: str = None,
    vmin_override=None,
    vmax_override=None,
    cmap_override=None,
    convert_fn=None,
) -> str:
    """
    Plota um campo 2D e salva como imagem.

    Parameters
    ----------
    data          : array (NY, NX)
    var_name      : nome da variável (config.VAR_NAMES)
    timestamp     : datetime do campo
    output_dir    : diretório de saída
    title_extra   : texto adicional no título (ex: "Acumulado 24h")
    units_override: sobrescreve a unidade do config
    vmin/vmax_override: sobrescreve os limites do colormap
    cmap_override : sobrescreve o colormap
    convert_fn    : função de conversão aplicada aos dados (ex: m→mm)

    Returns
    -------
    Caminho do arquivo salvo.
    """
    os.makedirs(output_dir, exist_ok=True)

    arr   = data.copy().astype(np.float64)
    units = units_override or config.VAR_UNITS.get(var_name, "")
    desc  = config.VAR_DESC.get(var_name, var_name)

    if convert_fn is not None:
        arr = convert_fn(arr)

    cmap, vmin, vmax = get_cmap_config(var_name)
    if cmap_override is not None:
        cmap = cmap_override
    if vmin_override is not None:
        vmin = vmin_override
    if vmax_override is not None:
        vmax = vmax_override

    # Escala automática por percentis se vmin/vmax não definidos
    valid = arr[~np.isnan(arr)]
    if vmin is None:
        vmin = float(np.percentile(valid, 2))  if valid.size else 0
    if vmax is None:
        vmax = float(np.percentile(valid, 98)) if valid.size else 1
    if vmin == vmax:
        vmax = vmin + 1

    fig = plt.figure(figsize=(12, 8))
    ax  = setup_axes(fig)

    if HAS_CARTOPY:
        im = ax.pcolormesh(
            config.LONS, config.LATS, arr,
            cmap=cmap, vmin=vmin, vmax=vmax,
            transform=ccrs.PlateCarree(),
            shading="auto",
        )
        ax.set_extent(
            [config.LONS[0], config.LONS[-1], config.LATS[0], config.LATS[-1]],
            crs=ccrs.PlateCarree(),
        )
    else:
        im = ax.pcolormesh(
            config.LONS, config.LATS, arr,
            cmap=cmap, vmin=vmin, vmax=vmax,
            shading="auto",
        )
        ax.set_xlabel("Longitude (°)")
        ax.set_ylabel("Latitude (°)")

    cb = fig.colorbar(im, ax=ax, orientation="vertical", pad=0.02, fraction=0.03)
    cb.set_label(units, fontsize=10)

    time_str = timestamp.strftime("%d/%m/%Y %HZ")
    extra    = f" — {title_extra}" if title_extra else ""
    ax.set_title(f"{var_name} — {desc}{extra}\n{time_str}", fontsize=11, pad=8)

    # Nome do arquivo: VAR_YYYYMMDDHH[_extra].png
    extra_tag = title_extra.replace(" ", "_").lower() if title_extra else ""
    extra_tag = f"_{extra_tag}" if extra_tag else ""
    fname     = f"{var_name}_{timestamp.strftime('%Y%m%d%H')}{extra_tag}.{config.FIG_EXT}"
    fpath     = os.path.join(output_dir, fname)

    plt.savefig(fpath, dpi=config.DPI, bbox_inches="tight")
    plt.close(fig)
    return fpath


# ──────────────────────────────────────────────────────────────────────────────
# CONVERSÕES
# ──────────────────────────────────────────────────────────────────────────────

def m_to_mm(arr: np.ndarray) -> np.ndarray:
    """Converte metros → milímetros (para variáveis de precipitação)."""
    return arr * 1000.0
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               