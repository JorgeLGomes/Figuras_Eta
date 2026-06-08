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
    Tenta multiplos formatos de timestamp para localizar o arquivo .bin.
    Retorna o caminho completo se encontrado, ou None.
    """
    for fmt in _TIMESTAMP_FORMATS:
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

    dtype   = dtype or config.DTYPE
    nx, ny  = config.NX, config.NY
    nfloats = nx * ny
    nvars   = len(config.VARIABLES)

    if sequential:
        arrays = []
        with open(fpath, "rb") as f:
            for _ in range(nvars):
                rec_len = int(np.frombuffer(f.read(4), dtype=">u4")[0])
                raw     = f.read(rec_len)
                f.read(4)
                arr = np.frombuffer(raw, dtype=dtype).astype(np.float32).reshape((ny, nx))
                arrays.append(arr)
    else:
        raw_all = np.fromfile(fpath, dtype=dtype)
        expected = nvars * nfloats
        if raw_all.size < expected:
            raise ValueError(
                f"Arquivo {fpath} tem {raw_all.size} valores, esperado >= {expected}"
            )
        arrays = [
            raw_all[i * nfloats : (i + 1) * nfloats].reshape((ny, nx))
            for i in range(nvars)
        ]

    result = {}
    for i, v in enumerate(config.VARIABLES):
        name = v["name"] if isinstance(v, dict) else v[0]
        arr = arrays[i].copy()
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
