"""
reader.py — Leitura de arquivos binários GrADS com TEMPLATE
Suporta: big-endian / little-endian, stream (direto) ou sequential (Fortran)
"""

import os
import numpy as np
from datetime import datetime

import config


# Formatos de timestamp tentados na ordem (do mais completo ao mais curto).
# Alguns modelos omitem o mes no nome do arquivo (ex: %Y%d%H = YYYYDDHH).
_TIMESTAMP_FORMATS = [
    "%Y%m%d%H",   # 10 chars: YYYYMMDDHH  (padrao 2D)
    "%Y%d%H",     # 8 chars:  YYYYDDHH    (3D sem mes)
    "%Y%m%d",     # 8 chars:  YYYYMMDD    (sem hora)
]


def _build_filename(data_dir: str, timestamp: datetime, fmt: str = "%Y%m%d%H") -> str:
    """Monta o nome do arquivo com um formato de timestamp especifico."""
    tag = timestamp.strftime(fmt)
    fname = f"{config.FILE_PREFIX}{tag}{config.FILE_SUFFIX}"
    return os.path.join(data_dir, fname)


def _resolve_filename(data_dir: str, timestamp: datetime):
    """
    Localiza o arquivo .bin para um dado timestamp.

    Estrategia:
      1. Usa config.FILE_TIMESTAMP_FMT (definido por file_timestamp no config.yaml)
      2. Fallback: tenta todos os formatos em _TIMESTAMP_FORMATS
    Retorna o caminho completo se encontrado, ou None.
    """
    # Primário: formato declarado explicitamente no config.yaml
    primary_fmt = getattr(config, "FILE_TIMESTAMP_FMT", "%Y%m%d%H")

    # Campo fixo: file_timestamp vazio → arquivo sem parte de timestamp no nome
    if not primary_fmt:
        fpath = _build_filename(data_dir, timestamp, "")
        return fpath if os.path.exists(fpath) else None

    if primary_fmt:
        fpath = _build_filename(data_dir, timestamp, primary_fmt)
        if os.path.exists(fpath):
            return fpath

    # Fallback: tenta formatos alternativos (backward compat / auto-deteccao)
    for fmt in _TIMESTAMP_FORMATS:
        if fmt == primary_fmt:
            continue  # ja tentado acima
        fpath = _build_filename(data_dir, timestamp, fmt)
        if os.path.exists(fpath):
            return fpath
    return None


def read_field(
    data_dir: str,
    timestamp: datetime,
    var_name: str,
    sequential: bool = False,
    dtype: str = None,
) -> np.ndarray:
    """
    Lê um campo 2D de uma variável em um dado instante.

    Parameters
    ----------
    data_dir   : diretório onde estão os arquivos .bin
    timestamp  : datetime do passo de tempo desejado
    var_name   : nome da variável (ex: 'TP2M')
    sequential : True se o arquivo tem marcadores Fortran (4 bytes antes/depois de cada campo)
    dtype      : override do dtype (default: config.DTYPE)

    Returns
    -------
    np.ndarray shape (NY, NX) com undef substituído por np.nan
    """
    fpath = _resolve_filename(data_dir, timestamp)
    if fpath is None:
        tag = timestamp.strftime("%Y%m%d%H")
        raise FileNotFoundError(
            "Arquivo nao encontrado para " + tag + " em '" + data_dir + "' "
            "(prefixo=" + repr(config.FILE_PREFIX) + ", sufixo=" + repr(config.FILE_SUFFIX) + ")"
        )

    dtype   = dtype or config.DTYPE
    nx, ny  = config.NX, config.NY
    nfloats = nx * ny
    nbytes  = nfloats * 4          # float32 = 4 bytes
    var_idx = config.VAR_INDEX[var_name]

    with open(fpath, "rb") as f:
        if sequential:
            # Formato Fortran: [4B len][dados][4B len] por campo
            for i in range(var_idx + 1):
                rec_len_bytes = f.read(4)
                if not rec_len_bytes:
                    raise EOFError(f"Fim inesperado do arquivo em {fpath}")
                rec_len = int(np.frombuffer(rec_len_bytes, dtype=">u4")[0])
                data_bytes = f.read(rec_len)
                f.read(4)  # trailer
                if i == var_idx:
                    raw = data_bytes
        else:
            # Formato stream/direto: campos empilhados sem marcadores
            offset = var_idx * nbytes
            f.seek(offset)
            raw = f.read(nbytes)

    if len(raw) < nbytes:
        raise ValueError(
            f"Bytes insuficientes para '{var_name}' em {fpath}: "
            f"esperado {nbytes}, lido {len(raw)}"
        )

    arr = np.frombuffer(raw, dtype=dtype).astype(np.float32)
    arr = arr.reshape((ny, nx))

    # Substitui undef por NaN (suprime warning de inf/nan na subtracao)
    with np.errstate(invalid="ignore"):
        arr[np.abs(arr - config.UNDEF) < 1e14] = np.nan

    return arr


def read_all_fields(
    data_dir: str,
    timestamp: datetime,
    sequential: bool = False,
    dtype: str = None,
) -> dict:
    """
    Lê todos os campos de um arquivo de uma vez (mais eficiente que leituras individuais).

    Returns
    -------
    dict {var_name: np.ndarray (NY, NX)}
    """
    fpath = _resolve_filename(data_dir, timestamp)
    if fpath is None:
        tag = timestamp.strftime("%Y%m%d%H")
        raise FileNotFoundError(
            "Arquivo nao encontrado para " + tag + " em '" + data_dir + "' "
            "(prefixo=" + repr(config.FILE_PREFIX) + ", sufixo=" + repr(config.FILE_SUFFIX) + ")"
        )

    dtype    = dtype or config.DTYPE
    nx, ny   = config.NX, config.NY
    nfloats  = nx * ny
    # Total de campos binarios (sum de max(nlev,1) por variavel)
    n_fields = getattr(config, "NVARS_FIELDS", len(config.VARIABLES))

    if sequential:
        # Le todos os campos crus de uma vez
        all_raw = []
        with open(fpath, "rb") as f:
            for _ in range(n_fields):
                rec_len = int(np.frombuffer(f.read(4), dtype=">u4")[0])
                raw     = f.read(rec_len)
                f.read(4)
                all_raw.append(
                    np.frombuffer(raw, dtype=dtype).astype(np.float32).reshape((ny, nx))
                )
    else:
        raw_all = np.fromfile(fpath, dtype=dtype)
        expected = n_fields * nfloats
        if raw_all.size < expected:
            raise ValueError(
                "Arquivo " + fpath + " tem " + str(raw_all.size) +
                " valores, esperado >= " + str(expected)
            )
        all_raw = [
            raw_all[i * nfloats : (i + 1) * nfloats].reshape((ny, nx))
            for i in range(n_fields)
        ]

    result = {}
    for v in config.VARIABLES:
        name = v["name"] if isinstance(v, dict) else v[0]
        nlev = int(v.get("nlev", 0) or 0) if isinstance(v, dict) else 0
        idx  = config.VAR_INDEX[name]   # offset binario correto

        if nlev > 0:
            # 3D: empilha nlev campos -> (nlev, NY, NX)
            arrs = []
            for k in range(nlev):
                arr = all_raw[idx + k].copy()
                with np.errstate(invalid="ignore"):
                    arr[np.abs(arr - config.UNDEF) < 1e14] = np.nan
                arrs.append(arr)
            result[name] = np.stack(arrs, axis=0)
        else:
            # 2D: campo unico -> (NY, NX)
            arr = all_raw[idx].copy()
            with np.errstate(invalid="ignore"):
                arr[np.abs(arr - config.UNDEF) < 1e14] = np.nan
            result[name] = arr

    return result


def file_exists(data_dir: str, timestamp: datetime) -> bool:
    """Verifica se o arquivo correspondente ao timestamp existe (qualquer formato)."""
    return _resolve_filename(data_dir, timestamp) is not None


def list_available_timestamps(data_dir: str) -> list:
    """Retorna lista de timestamps para os quais existem arquivos .bin."""
    return [t for t in config.TIMESTAMPS if file_exists(data_dir, t)]


def read_fields_selective(
    data_dir: str,
    timestamp: datetime,
    var_level_map: dict,
    sequential: bool = False,
    dtype: str = None,
) -> dict:
    """
    Le apenas os campos especificos solicitados (minimo uso de memoria).

    Ao inves de ler todos os nlev niveis de cada variavel 3D, le apenas os
    niveis necessarios para gerar as figuras (plot_levels).

    Parameters
    ----------
    var_level_map : dict
        {var_name: None}           -> variavel 2D: le 1 campo
        {var_name: [k0, k1, ...]}  -> variavel 3D: le apenas esses indices de nivel

    Returns
    -------
    dict:
        {var_name: np.ndarray(NY, NX)}       para vars 2D
        {var_name: {k: np.ndarray(NY, NX)}}  para vars 3D (k = indice do nivel)
    """
    fpath = _resolve_filename(data_dir, timestamp)
    if fpath is None:
        tag = timestamp.strftime("%Y%m%d%H")
        raise FileNotFoundError(
            "Arquivo nao encontrado para " + tag + " em '" + data_dir + "' "
            "(prefixo=" + repr(config.FILE_PREFIX) + ", sufixo=" + repr(config.FILE_SUFFIX) + ")"
        )

    dtype   = dtype or config.DTYPE
    nx, ny  = config.NX, config.NY
    nfloats = nx * ny
    nbytes  = nfloats * 4

    _yrev = getattr(config, "YREV", False)
    def _clean(arr):
        arr = arr.astype(np.float32).reshape(ny, nx).copy()
        if _yrev: arr = arr[::-1, :]
        with np.errstate(invalid="ignore"):
            arr[np.abs(arr - config.UNDEF) < 1e14] = np.nan
        return arr

    result = {}

    if sequential:
        # Formato Fortran: percorre registros sequencialmente e descarta os desnecessarios.
        # Monta conjunto de field_indices necessarios.
        needed = {}
        for var, level_ks in var_level_map.items():
            base = config.VAR_INDEX[var]
            if level_ks is None:
                needed[base] = (var, None)
            else:
                for k in level_ks:
                    needed[base + k] = (var, k)

        n_fields = getattr(config, "NVARS_FIELDS", len(config.VARIABLES))
        tmp = {}
        with open(fpath, "rb") as f:
            for fi in range(n_fields):
                rec_len = int(np.frombuffer(f.read(4), dtype=">u4")[0])
                raw     = f.read(rec_len)
                f.read(4)
                if fi in needed:
                    var, lev_k = needed[fi]
                    arr = _clean(np.frombuffer(raw, dtype=dtype))
                    if lev_k is None:
                        tmp[var] = arr
                    else:
                        tmp.setdefault(var, {})[lev_k] = arr
        result = tmp
    else:
        # Formato stream: seek direto a cada campo necessario (sem carregar o arquivo inteiro).
        with open(fpath, "rb") as f:
            for var, level_ks in var_level_map.items():
                base = config.VAR_INDEX[var]
                if level_ks is None:
                    # 2D: 1 campo
                    f.seek(base * nbytes)
                    raw = f.read(nbytes)
                    result[var] = _clean(np.frombuffer(raw, dtype=dtype))
                else:
                    # 3D: apenas os niveis solicitados
                    lev_dict = {}
                    for k in level_ks:
                        f.seek((base + k) * nbytes)
                        raw = f.read(nbytes)
                        lev_dict[k] = _clean(np.frombuffer(raw, dtype=dtype))
                    result[var] = lev_dict

    return result
