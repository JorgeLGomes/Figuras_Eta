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
import time
import tempfile
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
from concurrent.futures import ProcessPoolExecutor, as_completed

try:
    import rasterio
    import rasterio.shutil as rio_shutil
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

def write_cog(
    arr: np.ndarray,
    fpath: str,
    metadata: Optional[dict] = None,
    overviews: bool = False,
) -> str:
    """
    Escreve arr (NY, NX) float32 como GeoTIFF tiled georeferenciado.

    Parameters
    ----------
    arr       : array (NY, NX) float32, preparado por _prepare_array
    fpath     : caminho do arquivo .tif de saida
    metadata  : tags GDAL a gravar nos metadados
    overviews : se True, embute overviews (piramides) no arquivo via
                rasterio.shutil.copy.
                ATENCAO: alguns visualizadores (ex: SisMOM) exibem cada
                nivel de overview como uma camada separada. Use False
                (padrao) para compatibilidade maxima.
    """
    if not HAS_RASTERIO:
        raise ImportError("rasterio e necessario.")

    os.makedirs(os.path.dirname(os.path.abspath(fpath)), exist_ok=True)

    # Garante array nativo C-contiguous float32 (evita problemas de byte order)
    arr = np.ascontiguousarray(arr, dtype=np.float32)

    profile = {
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

    if not overviews:
        # GeoTIFF tiled simples — sem overviews embutidos
        # Compativel com todos os visualizadores, incluindo SisMOM
        with rasterio.open(fpath, "w", **profile) as dst:
            dst.write(arr, 1)
            if metadata:
                dst.update_tags(**metadata)
        return fpath

    # Com overviews: usa arquivo temporario + rasterio.shutil.copy
    # NOTA: nao usar rasterio.open+COPY_SRC_OVERVIEWS+dst.write() juntos
    #       — isso corrompe os valores dos pixels.
    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with rasterio.open(tmp_path, "w", **profile) as dst:
            dst.write(arr, 1)
            if metadata:
                dst.update_tags(**metadata)

        with rasterio.open(tmp_path, "r+") as dst:
            dst.build_overviews(OVERVIEW_LEVELS, Resampling.average)
            dst.update_tags(ns="rio_overview", resampling="average")

        rio_shutil.copy(
            tmp_path, fpath,
            copy_src_overviews=True,
            compress=COMPRESS,
            predictor=PREDICTOR,
            tiled=True,
            blockxsize=TILE_SIZE,
            blockysize=TILE_SIZE,
            driver="GTiff",
        )
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    return fpath


# ──────────────────────────────────────────────────────────────────────────────
# EXPORTACAO POR VARIAVEL / TIMESTEP
# ──────────────────────────────────────────────────────────────────────────────

def export_field_as_cog(
    data: np.ndarray,
    var_name: str,
    timestamp: datetime,
    cog_dir: str,
    title_extra: str = "",
    overviews: bool = False,
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

    return write_cog(arr, fpath, metadata=meta, overviews=overviews)


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
# Use accumulate.export_all_accumulations_as_cog() -- API atual
# Nomenclatura: PREC_ACUM24h_2026060500.tif  (validade no nome)
# ──────────────────────────────────────────────────────────────────────────────

def export_all_24h_accumulations_as_cog(
    data_dir: str,
    cog_base_dir: str,
    sequential: bool = False,
    verbose: bool = True,
    overviews: bool = False,
    skip_existing: bool = False,
) -> dict:
    """
    Wrapper de compatibilidade -- delega para accumulate.export_all_accumulations_as_cog().

    Nomenclatura atual: PREC_ACUM24h_2026060500.tif
    Janelas ACUM00Z e ACUM12Z calculadas a partir do horario do run (config.T0).
    """
    return accumulate.export_all_accumulations_as_cog(
        data_dir      = data_dir,
        cog_dir       = cog_base_dir,
        sequential    = sequential,
        overviews     = overviews,
        skip_existing = skip_existing,
        verbose       = verbose,
    )


# ──────────────────────────────────────────────────────────────────────────────
# EXPORTACAO COMPLETA (todas as variaveis, todos os timesteps)
# ──────────────────────────────────────────────────────────────────────────────

def _worker_cog_timestep(args):
    """
    Worker por TIMESTEP: le o arquivo .bin UMA vez e gera TODOS os COGs
    das variaveis solicitadas. Paralelismo correto = 1 task por arquivo.

    args: (data_dir, timestamp, vars_list, cog_dir, sequential, overviews, skip_existing)
    returns: list of (var, timestamp, fpath_or_None, error_or_None)
    """
    _data_dir, _t, _vars, _out_dir, _seq, _ovr, _skip = args
    results   = []
    ts_str    = _t.strftime('%Y%m%d%H')

    # Identifica quais variaveis precisam ser geradas
    # _out_dir pode ser dict {var: dir} ou str (retrocompatibilidade)
    def _var_dir(var):
        return _out_dir[var] if isinstance(_out_dir, dict) else _out_dir

    vars_needed = []
    for var in _vars:
        fpath = os.path.join(_var_dir(var), f"{var}_{ts_str}.tif")
        if _skip and os.path.exists(fpath):
            results.append((var, _t, fpath, None))
        else:
            vars_needed.append(var)

    if not vars_needed:
        return results

    # Leitura unica do arquivo para todas as variaveis
    try:
        fields = reader.read_all_fields(_data_dir, _t, sequential=_seq)
    except Exception as e:
        return results + [(v, _t, None, f"leitura: {e}") for v in vars_needed]

    # Gera COG de cada variavel a partir dos dados ja lidos
    for var in vars_needed:
        try:
            fpath = export_field_as_cog(fields[var], var, _t, _var_dir(var), overviews=_ovr)
            results.append((var, _t, fpath, None))
        except Exception as e:
            results.append((var, _t, None, str(e)))

    return results


def export_all_fields_as_cog(
    data_dir: str,
    cog_base_dir: str,
    vars_to_export: list = None,
    sequential: bool = False,
    workers: int = 1,
    verbose: bool = True,
    overviews: bool = False,
    skip_existing: bool = False,
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
    skip_existing : pula arquivos ja existentes

    Returns
    -------
    dict {var_name: [lista de caminhos]}
    """
    vars_to_export = vars_to_export or config.VAR_NAMES
    timestamps     = reader.list_available_timestamps(data_dir)

    if not timestamps:
        print(f"[export_cog] Nenhum arquivo encontrado em '{data_dir}'")
        return {}

    if verbose:
        print(
            f"[export_cog] {len(timestamps)} timesteps x {len(vars_to_export)} variaveis"
            f" = {len(timestamps) * len(vars_to_export)} COGs a gerar | workers={workers}"
        )

    # Estrutura por variavel: cog_base_dir/VARNAME/
    os.makedirs(cog_base_dir, exist_ok=True)
    var_dirs = {}
    for var in vars_to_export:
        d = os.path.join(cog_base_dir, var)
        os.makedirs(d, exist_ok=True)
        var_dirs[var] = d

    # 1 task por TIMESTEP (nao por variavel) — leitura unica do arquivo
    tasks = [
        (data_dir, t, vars_to_export, var_dirs, sequential, overviews, skip_existing)
        for t in timestamps
    ]

    saved   = {v: [] for v in vars_to_export}
    n_ok    = 0
    n_skip  = 0
    n_err   = 0
    done    = 0
    t0      = time.time()

    def _process(res_list):
        nonlocal n_ok, n_skip, n_err, done
        done += 1
        pct = done / len(tasks) * 100
        for var, ts, fpath, err in res_list:
            if err:
                n_err += 1
                if verbose:
                    print(f"  [ERRO] {var} {ts.strftime('%Y%m%d%H')}: {err}")
            else:
                saved[var].append(fpath)
                n_ok += 1
        if verbose:
            elapsed = time.time() - t0
            eta = (elapsed / done) * (len(tasks) - done) if done else 0
            print(
                f"  [{done:3d}/{len(tasks)}  {pct:5.1f}%]"
                f"  ok={n_ok}  err={n_err}"
                f"  {elapsed:.0f}s  ETA={eta:.0f}s",
                flush=True,
            )

    if workers > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futs = {pool.submit(_worker_cog_timestep, task): task for task in tasks}
            for fut in as_completed(futs):
                _process(fut.result())
    else:
        for task in tasks:
            _process(_worker_cog_timestep(task))

    elapsed = time.time() - t0
    speed   = n_ok / elapsed if elapsed > 0 else 0
    if verbose:
        print(
            f"\n[export_cog] {n_ok} COGs gerados, {n_err} erros"
            f" | {elapsed:.1f}s ({speed:.1f} COG/s)"
        )

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
