"""
plot_utils.py — Utilitarios comuns de plot para o modelo Eta
"""

import os
import threading
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.ticker as mticker
from datetime import datetime

# Tenta usar cartopy; se nao disponivel, usa matplotlib puro
try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    HAS_CARTOPY = True
except ImportError:
    HAS_CARTOPY = False
    print("[plot_utils] cartopy nao encontrado -- usando matplotlib puro.")

import config


# ------------------------------------------------------------------------------
# COLORMAPS POR VARIAVEL
# ------------------------------------------------------------------------------

def _precip_cmap():
    """Colormap branco->azul escuro para precipitacao."""
    colors = [
        (1.00, 1.00, 1.00),
        (0.75, 0.93, 1.00),
        (0.38, 0.75, 1.00),
        (0.00, 0.56, 0.94),
        (0.00, 0.39, 0.75),
        (0.00, 0.20, 0.60),
        (0.30, 0.00, 0.50),
    ]
    return mcolors.LinearSegmentedColormap.from_list("precip", colors)


_PRECIP_CMAP = _precip_cmap()
_CUSTOM_CMAPS = {"precip": _PRECIP_CMAP}


def _resolve_cmap(cmap_name):
    """Converte string de colormap para objeto matplotlib."""
    if isinstance(cmap_name, str):
        return _CUSTOM_CMAPS.get(cmap_name, cmap_name)
    return cmap_name


def get_cmap_config(var_name: str):
    """Retorna (cmap, vmin, vmax) para a variavel."""
    cfg = config.CMAP_CONFIG.get(var_name, {})
    if isinstance(cfg, dict):
        raw_cmap = cfg.get("cmap", "viridis")
        vmin     = cfg.get("vmin")
        vmax     = cfg.get("vmax")
    else:
        raw_cmap, vmin, vmax = cfg
    return _resolve_cmap(raw_cmap), vmin, vmax


# ------------------------------------------------------------------------------
# SETUP DO MAPA
# ------------------------------------------------------------------------------

def _setup_axes_cartopy(fig, rect=111):
    """Cria eixo com projecao PlateCarree (cartopy)."""
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
    ax.set_aspect("auto")
    ax.grid(True, linewidth=0.3, color="0.7", linestyle="--")
    return ax


def setup_axes(fig, rect=111):
    if HAS_CARTOPY:
        return _setup_axes_cartopy(fig, rect)
    return _setup_axes_plain(fig, rect)


# ------------------------------------------------------------------------------
# CACHE DE FIGURA POR PROCESSO
# Reutiliza fig entre campos do mesmo worker (evita overhead de criacao)
# ------------------------------------------------------------------------------

_proc_local = threading.local()


def _get_fig():
    """Retorna (ou cria) a figura reutilizavel do processo atual."""
    if not getattr(_proc_local, "fig", None):
        _proc_local.fig = plt.figure(figsize=(12, 8))
    return _proc_local.fig


# ------------------------------------------------------------------------------
# PLOT GENERICO DE CAMPO 2D
# ------------------------------------------------------------------------------

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

    Otimizacoes vs versao anterior:
    - imshow (grade regular): 5-10x mais rapido que pcolormesh
    - compress_level=1: PNG mais rapido de escrever
    - Figura reutilizada por processo: sem overhead de criacao/destruicao

    Returns
    -------
    Caminho do arquivo salvo.
    """
    os.makedirs(output_dir, exist_ok=True)

    with np.errstate(invalid="ignore"):
        arr = data.copy().astype(np.float64)
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

    valid = arr[~np.isnan(arr)]
    if vmin is None:
        vmin = float(np.percentile(valid, 2))  if valid.size else 0
    if vmax is None:
        vmax = float(np.percentile(valid, 98)) if valid.size else 1
    if vmin == vmax:
        vmax = vmin + 1

    if HAS_CARTOPY:
        # Cartopy: cria nova figura (axes cartopy nao sao reutilizaveis)
        fig = plt.figure(figsize=(12, 8))
        ax  = _setup_axes_cartopy(fig)
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
        # Matplotlib puro: reutiliza figura; imshow >> pcolormesh em grade regular
        fig = _get_fig()
        fig.clear()
        ax = _setup_axes_plain(fig)
        im = ax.imshow(
            arr,
            extent=[config.LONS[0], config.LONS[-1], config.LATS[0], config.LATS[-1]],
            origin="lower",
            aspect="auto",
            cmap=cmap, vmin=vmin, vmax=vmax,
            interpolation="nearest",
        )
        ax.set_xlabel("Longitude (graus)")
        ax.set_ylabel("Latitude (graus)")

    cb = fig.colorbar(im, ax=ax, orientation="vertical", pad=0.02, fraction=0.03)
    cb.set_label(units, fontsize=10)

    time_str = timestamp.strftime("%d/%m/%Y %HZ")
    extra    = f" -- {title_extra}" if title_extra else ""
    ax.set_title(f"{var_name} -- {desc}{extra}\n{time_str}", fontsize=11, pad=8)

    extra_tag = title_extra.replace(" ", "_").lower() if title_extra else ""
    extra_tag = f"_{extra_tag}" if extra_tag else ""
    fname = f"{var_name}_{timestamp.strftime('%Y%m%d%H')}{extra_tag}.{config.FIG_EXT}"
    fpath = os.path.join(output_dir, fname)

    # compress_level=1: compressao minima = PNG mais rapido de gravar em disco
    fig.savefig(fpath, dpi=config.DPI, bbox_inches="tight",
                pil_kwargs={"compress_level": 1})
    if HAS_CARTOPY:
        plt.close(fig)
    return fpath


# ------------------------------------------------------------------------------
# CONVERSOES
# ------------------------------------------------------------------------------

def m_to_mm(arr: np.ndarray) -> np.ndarray:
    """Converte metros para milimetros."""
    with np.errstate(over="ignore", invalid="ignore"):
        return arr * 1000.0


# ------------------------------------------------------------------------------
# PLOT DE ACUMULADOS
# ------------------------------------------------------------------------------

def plot_accumulation(
    var_name: str,
    data: np.ndarray,
    validity,
    accum_hours: int,
    accum_type: str,
    output_path: str,
    vmax=None,
) -> str:
    """
    Plota campo acumulado de precipitacao e salva em output_path.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    with np.errstate(invalid="ignore"):
        arr = data.copy().astype(np.float64)

    units = "mm"
    desc  = config.VAR_DESC.get(var_name, var_name)

    cmap, _, _ = get_cmap_config(var_name)
    vmin = 0.0

    if vmax is None:
        valid = arr[~np.isnan(arr)]
        vmax  = float(np.percentile(valid, 98)) if valid.size else 50.0
    if vmax <= vmin:
        vmax = vmin + 1.0

    if HAS_CARTOPY:
        fig = plt.figure(figsize=(12, 8))
        ax  = _setup_axes_cartopy(fig)
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
        fig = _get_fig()
        fig.clear()
        ax = _setup_axes_plain(fig)
        im = ax.imshow(
            arr,
            extent=[config.LONS[0], config.LONS[-1], config.LATS[0], config.LATS[-1]],
            origin="lower",
            aspect="auto",
            cmap=cmap, vmin=vmin, vmax=vmax,
            interpolation="nearest",
        )
        ax.set_xlabel("Longitude (graus)")
        ax.set_ylabel("Latitude (graus)")

    cb = fig.colorbar(im, ax=ax, orientation="vertical", pad=0.02, fraction=0.03)
    cb.set_label(units, fontsize=10)

    time_str = validity.strftime("%d/%m/%Y %HZ")
    ax.set_title(
        f"{var_name} -- {desc} (Acumulado {accum_hours}h -- {accum_type})\n{time_str}",
        fontsize=11, pad=8,
    )

    fig.savefig(output_path, dpi=config.DPI, bbox_inches="tight",
                pil_kwargs={"compress_level": 1})
    if HAS_CARTOPY:
        plt.close(fig)
    return output_path
