"""
reader.py — Leitura de arquivos binários GrADS com TEMPLATE
Suporta: big-endian / little-endian, stream (direto) ou sequential (Fortran)
"""

import os
import numpy as np
from datetime import datetime

import config


def _build_filename(data_dir: str, timestamp: datetime) -> str:
    """
    Monta o nome do arquivo a partir do timestamp.
    CTL template: Eta03_BESM_2026060400+%y4%m2%d2%h2_2D.bin
    """
    tag = timestamp.strftime("%Y%m%d%H")
    fname = f"{config.FILE_PREFIX}{tag}{config.FILE_SUFFIX}"
    return os.path.join(data_dir, fname)


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
    fpath = _build_filename(data_dir, timestamp)
    if not os.path.exists(fpath):
        raise FileNotFoundError(f"Arquivo não encontrado: {fpath}")

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
    fpath = _build_filename(data_dir, timestamp)
    if not os.path.exists(fpath):
        raise FileNotFoundError(f"Arquivo não encontrado: {fpath}")

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
        arr[np.abs(arr - config.UNDEF) < 1e14] = np.nan
        result[name] = arr

    return result


def file_exists(data_dir: str, timestamp: datetime) -> bool:
    """Verifica se o arquivo correspondente ao timestamp existe."""
    return os.path.exists(_build_filename(data_dir, timestamp))


def list_available_timestamps(data_dir: str) -> list:
    """Retorna lista de timestamps para os quais existem arquivos .bin."""
    return [t for t in config.TIMESTAMPS if file_exists(data_dir, t)]
