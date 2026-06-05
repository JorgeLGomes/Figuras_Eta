"""
export_cog.py — Exportacao de campos do modelo Eta como Cloud Optimized GeoTIFF (COG)

Cada campo e exportado como um arquivo .tif georeferenciado em WGS84 (EPSG:4326),
com compressao DEFLATE, tiles 512x512 e overviews (piramides) para conformidade COG.

Dependencia: rasterio >= 1.3
    pip install rasterio

Estrutura de saida:
    cog/
    ├── TP2M/
    │   ├── TP2M_2026060400.tif
    │   ├── TP2M_2026060401.tif
    │   └── ...
    ├── PREC/
    │   ├── PREC_2026060406.tif
    │   └── acumulado_24h/
    │       └── PREC_2026060500_acum24h.tif
    └── ...

Valores:
    - Precipitacao (PREC, PRCV, PRGE, NEVE): convertidos de metros para mm
    - UNDEF do modelo substituido por NaN (nodata no GeoTIFF = -9999.0)
    - Arrays armazenados como float32
"""

import os
import tempfile
import numpy as np
from datetime import datetime, timedelta
from typing import Optional

try:
    import rasterio
    from rasterio.transform import from_origin
    from rasterio.crs import CRS
    from rasterio.enums import Resampling
    HAS_RASTERIO = True
except ImportError:
    HAS_RASTERIO = False
    print("[export_cog] AVISO: rasterio nao encontrado.")
    print("[export_cog]   Instale com: pip install rasterio")

import config
import reader
import accumulate

# ──────────────────────────────────────────────────────────────────────────────
# PARAMETROS COG
# ──────────────────────────────────────────────────────────────────────────────

NODATA        = -9999.0
TILE_SIZE     = 512
OVERVIEW_LEVELS = [2, 4, 8, 16, 32]
COMPRESS      = "DEFLATE"       # DEFLATE (lossless) ou LZW
ZLEVEL        = 6               # nivel de compressao (1-9)
PREDICTOR     = 2               # predictor horizontal para floats

# CRS: WGS84 geografico
CRS_WGS84 = CRS.from_epsg(4326)

# Transform rasterio: canto superior esquerdo, DLAT negativo (N->S)
# GrADS armazena de sul para norte; rasterio espera norte para sul.
# upper_left_lat = LAT0 + (NY - 1) * DLAT  (linha 0 = norte)
_UL_LAT = config.LAT0 + (config.NY - 1) * config.DLAT
_UL_LON = config.LON0

# from_origin(west, north, xsize, ysize) → transform com ysize positivo internamente
TRANSFORM = from_origin(_UL_LON, _UL_LAT, config.DLON, config.DLAT)

# Variaveis de precipitacao que precisam de conversao m -> mm
_PRECIP_VARS = {"PREC", "PRCV", "PRGE", "NEVE"}


# ──────────────────────────────────────────────────────────────────────────────
# PREPARACAO DO ARRAY
# ──────────────────────────────────────────────────────────────────────────────

def _prepare_array(data: np.ndarray, var_name: str) -> np.ndarray:
    """
    - Converte m->mm para precipitacao
    - Flipa verticalmente (GrADS: S->N; rasterio: N->S)
    - Substitui NaN por NODATA
    - Retorna float32
    """
    arr = data.astype(np.float32)

    if var_name in _PRECIP_VARS:
        arr = arr * 1000.0          # m -> mm

    arr = np.flipud(arr)            # S->N para N->S

    arr = np.where(np.isnan(arr), np.float32(NODATA), arr)
    return arr


# ──────────────────────────────────────────────────────────────────────────────
# ESCRITOR COG
# ──────────────────────────────────────────────────────────────────────────────

def _write_cog(arr: np.ndarray, fpath: str, metadata: Optional[dict] = None) -> str:
    """
    Escreve um array (NY, NX) float32 como COG GeoTIFF.

    Estrategia:
      1. Escreve GeoTIFF temporario com tiles e compressao
      2. Adiciona overviews (piramides)
      3. Copia para arquivo final com COPY_SRC_OVERVIEWS=YES (formato COG)

    Parameters
    ----------
    arr      : array (NY, NX) ja preparado (_prepare_array)
    fpath    : caminho de saida do .tif
    metadata : dict de tags GDAL a incluir nos metadados do arquivo

    Returns
    -------
    Caminho do arquivo COG criado.
    """
    if not HAS_RASTERIO:
        raise ImportError("rasterio e necessario para exportar COG GeoTIFF.")

    os.makedirs(os.path.dirname(os.path.abspath(fpath)), exist_ok=True)

    profile_tmp = {
        "driver"    : "GTiff",
        "dtype"     : "float32",
        "width"     : config.NX,
        "height"    : config.NY,
        "count"     : 1,
        "crs"       : CRS_WGS84,
        "transform" : TRANSFORM,
        "nodata"    : NODATA,
        "compress"  : COMPRESS,
        "zlevel"    : ZLEVEL,
        "predictor" : PREDICTOR,
        "tiled"     : True,
        "blockxsize": TILE_SIZE,
        "blockysize": TILE_SIZE,
        "BIGTIFF"   : "IF_SAFER",
    }

    # Escrita em arquivo temporario
    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with rasterio.open(tmp_path, "w", **profile_tmp) as dst:
            dst.write(arr[np.newaxis, :, :], 1)   # banda 1
            if metadata:
                dst.update_tags(**metadata)

        # Adicionar overviews ao arquivo temporario
        with rasterio.open(tmp_path, "r+") as dst:
            dst.build_overviews(OVERVIEW_LEVELS, Resampling.average)
            dst.update_tags(ns="rio_overview", resampling="average")

        # Copiar para COG final com overviews embutidos
        profile_cog = profile_tmp.copy()
        profile_cog.update({
            "COPY_SRC_OVERVIEWS": "YES",
        })

        with rasterio.open(tmp_path, "r") as src:
            with rasterio.open(fpath, "w", **profile_cog) as dst:
                dst.write(src.read(1), 1)
                # Copiar overviews
                for i, ovr_level in enumerate(src.overviews(1)):
                    ovr_data = src.read(1, out_shape=(
                        1,
                        src.height // ovr_level,
                        src.width  // ovr_level,
                    ), resampling=Resampling.average)
                    dst.write(ovr_data, 1)
                if metadata:
                    dst.update_tags(**metadata)

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return fpath


def _write_cog_simple(arr: np.ndarray, fpath: str, metadata: Optional[dict] = None) -> str:
    """
    Versao simplificada: usa o driver COG nativo do GDAL (rasterio >= 1.4 / GDAL >= 3.1).
    Mais rapido e confiavel quando disponivel.
    """
    if not HAS_RASTERIO:
        raise ImportError("rasterio e necessario para exportar COG GeoTIFF.")

    os.makedirs(os.path.dirname(os.path.abspath(fpath)), exist_ok=True)

    profile = {
        "driver"          : "COG",
        "dtype"           : "float32",
        "width"           : config.NX,
        "height"          : config.NY,
        "count"           : 1,
        "crs"             : CRS_WGS84,
        "transform"       : TRANSFORM,
        "nodata"          : NODATA,
        "compress"        : COMPRESS,
        "overview_resampling": "AVERAGE",
        "BIGTIFF"         : "IF_SAFER",
    }

    with rasterio.open(fpath, "w", **profile) as dst:
        dst.write(arr[np.newaxis, :, :], 1)
        if metadata:
            dst.update_tags(**metadata)

    return fpath


def write_cog(arr: np.ndarray, fpath: str, metadata: Optional[dict] = None) -> str:
    """
    Escolhe automaticamente entre o driver COG nativo e a abordagem manual com overviews.
    """
    if not HAS_RASTERIO:
        raise ImportError("rasterio e necessario.")

    # Tenta driver COG nativo (GDAL >= 3.1)
    if "COG" in rasterio.drivers.raster_driver_extensions().values() or \
       "COG" in [d.upper() for d in rasterio.drivers.raster_driver_extensions()]:
        try:
            return _write_cog_simple(arr, fpath, metadata)
        except Exception:
            pass

    # Fallback: GeoTIFF com overviews manuais
    return _write_cog(arr, fpath, metadata)


# ──────────────────────────────────────────────────────────────────────────────
# EXPORTACAO POR VARIAVEL / TIMESTEP
# ──────────────────────────────────────────────────────────────────────────────

def export_field_as_cog(
    data: np.ndarray,
    var_name: str,
    timestamp: datetime,
    cog_dir: str,
    title_extra: str = "",
) -> str:
    """
    Exporta um campo 2D como COG GeoTIFF.

    Parameters
    ----------
    data       : array (NY, NX) lido pelo reader
    var_name   : nome da variavel
    timestamp  : datetime do campo
    cog_dir    : diretorio de saida
    title_extra: sufixo no nome do arquivo (ex: "acum24h")

    Returns
    -------
    Caminho do arquivo .tif criado.
    """
    arr = _prepare_array(data, var_name)

    units = config.VAR_UNITS.get(var_name, "")
    if var_name in _PRECIP_VARS:
        units = "mm"

    meta = {
        "variable"   : var_name,
        "description": config.VAR_DESC.get(var_name, var_name),
        "units"      : units,
        "timestamp"  : timestamp.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model"      : f"Eta03/BESM run {config.RUN_TAG}",
        "nodata"     : str(NODATA),
        "crs"        : "EPSG:4326",
    }
    if title_extra:
        meta["title_extra"] = title_extra

    extra_tag = f"_{title_extra.replace(' ', '_').lower()}" if title_extra else ""
    fname = f"{var_name}_{timestamp.strftime('%Y%m%d%H')}{extra_tag}.tif"
    fpath = os.path.join(cog_dir, fname)

    return write_cog(arr, fpath, metadata=meta)


def export_var_all_timesteps(
    data_dir: str,
    var_name: str,
    cog_dir: str,
    sequential: bool = False,
    verbose: bool = True,
) -> list:
    """
    Exporta todos os timesteps disponiveis de uma variavel como COG GeoTIFF.

    Returns
    -------
    Lista de caminhos criados.
    """
    timestamps = reader.list_available_timestamps(data_dir)
    os.makedirs(cog_dir, exist_ok=True)
    saved = []

    for t in timestamps:
        try:
            data  = reader.read_field(data_dir, t, var_name, sequential=sequential)
            fpath = export_field_as_cog(data, var_name, t, cog_dir)
            saved.append(fpath)
            if verbose:
                print(f"  [COG] {var_name} {t.strftime('%Y%m%d%H')} -> {fpath}")
        except Exception as e:
            if verbose:
                print(f"  [COG] ERRO {var_name} {t.strftime('%Y%m%d%H')}: {e}")

    return saved


# ──────────────────────────────────────────────────────────────────────────────
# EXPORTACAO DE ACUMULADOS 24H
# ──────────────────────────────────────────────────────────────────────────────

def export_24h_accumulation_as_cog(
    data_dir: str,
    var_name: str,
    t_end: datetime,
    cog_dir: str,
    sequential: bool = False,
) -> str:
    """
    Calcula o acumulado 24h e exporta como COG GeoTIFF.

    Returns
    -------
    Caminho do arquivo .tif criado.
    """
    arr_m = accumulate.compute_24h_accumulation(data_dir, var_name, t_end, sequential)
    t_start = t_end - timedelta(hours=24)
    title_extra = f"acum24h_{t_start.strftime('%Y%m%d%H')}_{t_end.strftime('%Y%m%d%H')}"

    return export_field_as_cog(arr_m, var_name, t_end, cog_dir, title_extra=title_extra)


def export_all_24h_accumulations_as_cog(
    data_dir: str,
    cog_base_dir: str,
    sequential: bool = False,
    verbose: bool = True,
) -> dict:
    """
    Exporta acumulados 24h de PREC, PRCV e PRGE como COG GeoTIFF
    para todos os periodos disponiveis no forecast.

    Returns
    -------
    dict {var_name: [lista de caminhos]}
    """
    saved = {}
    t_max = config.T0 + timedelta(hours=config.NTIMES - 1)

    for var in config.PRECIP_VARS:
        out_dir = os.path.join(cog_base_dir, var, "acumulado_24h")
        os.makedirs(out_dir, exist_ok=True)
        saved[var] = []

        t_end = config.T0 + timedelta(hours=24)
        while t_end <= t_max:
            try:
                fpath = export_24h_accumulation_as_cog(
                    data_dir, var, t_end, out_dir, sequential
                )
                saved[var].append(fpath)
                if verbose:
                    print(f"  [COG acum24h] {var} {t_end.strftime('%Y%m%d%H')} -> {fpath}")
            except FileNotFoundError as e:
                if verbose:
                    print(f"  [COG acum24h] AVISO arquivo ausente: {e}")
            except Exception as e:
                if verbose:
                    print(f"  [COG acum24h] ERRO {var} {t_end}: {e}")
            t_end += timedelta(hours=24)

    return saved


# ──────────────────────────────────────────────────────────────────────────────
# EXPORTACAO COMPLETA (todas as variaveis, todos os timesteps)
# ──────────────────────────────────────────────────────────────────────────────

def export_all_fields_as_cog(
    data_dir: str,
    cog_base_dir: str,
    vars_to_export: list = None,
    sequential: bool = False,
    workers: int = 1,
    verbose: bool = True,
) -> dict:
    """
    Exporta todos os campos de todas as variaveis como COG GeoTIFF.

    Parameters
    ----------
    data_dir      : diretorio com os .bin
    cog_base_dir  : diretorio raiz de saida dos COGs
    vars_to_export: lista de variaveis (None = todas)
    sequential    : True se arquivos .bin usam marcadores Fortran
    workers       : processos paralelos (1 = serial)
    verbose       : exibir progresso

    Returns
    -------
    dict {var_name: [lista de caminhos]}
    """
    from concurrent.futures import ProcessPoolExecutor, as_completed

    vars_to_export = vars_to_export or config.VAR_NAMES
    timestamps     = reader.list_available_timestamps(data_dir)

    if not timestamps:
        print(f"[export_cog] Nenhum arquivo encontrado em '{data_dir}'")
        return {}

    if verbose:
        print(
            f"[export_cog] {len(timestamps)} timesteps x {len(vars_to_export)} variaveis"
            f" = {len(timestamps) * len(vars_to_export)} COGs a gerar."
        )

    def _worker_cog(args):
        _data_dir, _var, _t, _out_dir, _seq = args
        try:
            data  = reader.read_field(_data_dir, _t, _var, sequential=_seq)
            fpath = export_field_as_cog(data, _var, _t, _out_dir)
            return (_var, _t, fpath, None)
        except Exception as e:
            return (_var, _t, None, str(e))

    tasks = []
    for var in vars_to_export:
        out_dir = os.path.join(cog_base_dir, var)
        for t in timestamps:
            tasks.append((data_dir, var, t, out_dir, sequential))

    saved  = {v: [] for v in vars_to_export}
    n_ok   = 0
    n_err  = 0

    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_worker_cog, task): task for task in tasks}
            for fut in as_completed(futures):
                var, t, fpath, err = fut.result()
                if err:
                    n_err += 1
                    if verbose:
                        print(f"  [ERRO] {var} {t.strftime('%Y%m%d%H')}: {err}")
                else:
                    n_ok += 1
                    saved[var].append(fpath)
                    if verbose:
                        print(f"  [COG] {fpath}")
    else:
        for task in tasks:
            var, t, fpath, err = _worker_cog(task)
            if err:
                n_err += 1
                if verbose:
                    print(f"  [ERRO] {var} {t.strftime('%Y%m%d%H')}: {err}")
            else:
                n_ok += 1
                saved[var].append(fpath)
                if verbose:
                    print(f"  [COG] {fpath}")

    if verbose:
        print(f"\n[export_cog] {n_ok} COGs gerados, {n_err} erros.")

    return saved


# ──────────────────────────────────────────────────────────────────────────────
# VALIDACAO (verifica se um .tif e realmente um COG valido)
# ──────────────────────────────────────────────────────────────────────────────

def validate_cog(fpath: str) -> bool:
    """
    Verificacao basica: abre o arquivo e confirma que tem overviews e tiles.
    Para validacao completa use: python -m cogdumper ou rio cogeo validate.
    """
    if not HAS_RASTERIO:
        return False
    try:
        with rasterio.open(fpath) as src:
            has_overviews = len(src.overviews(1)) > 0
            is_tiled      = src.profile.get("tiled", False)
            return has_overviews and is_tiled
    except Exception:
        return False
