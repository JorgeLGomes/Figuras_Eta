#!/usr/bin/env python3
"""
ctl_to_yaml.py — Gera config.yaml e variables.yaml a partir de um descritor de dados

Formatos suportados:
  CTL (GrADS)  — extensoes .ctl
  NetCDF       — extensoes .nc, .nc4, .nc3, .netcdf, .cdf

Uso:
    python ctl_to_yaml.py <arquivo.ctl>
    python ctl_to_yaml.py <arquivo.nc>
    python ctl_to_yaml.py <arquivo> --format ctl|netcdf
    python ctl_to_yaml.py <arquivo> --config saida_config.yaml --vars saida_vars.yaml
    python ctl_to_yaml.py <arquivo> --stdout      # imprime no terminal, nao grava
    python ctl_to_yaml.py <arquivo> --dry-run     # mostra o que seria gerado
    python ctl_to_yaml.py <arquivo> --list-vars   # lista as variaveis encontradas e sai

Exemplos:
    python ctl_to_yaml.py Eta03_BESM_2026060600+000_2D.ctl
    python ctl_to_yaml.py saida_modelo.nc --next-to-ctl
    python ctl_to_yaml.py saida.nc --list-vars

Dependencias:
  CTL   : nenhuma (stdlib Python)
  NetCDF: netCDF4 (pip install netCDF4)  ou  scipy (pip install scipy)
"""

import re
import sys
import argparse
import pathlib
import textwrap
from datetime import timedelta


# ─────────────────────────────────────────────────────────────────────────────
# TABELA DE COLORMAPS / LIMITES POR VARIAVEL
# Adicione novas entradas aqui; a chave e o nome da variavel em maiusculas.
# ─────────────────────────────────────────────────────────────────────────────
_VAR_META = {
    # Pressao
    "PSLM":  dict(cmap="RdBu_r",  vmin=990,   vmax=1030,  precip=False),
    "PSLC":  dict(cmap="RdBu_r",  vmin=980,   vmax=1030,  precip=False),
    "PSFC":  dict(cmap="RdBu_r",  vmin=980,   vmax=1030,  precip=False),
    "MSLP":  dict(cmap="RdBu_r",  vmin=990,   vmax=1030,  precip=False),
    # Temperatura
    "TP2M":  dict(cmap="RdBu_r",  vmin=268,   vmax=308,   precip=False),
    "T2M":   dict(cmap="RdBu_r",  vmin=268,   vmax=308,   precip=False),
    "MXTP":  dict(cmap="hot_r",   vmin=270,   vmax=313,   precip=False),
    "MNTP":  dict(cmap="cool",    vmin=260,   vmax=305,   precip=False),
    "DP2M":  dict(cmap="BrBG",    vmin=260,   vmax=300,   precip=False),
    "TSFC":  dict(cmap="RdBu_r",  vmin=268,   vmax=320,   precip=False),
    "TSOIL": dict(cmap="RdBu_r",  vmin=270,   vmax=315,   precip=False),
    "TSKIN": dict(cmap="RdBu_r",  vmin=268,   vmax=320,   precip=False),
    "TSEA":  dict(cmap="RdBu_r",  vmin=271,   vmax=305,   precip=False),
    # Umidade / agua
    "US2M":  dict(cmap="YlGnBu",  vmin=0,     vmax=100,   precip=False),
    "UR2M":  dict(cmap="YlGnBu",  vmin=0,     vmax=1,     precip=False),
    "RH2M":  dict(cmap="YlGnBu",  vmin=0,     vmax=100,   precip=False),
    "USOIL": dict(cmap="YlGnBu",  vmin=0,     vmax=1,     precip=False),
    "SMAV":  dict(cmap="YlGnBu",  vmin=0,     vmax=1,     precip=False),
    "AGPL":  dict(cmap="YlGnBu",  vmin=0,     vmax=60,    precip=False),
    "PWAT":  dict(cmap="YlGnBu",  vmin=0,     vmax=60,    precip=False),
    "CWINT": dict(cmap="Blues",   vmin=0,     vmax=0.5,   precip=False),
    "CIINT": dict(cmap="Purples", vmin=0,     vmax=0.3,   precip=False),
    # Vento
    "U10M":  dict(cmap="bwr",     vmin=-20,   vmax=20,    precip=False),
    "V10M":  dict(cmap="bwr",     vmin=-20,   vmax=20,    precip=False),
    "MAGV":  dict(cmap="YlOrRd",  vmin=0,     vmax=20,    precip=False),
    "WNDSPD":dict(cmap="YlOrRd",  vmin=0,     vmax=20,    precip=False),
    "U100":  dict(cmap="bwr",     vmin=-25,   vmax=25,    precip=False),
    "V100":  dict(cmap="bwr",     vmin=-25,   vmax=25,    precip=False),
    "USST":  dict(cmap="bwr",     vmin=-0.5,  vmax=0.5,   precip=False),
    "VSST":  dict(cmap="bwr",     vmin=-0.5,  vmax=0.5,   precip=False),
    # Precipitacao
    "PREC":  dict(cmap="precip",  vmin=0,     vmax=50,    precip=True),
    "PRCV":  dict(cmap="precip",  vmin=0,     vmax=40,    precip=True),
    "PRGE":  dict(cmap="precip",  vmin=0,     vmax=20,    precip=True),
    "NEVE":  dict(cmap="Blues",   vmin=0,     vmax=20,    precip=True),
    "RAIN":  dict(cmap="precip",  vmin=0,     vmax=50,    precip=True),
    "SNOW":  dict(cmap="Blues",   vmin=0,     vmax=20,    precip=True),
    "RACC":  dict(cmap="precip",  vmin=0,     vmax=200,   precip=True),
    "ACPR":  dict(cmap="precip",  vmin=0,     vmax=200,   precip=True),
    # Fluxos de calor / energia
    "CLSF":  dict(cmap="RdBu",    vmin=-200,  vmax=600,   precip=False),
    "CSSF":  dict(cmap="RdBu",    vmin=-50,   vmax=300,   precip=False),
    "GHFL":  dict(cmap="coolwarm",vmin=-50,   vmax=50,    precip=False),
    "LHF":   dict(cmap="RdBu",    vmin=-50,   vmax=400,   precip=False),
    "SHF":   dict(cmap="RdBu",    vmin=-50,   vmax=300,   precip=False),
    # Radiacao
    "OCIS":  dict(cmap="YlOrRd",  vmin=0,     vmax=900,   precip=False),
    "OLIS":  dict(cmap="inferno", vmin=200,   vmax=450,   precip=False),
    "OCES":  dict(cmap="YlOrRd",  vmin=0,     vmax=200,   precip=False),
    "OLES":  dict(cmap="inferno", vmin=200,   vmax=450,   precip=False),
    "ROCE":  dict(cmap="YlOrRd",  vmin=0,     vmax=500,   precip=False),
    "ROLE":  dict(cmap="inferno", vmin=150,   vmax=300,   precip=False),
    "SWDN":  dict(cmap="YlOrRd",  vmin=0,     vmax=900,   precip=False),
    "LWDN":  dict(cmap="inferno", vmin=200,   vmax=450,   precip=False),
    "SWUP":  dict(cmap="YlOrRd",  vmin=0,     vmax=200,   precip=False),
    "LWUP":  dict(cmap="inferno", vmin=200,   vmax=450,   precip=False),
    "ALBE":  dict(cmap="YlGn",    vmin=0,     vmax=0.8,   precip=False),
    # Nuvens
    "LWNV":  dict(cmap="Greys",   vmin=0,     vmax=1,     precip=False),
    "MDNV":  dict(cmap="Greys",   vmin=0,     vmax=1,     precip=False),
    "HINV":  dict(cmap="Greys",   vmin=0,     vmax=1,     precip=False),
    "CLD":   dict(cmap="Greys",   vmin=0,     vmax=1,     precip=False),
    "CLDF":  dict(cmap="Greys",   vmin=0,     vmax=1,     precip=False),
    "TCLD":  dict(cmap="Greys",   vmin=0,     vmax=1,     precip=False),
    # Instabilidade / CLP
    "CAPE":  dict(cmap="hot_r",   vmin=0,     vmax=3000,  precip=False),
    "CIN":   dict(cmap="Blues_r", vmin=-500,  vmax=0,     precip=False),
    "HPBL":  dict(cmap="YlOrRd",  vmin=0,     vmax=3000,  precip=False),
    "PBLH":  dict(cmap="YlOrRd",  vmin=0,     vmax=3000,  precip=False),
    # Solo / escoamento
    "RNOF":  dict(cmap="Blues",   vmin=0,     vmax=None,  precip=False),
    "RNSG":  dict(cmap="Blues",   vmin=0,     vmax=None,  precip=False),
    # Transporte de umidade
    "QUINT": dict(cmap="bwr",     vmin=-300,  vmax=300,   precip=False),
    "QVINT": dict(cmap="bwr",     vmin=-300,  vmax=300,   precip=False),
}

# Inferencia de cmap por unidade (fallback quando a variavel nao esta na tabela)
_UNIT_CMAP = {
    "k":    ("RdBu_r",  None,  None),
    "hpa":  ("RdBu_r",  None,  None),
    "pa":   ("RdBu_r",  None,  None),
    "m/s":  ("bwr",     -20,   20),
    "w/m2": ("RdBu",    None,  None),
    "j/kg": ("hot_r",   0,     3000),
    "kg/m2":("YlGnBu",  0,     None),
    "mm/h": ("precip",  0,     50),
    "mm":   ("precip",  0,     200),
    "%":    ("YlGnBu",  0,     100),
}


# Tabela de metadados para variaveis 3D (NLEV > 0 no CTL / dim vertical no NetCDF)
# plot_levels: niveis de pressao (hPa) plotados por padrao
_VAR3D_META = {
    # Temperatura
    "T":       dict(cmap="RdBu_r",  vmin=210,   vmax=310,   precip=False, plot_levels=[850, 700, 500, 300, 250, 200]),
    "TEMP":    dict(cmap="RdBu_r",  vmin=210,   vmax=310,   precip=False, plot_levels=[850, 700, 500, 300, 250, 200]),
    "TMP":     dict(cmap="RdBu_r",  vmin=210,   vmax=310,   precip=False, plot_levels=[850, 700, 500, 300, 250, 200]),
    "TH":      dict(cmap="RdBu_r",  vmin=270,   vmax=500,   precip=False, plot_levels=[500, 300]),
    "THE":     dict(cmap="hot_r",   vmin=320,   vmax=380,   precip=False, plot_levels=[850, 700]),
    "THTE":    dict(cmap="hot_r",   vmin=320,   vmax=380,   precip=False, plot_levels=[850, 700]),
    # Vento
    "U":       dict(cmap="bwr",     vmin=-50,   vmax=50,    precip=False, plot_levels=[850, 500, 250, 200]),
    "V":       dict(cmap="bwr",     vmin=-50,   vmax=50,    precip=False, plot_levels=[850, 500, 250, 200]),
    "UWND":    dict(cmap="bwr",     vmin=-50,   vmax=50,    precip=False, plot_levels=[850, 500, 250]),
    "VWND":    dict(cmap="bwr",     vmin=-50,   vmax=50,    precip=False, plot_levels=[850, 500, 250]),
    "W":       dict(cmap="bwr",     vmin=-5,    vmax=5,     precip=False, plot_levels=[500]),
    "OMEGA":   dict(cmap="bwr",     vmin=-2,    vmax=2,     precip=False, plot_levels=[700, 500, 300]),
    "VV":      dict(cmap="bwr",     vmin=-2,    vmax=2,     precip=False, plot_levels=[500, 300]),
    # Altura geopotencial
    "Z":       dict(cmap="viridis", vmin=None,  vmax=None,  precip=False, plot_levels=[850, 500, 250]),
    "HGT":     dict(cmap="viridis", vmin=None,  vmax=None,  precip=False, plot_levels=[850, 500, 250]),
    "GH":      dict(cmap="viridis", vmin=None,  vmax=None,  precip=False, plot_levels=[850, 500, 250]),
    "GP":      dict(cmap="viridis", vmin=None,  vmax=None,  precip=False, plot_levels=[500, 250]),
    "GEOPOT":  dict(cmap="viridis", vmin=None,  vmax=None,  precip=False, plot_levels=[500]),
    # Umidade
    "Q":       dict(cmap="YlGnBu",  vmin=0,     vmax=0.022, precip=False, plot_levels=[850, 700]),
    "QV":      dict(cmap="YlGnBu",  vmin=0,     vmax=0.022, precip=False, plot_levels=[850, 700]),
    "SPFH":    dict(cmap="YlGnBu",  vmin=0,     vmax=0.022, precip=False, plot_levels=[850, 700]),
    "QC":      dict(cmap="Blues",   vmin=0,     vmax=0.001, precip=False, plot_levels=[500]),
    "QI":      dict(cmap="Purples", vmin=0,     vmax=0.001, precip=False, plot_levels=[300, 200]),
    "RH":      dict(cmap="YlGnBu",  vmin=0,     vmax=100,   precip=False, plot_levels=[850, 700, 500]),
    "RHUM":    dict(cmap="YlGnBu",  vmin=0,     vmax=100,   precip=False, plot_levels=[850, 700]),
    # Pressao / sigma
    "P":       dict(cmap="RdBu_r",  vmin=None,  vmax=None,  precip=False, plot_levels=[]),
    "PRES":    dict(cmap="RdBu_r",  vmin=None,  vmax=None,  precip=False, plot_levels=[]),
    # Nuvens
    "CFRAC":   dict(cmap="Greys",   vmin=0,     vmax=1,     precip=False, plot_levels=[500]),
    "CLDF3D":  dict(cmap="Greys",   vmin=0,     vmax=1,     precip=False, plot_levels=[500]),
    # Turbulencia
    "TKE":     dict(cmap="hot_r",   vmin=0,     vmax=5,     precip=False, plot_levels=[925, 850]),
    "KM":      dict(cmap="hot_r",   vmin=0,     vmax=100,   precip=False, plot_levels=[925]),
}


# ─────────────────────────────────────────────────────────────────────────────
# PARSER DO CTL
# ─────────────────────────────────────────────────────────────────────────────

class CTLParseError(ValueError):
    pass


def _parse_tdef_dt(dt_str: str) -> int:
    """
    Converte string de intervalo de tempo GrADS para horas.
    Exemplos: '1HR', '6HR', '3HR', '1DY', '30MN'
    """
    dt_str = dt_str.strip().upper()
    m = re.match(r'^(\d+)(HR|MN|DY|MO|YR)$', dt_str)
    if not m:
        raise CTLParseError(f"Intervalo de tempo nao reconhecido: '{dt_str}'")
    val, unit = int(m.group(1)), m.group(2)
    if unit == "HR":
        return val
    if unit == "MN":
        if val % 60 != 0:
            raise CTLParseError(f"Intervalo em minutos deve ser multiplo de 60: {val}MN")
        return val // 60
    if unit == "DY":
        return val * 24
    raise CTLParseError(f"Unidade de tempo '{unit}' nao suportada (use HR, MN ou DY)")


def _dset_to_prefix_suffix(dset: str) -> tuple[str, str, bool]:
    """
    Extrai (file_prefix, file_suffix, has_template) do padrao DSET do GrADS.

    O GrADS usa substituicoes de tempo no DSET quando OPTIONS TEMPLATE esta ativo:
      %y4  -> YYYY (ano 4 digitos)
      %y2  -> YY
      %m2  -> MM
      %m1  -> M
      %d2  -> DD
      %d1  -> D
      %h2  -> HH
      %h1  -> H
      %n2  -> mm (minutos)

    Ex: 'Eta03_BESM_2026060600+%y4%m2%d2%h2_2D.bin'
      prefix = 'Eta03_BESM_{run_tag}+'
      suffix = '_2D.bin'

    Estrategia:
      - Localiza o primeiro %xN ou %xX (marcador de tempo)
      - Tudo antes e o prefix (substituindo run_tag se encontrado)
      - Tudo depois do ultimo marcador de tempo e o suffix
    """
    # Remove ^ inicial (caminho relativo ao CTL no GrADS)
    dset = dset.lstrip('^').strip()

    time_tokens = ['%y4', '%y2', '%m2', '%m1', '%d2', '%d1', '%h2', '%h1', '%n2']

    # Posicao do primeiro e ultimo token de tempo
    first_pos = len(dset)
    last_end   = 0
    has_template = False

    for tok in time_tokens:
        idx = dset.find(tok)
        if idx != -1:
            has_template = True
            if idx < first_pos:
                first_pos = idx
            end = idx + len(tok)
            if end > last_end:
                last_end = end

    if not has_template:
        # Arquivo unico sem TEMPLATE — prefix = dset inteiro, suffix vazio
        return dset, "", False

    raw_prefix = dset[:first_pos]
    suffix     = dset[last_end:]

    # Tenta identificar o run_tag no prefix (sequencia de 10 digitos)
    # Ex: 'Eta03_BESM_2026060600+' -> run_tag = '2026060600'
    m = re.search(r'(\d{10})', raw_prefix)
    if m:
        prefix = raw_prefix[:m.start()] + "{run_tag}" + raw_prefix[m.end():]
    else:
        prefix = raw_prefix

    return prefix, suffix, True


def _infer_dtype(options: list[str]) -> str:
    """Infere dtype numpy a partir das OPTIONS do CTL."""
    opts_upper = [o.upper() for o in options]
    if "BYTESWAPPED" in opts_upper:
        return "<f4"  # little-endian
    return ">f4"      # big-endian (padrao GrADS)


def _infer_var_meta(name: str, units: str, description: str, nlev: int = 0) -> dict:
    """
    Retorna dict com cmap, vmin, vmax, precip (e plot_levels para 3D).
    Prioridade: tabela 3D (nlev>0) > tabela 2D > inferencia por unidade > defaults.
    """
    key = name.upper()
    if nlev > 0 and key in _VAR3D_META:
        return dict(_VAR3D_META[key])
    if key in _VAR_META:
        return dict(_VAR_META[key])

    # Tenta inferir pela unidade
    units_norm = units.lower().strip()
    for unit_key, (cmap, vmin, vmax) in _UNIT_CMAP.items():
        if unit_key in units_norm:
            return dict(cmap=cmap, vmin=vmin, vmax=vmax,
                        precip=("mm" in units_norm))

    # Fallback: escala automatica
    return dict(cmap="viridis", vmin=None, vmax=None, precip=False)


def _parse_vars_line(line: str) -> dict | None:
    """
    Parseia uma linha de variavel do CTL.
    Formato GrADS: NAME  NLEV  UNITS  Descricao longa
      - NLEV  : numero de niveis (0 = 2D)
      - UNITS : codigo numerico (ex: 99) OU string de unidade (ex: 'hPa')
    Retorna None se a linha for 'ENDVARS' ou vazia.
    """
    line = line.strip()
    if not line or line.upper() == "ENDVARS":
        return None

    parts = line.split(None, 3)  # maximo 4 campos
    if len(parts) < 2:
        return None

    name = parts[0]
    # nlev: 0 = variavel 2D (superficie); >0 = variavel 3D com N niveis verticais
    nlev_str = parts[1] if len(parts) > 1 else "0"
    try:
        nlev = int(nlev_str)
    except ValueError:
        nlev = 0
    units_raw = parts[2] if len(parts) > 2 else ""
    description = parts[3].strip() if len(parts) > 3 else ""

    # Se units_raw e puramente numerico, e o codigo GrADS (sem sentido semantico)
    if re.match(r'^-?\d+$', units_raw):
        # Tenta extrair unidade do description entre [ ] ou ( )
        m_bracket = re.search(r'\[([^\]]+)\]', description)
        m_paren   = re.search(r'\(([^)]+)\)', description)
        if m_bracket:
            units = m_bracket.group(1).strip()
        elif m_paren and len(m_paren.group(1)) <= 12:
            units = m_paren.group(1).strip()
        else:
            units = ""
        # Remove o trecho de unidade da description
        description = re.sub(r'\s*\[[^\]]+\]', '', description).strip()
    else:
        units = units_raw

    return dict(name=name, nlev=nlev, units=units, description=description or name)


def parse_ctl(path: str) -> dict:
    """
    Le e parseia um arquivo CTL GrADS.
    Retorna dict com chaves:
      dset, undef, dtype, options, sequential, yrev,
      nx, ny, lon0, lat0, dlon, dlat,
      ntimes, dt_hours,
      file_prefix, file_suffix,
      variables: list[dict]
    """
    ctl = pathlib.Path(path)
    if not ctl.exists():
        raise FileNotFoundError(f"CTL nao encontrado: {ctl}")

    result = {
        "dset": "", "undef": 1.0e+20,
        "dtype": ">f4", "options": [],
        "sequential": False, "yrev": False,
        "nx": 0, "ny": 0,
        "lon0": 0.0, "lat0": 0.0, "dlon": 0.0, "dlat": 0.0,
        "ntimes": 1, "dt_hours": 1,
        "file_prefix": "", "file_suffix": "",
        "title": "",
        "variables": [],
        "zdef": {"nz": 1, "levels": []},
    }

    lines = ctl.read_text(encoding="utf-8", errors="replace").splitlines()

    in_vars = False
    n_vars_expected = 0
    in_zdef = False
    zdef_nz = 0
    zdef_values = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith('*'):  # comentario
            continue

        upper = line.upper()

        # DSET
        if upper.startswith("DSET"):
            result["dset"] = line.split(None, 1)[1] if len(line.split(None, 1)) > 1 else ""
            continue

        # TITLE
        if upper.startswith("TITLE"):
            result["title"] = line.split(None, 1)[1] if len(line.split(None, 1)) > 1 else ""
            continue

        # UNDEF
        if upper.startswith("UNDEF"):
            try:
                result["undef"] = float(line.split()[1])
            except (IndexError, ValueError):
                pass
            continue

        # OPTIONS
        if upper.startswith("OPTIONS"):
            opts = line.split()[1:]
            result["options"] = opts
            opts_up = [o.upper() for o in opts]
            result["sequential"] = "SEQUENTIAL" in opts_up
            result["yrev"]       = "YREV" in opts_up
            result["dtype"]      = _infer_dtype(opts)
            continue

        # XDEF  NX  LINEAR  lon0  dlon
        if upper.startswith("XDEF"):
            parts = line.split()
            if len(parts) >= 5 and parts[2].upper() == "LINEAR":
                result["nx"]   = int(parts[1])
                result["lon0"] = float(parts[3])
                result["dlon"] = float(parts[4])
            continue

        # YDEF  NY  LINEAR  lat0  dlat
        if upper.startswith("YDEF"):
            parts = line.split()
            if len(parts) >= 5 and parts[2].upper() == "LINEAR":
                result["ny"]   = int(parts[1])
                result["lat0"] = float(parts[3])
                result["dlat"] = float(parts[4])
            continue

        # TDEF  NTIMES  LINEAR  start  dt
        if upper.startswith("TDEF"):
            parts = line.split()
            if len(parts) >= 5:
                result["ntimes"] = int(parts[1])
                try:
                    result["dt_hours"] = _parse_tdef_dt(parts[4])
                except CTLParseError as e:
                    print(f"[aviso] {e} — usando dt_hours=1", file=sys.stderr)
                    result["dt_hours"] = 1
            continue

        # ZDEF  NZ  {LINEAR z0 dz | LEVELS z1 z2 ...} (pode ser multi-linha)
        if in_zdef:
            for tok in line.split():
                try:
                    zdef_values.append(float(tok))
                except ValueError:
                    pass
            if len(zdef_values) >= zdef_nz:
                in_zdef = False
                result["zdef"]["levels"] = zdef_values[:zdef_nz]
            continue

        if upper.startswith("ZDEF"):
            parts_z = line.split()
            if len(parts_z) >= 2:
                try:
                    zdef_nz = int(parts_z[1])
                except ValueError:
                    zdef_nz = 1
                result["zdef"]["nz"] = zdef_nz
                if len(parts_z) > 2 and parts_z[2].upper() == "LINEAR" and len(parts_z) >= 5:
                    z0 = float(parts_z[3])
                    dz = float(parts_z[4])
                    result["zdef"]["levels"] = [round(z0 + i * dz, 6) for i in range(zdef_nz)]
                elif len(parts_z) > 2 and parts_z[2].upper() == "LEVELS":
                    inline = []
                    for tok in parts_z[3:]:
                        try: inline.append(float(tok))
                        except ValueError: pass
                    zdef_values = inline
                    if len(inline) >= zdef_nz:
                        result["zdef"]["levels"] = inline[:zdef_nz]
                    else:
                        in_zdef = True
            continue

        # VARS  N
        if upper.startswith("VARS") and not in_vars:
            try:
                n_vars_expected = int(line.split()[1])
            except (IndexError, ValueError):
                n_vars_expected = 0
            in_vars = True
            continue

        # Dentro do bloco VARS
        if in_vars:
            if upper == "ENDVARS":
                in_vars = False
                continue
            vinfo = _parse_vars_line(line)
            if vinfo:
                result["variables"].append(vinfo)
            continue

    # Deriva prefix/suffix do DSET
    prefix, suffix, _ = _dset_to_prefix_suffix(result["dset"])
    result["file_prefix"] = prefix
    result["file_suffix"] = suffix

    # Adiciona metadados inferidos a cada variavel
    zlevels = result["zdef"].get("levels", [])
    for v in result["variables"]:
        nlev_v = v.get("nlev", 0)
        meta = _infer_var_meta(v["name"], v.get("units", ""), v.get("description", ""), nlev=nlev_v)
        v.update(meta)
        if nlev_v > 0:
            v["ndim"] = 3
            v["levels"] = list(zlevels) if zlevels else []
            pl = v.get("plot_levels", [])
            if pl and zlevels:
                v["plot_levels"] = [p for p in pl if any(abs(p - z) < 1.0 for z in zlevels)] or list(zlevels[:6])
            elif not pl and zlevels:
                v["plot_levels"] = list(zlevels[:6])
        else:
            v["ndim"] = 2

    return result


# ─────────────────────────────────────────────────────────────────────────────
# GERADORES YAML
# (escrita manual para controle total de formatacao e comentarios)
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_float(v) -> str:
    """Formata float evitando notacao cientifica desnecessaria."""
    if v is None:
        return "~"
    if isinstance(v, float) and (abs(v) >= 1e10 or (abs(v) > 0 and abs(v) < 1e-4)):
        return f"{v:.3e}"
    if isinstance(v, float) and v == int(v):
        return str(int(v))
    return str(v)



def _path_to_data_dir_template(source_path: str) -> str:
    """
    Deriva um template de data_dir a partir do caminho completo do arquivo CTL/NetCDF.

    Substitui a primeira ocorrencia de run_tag (10 digitos = YYYYMMDDHH) por {data}.
    Se nao encontrar run_tag de 10 digitos, tenta data de 8 digitos (YYYYMMDD).

    Exemplos
    --------
    /dados/sismom_forecast/2026060600/regional/eta/2D/arquivo.ctl
      -> /dados/sismom_forecast/{data}/regional/eta/2D

    /dados/sismom_forecast/2026060600/regional/eta/3D/arquivo.nc
      -> /dados/sismom_forecast/{data}/regional/eta/3D

    /dados/rodadas/20260606/eta/arquivo.nc
      -> /dados/rodadas/{yyyy}{mm}{dd}/eta
    """
    if not source_path:
        return ""
    directory = str(pathlib.Path(source_path).parent)
    # Tenta run_tag de 10 digitos (YYYYMMDDHH)
    m = re.search(r'(\d{10})', directory)
    if m:
        return directory[:m.start()] + '{data}' + directory[m.end():]
    # Tenta data de 8 digitos (YYYYMMDD)
    m = re.search(r'(\d{8})', directory)
    if m:
        return directory[:m.start()] + '{yyyy}{mm}{dd}' + directory[m.end():]
    return directory


def generate_config_yaml(ctl: dict) -> str:
    """Gera o conteudo de config.yaml a partir do resultado do parse_ctl."""
    undef_str = f"{ctl['undef']:.3e}" if abs(ctl['undef']) >= 1e6 else str(ctl['undef'])
    prefix    = ctl["file_prefix"]
    suffix    = ctl["file_suffix"]

    # Variaveis de precipitacao para o bloco accumulation
    precip_vars = [v["name"] for v in ctl["variables"] if v.get("precip")]
    if not precip_vars:
        precip_vars = ["PREC"]

    pv_lines = "\n".join(f"    - {v}" for v in precip_vars)

    lines = []
    lines.append(f"# Gerado a partir de: {ctl.get('_source_file', 'arquivo.ctl')}")
    if ctl.get("title"):
        lines.append(f"# Titulo original: {ctl['title']}")
    lines.append("")
    lines.append("# " + "─" * 77)
    lines.append("# config.yaml — Configuracao do modelo (gerado por ctl_to_yaml.py)")
    lines.append("#")
    lines.append("# A tag da rodada NAO fica aqui; passe sempre via --run no CLI:")
    lines.append("#   --run 2026060600   (YYYYMMDDHH completo)")
    lines.append("#   --run 00           (00Z de hoje, data do sistema)")
    lines.append("# " + "─" * 77)
    lines.append("")
    lines.append("run:")
    lines.append(f"  ntimes: {ctl['ntimes']}          # numero de passos de tempo (inclui analise = 0)")
    lines.append(f"  dt_hours: {ctl['dt_hours']}       # intervalo de saida do modelo em horas")
    lines.append("")
    lines.append("grid:")
    lines.append(f"  nx: {ctl['nx']}")
    lines.append(f"  ny: {ctl['ny']}")
    lines.append(f"  lon0: {ctl['lon0']}   # longitude do canto sudoeste (graus E)")
    lines.append(f"  lat0: {ctl['lat0']}   # latitude do canto sudoeste (graus N)")
    lines.append(f"  dlon: {ctl['dlon']}")
    lines.append(f"  dlat: {ctl['dlat']}")
    lines.append("")
    lines.append("model:")
    lines.append(f"  undef: {undef_str}")
    lines.append(f'  dtype: "{ctl["dtype"]}"       # ">f4" big-endian | "<f4" little-endian (BYTESWAPPED)')
    lines.append(f'  file_prefix: "{prefix}"')
    lines.append(f'  file_suffix: "{suffix}"')
    lines.append(f'  sequential: {str(ctl["sequential"]).lower()}   # OPTIONS SEQUENTIAL no CTL')
    lines.append("")
    lines.append("paths:")
    # Deriva data_dir template a partir do caminho do arquivo fonte
    _src_path  = ctl.get("_source_path", "")
    _data_tpl  = _path_to_data_dir_template(_src_path)
    _data_line = f'  data_dir: "{_data_tpl}"' if _data_tpl else '  data_dir: ""  # ex: /dados/{data}/regional/eta/2D'
    lines.append("  # Caminho dos dados do modelo. Variaveis: {data}={run_tag}=YYYYMMDDHH, {yyyy}, {mm}, {dd}, {hh}")
    lines.append(_data_line)
    lines.append('  output_dir: "saida"')
    lines.append('  log_dir:    "logs"')
    lines.append("")
    lines.append("figure:")
    lines.append('  ext: "png"')
    lines.append("  dpi: 120")
    lines.append("")
    lines.append("accumulation:")
    lines.append("  hours: 24          # 24h = ACUM00Z + ACUM12Z; outros = janelas sequenciais")
    lines.append("  precip_vars:")
    for pv in precip_vars:
        lines.append(f"    - {pv}")
    lines.append("")
    return "\n".join(lines)


def generate_variables_yaml(ctl: dict) -> str:
    """Gera o conteudo de variables.yaml a partir do resultado do parse_ctl."""
    lines = [
        "# ─────────────────────────────────────────────────────────────────────────────",
        f"# variables.yaml — Variaveis 2D do modelo (gerado por ctl_to_yaml.py)",
        f"# Fonte: {ctl.get('_source_file', 'arquivo.ctl')}",
        "#",
        "# A ORDEM deve coincidir com o arquivo CTL do modelo.",
        "# cmap: colormap matplotlib; 'precip' usa paleta propria",
        "# vmin/vmax: null = escala automatica por percentis",
        "# enabled: false para desativar plot e COG (mantém posicao binaria)",
        "# ─────────────────────────────────────────────────────────────────────────────",
        "",
        "variables:",
        "",
    ]

    for v in ctl["variables"]:
        name  = v["name"]
        desc  = v.get("description", name)
        units = v.get("units", "")
        cmap  = v.get("cmap", "viridis")
        vmin  = _fmt_float(v.get("vmin"))
        vmax  = _fmt_float(v.get("vmax"))
        prec  = str(bool(v.get("precip", False))).lower()
        enab  = "true"

        lines.append(f"  - name: {name}")
        lines.append(f'    description: "{desc}"')
        if units:
            lines.append(f'    units: "{units}"')
        else:
            lines.append(f'    units: ""')
        lines.append(f"    cmap: {cmap}")
        lines.append(f"    vmin: {vmin}")
        lines.append(f"    vmax: {vmax}")
        lines.append(f"    precip: {prec}")
        lines.append(f"    enabled: {enab}")
        if v.get("ndim") == 3:
            nlev_v = v.get("nlev", 0)
            lev_v  = v.get("levels", [])
            pl_v   = v.get("plot_levels", [])
            lines.append(f"    ndim: 3")
            lines.append(f"    nlev: {nlev_v}")
            if lev_v:
                lev_fmt = "[" + ", ".join(
                    str(int(x)) if x == int(x) else str(round(x, 4))
                    for x in lev_v) + "]"
                lines.append(f"    levels: {lev_fmt}")
            else:
                lines.append("    levels: []   # preencha com os niveis do modelo")
            pl_fmt = "[" + ", ".join(str(int(p)) for p in pl_v) + "]" if pl_v else "[]"
            lines.append(f"    plot_levels: {pl_fmt}")
        lines.append("")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# PARSER NETCDF
# ─────────────────────────────────────────────────────────────────────────────

_NC_EXTENSIONS = {".nc", ".nc4", ".nc3", ".netcdf", ".cdf"}
_CTL_EXTENSIONS = {".ctl"}

# Candidatos de nome para coordenadas (ordem de prioridade)
_LON_CANDIDATES  = ["lon", "longitude", "XLONG", "nav_lon", "x", "lon_rho",
                    "Longitude", "LON", "lons", "lon_0"]
_LAT_CANDIDATES  = ["lat", "latitude",  "XLAT",  "nav_lat", "y", "lat_rho",
                    "Latitude",  "LAT", "lats", "lat_0"]
_TIME_CANDIDATES = ["time", "Time", "TIME", "t", "T", "times", "time0"]
_LEV_CANDIDATES  = ["level", "pressure", "lev", "plev", "sigma", "hybrid",
                    "eta", "height", "z", "depth", "isobaric", "pres",
                    "pfull", "phalf", "lev_p", "vertical", "Layer"]


def _detect_format(path: str) -> str:
    """Retorna 'netcdf' ou 'ctl' baseado na extensao do arquivo."""
    ext = pathlib.Path(path).suffix.lower()
    if ext in _NC_EXTENSIONS:
        return "netcdf"
    return "ctl"


def _nc_open(path: str):
    """
    Abre um arquivo NetCDF retornando um objeto compativel com netCDF4.Dataset.
    Tenta netCDF4 primeiro, cai para scipy se nao estiver instalado.
    Retorna (dataset, backend_name).
    """
    # Tenta netCDF4
    try:
        import netCDF4 as nc4
        return nc4.Dataset(path, "r"), "netCDF4"
    except ImportError:
        pass

    # Tenta scipy
    try:
        from scipy.io import netcdf_file
        return netcdf_file(path, "r", mmap=False), "scipy"
    except ImportError:
        pass

    raise ImportError(
        "Nenhuma biblioteca NetCDF encontrada.\n"
        "Instale com:  pip install netCDF4\n"
        "         ou:  pip install scipy"
    )


def _nc_find_coord(ds, candidates: list, cf_axis: str = None,
                   cf_standard: str = None) -> str | None:
    """
    Localiza uma variavel coordenada no dataset.
    Prioridade: nome exato > atributo axis > atributo standard_name.
    """
    all_vars = list(getattr(ds, "variables", {}).keys())

    # 1. Por nome exato
    for name in candidates:
        if name in all_vars:
            return name

    # 2. Por atributos CF
    for varname in all_vars:
        var = ds.variables[varname]
        if cf_axis:
            axis = getattr(var, "axis", None)
            if axis and str(axis).upper() == cf_axis.upper():
                return varname
        if cf_standard:
            sn = getattr(var, "standard_name", None)
            if sn and cf_standard.lower() in str(sn).lower():
                return varname

    return None


def _nc_coord_1d(ds, varname: str):
    """Retorna array 1-D da coordenada, extraindo a dimensao espacial se necessario."""
    import numpy as np
    var = ds.variables[varname]
    data = var[:]
    # Converte MaskedArray para ndarray
    if hasattr(data, "data"):
        data = np.array(data)
    # Se 2-D (grade curvilinear), pega a media ao longo de um eixo
    if data.ndim == 2:
        data = data[0, :]   # primeira linha (aproximacao para grade regular)
    return data.ravel().astype(float)


def _nc_infer_dt(time_var, backend: str) -> int:
    """
    Infere dt_hours a partir de uma variavel de tempo NetCDF.
    Usa o atributo 'units' (CF) ou inspeciona os valores.
    """
    units = getattr(time_var, "units", "") or ""
    units = str(units).lower()

    arr = time_var[:]
    if hasattr(arr, "data"):
        import numpy as np
        arr = np.array(arr, dtype=float)

    if len(arr) < 2:
        return 1

    dt_raw = float(arr[1]) - float(arr[0])

    if "hour" in units:
        return max(1, int(round(dt_raw)))
    if "day" in units:
        h = int(round(dt_raw * 24))
        return max(1, h)
    if "minute" in units:
        h = int(round(dt_raw / 60))
        return max(1, h)
    if "second" in units:
        h = int(round(dt_raw / 3600))
        return max(1, h)

    # Sem unidade explicita: heuristica por magnitude
    if 0 < dt_raw <= 24:
        return int(round(dt_raw))     # provavelmente horas
    if 24 < dt_raw <= 3:
        return int(round(dt_raw * 24))  # provavelmente dias
    return 1


def _nc_dtype(var) -> str:
    """Infere dtype numpy a partir da variavel NetCDF."""
    try:
        dt = var.dtype
        if dt.kind == "f" and dt.itemsize == 4:
            endian = dt.byteorder
            if endian == "<":
                return "<f4"
            return ">f4"   # big-endian ou nativo (NetCDF classico e big-endian)
        if dt.kind == "f" and dt.itemsize == 8:
            return ">f8"
    except Exception:
        pass
    return ">f4"


def _nc_filename_to_prefix_suffix(fname: str) -> tuple:
    """
    Tenta extrair prefix e suffix do nome do arquivo NetCDF.
    Ex: 'modelo_2026060600_2D.nc'  ->  ('modelo_{run_tag}_2D', '.nc')
    Ex: 'saida_00Z.nc'             ->  ('saida_{run_tag}', '.nc')
    """
    stem   = pathlib.Path(fname).stem
    suffix = pathlib.Path(fname).suffix

    # Procura run_tag de 10 digitos
    m = re.search(r"(\d{10})", stem)
    if m:
        prefix = stem[:m.start()] + "{run_tag}" + stem[m.end():]
        return prefix, suffix

    # Procura data de 8 digitos (YYYYMMDD)
    m = re.search(r"(\d{8})", stem)
    if m:
        prefix = stem[:m.start()] + "{run_tag}" + stem[m.end():]
        return prefix, suffix

    # Sem padrao detectado
    return stem + "_{run_tag}", suffix


def parse_netcdf(path: str) -> dict:
    """
    Le um arquivo NetCDF (CF / COARDS / WRF / generico) e retorna o mesmo
    formato de dicionario que parse_ctl(), pronto para generate_config_yaml()
    e generate_variables_yaml().

    Dependencias: netCDF4  ou  scipy.io.netcdf
    """
    import numpy as np

    result = {
        "dset": path, "undef": 1.0e+20,
        "dtype": ">f4", "options": [],
        "sequential": False, "yrev": False,
        "nx": 0, "ny": 0,
        "lon0": 0.0, "lat0": 0.0, "dlon": 0.0, "dlat": 0.0,
        "ntimes": 1, "dt_hours": 1,
        "file_prefix": "", "file_suffix": "",
        "title": "",
        "variables": [],
        "_backend": "",
        "_warnings": [],
    }

    ds, backend = _nc_open(path)
    result["_backend"] = backend

    try:
        # ── Atributos globais ─────────────────────────────────────────────────
        for attr in ("title", "TITLE", "Title", "description", "institution"):
            val = getattr(ds, attr, None)
            if val:
                result["title"] = str(val).strip()
                break

        # ── Coordenadas ───────────────────────────────────────────────────────
        lon_name  = _nc_find_coord(ds, _LON_CANDIDATES,  cf_axis="X", cf_standard="longitude")
        lat_name  = _nc_find_coord(ds, _LAT_CANDIDATES,  cf_axis="Y", cf_standard="latitude")
        time_name = _nc_find_coord(ds, _TIME_CANDIDATES, cf_axis="T", cf_standard="time")
        lev_name  = _nc_find_coord(ds, _LEV_CANDIDATES,  cf_axis="Z", cf_standard="pressure")

        if lon_name is None or lat_name is None:
            result["_warnings"].append(
                "Coordenadas lon/lat nao encontradas automaticamente. "
                "Verifique se o arquivo segue convencoes CF (axis=X/Y)."
            )

        # ── Grade ─────────────────────────────────────────────────────────────
        if lon_name:
            lon_arr = _nc_coord_1d(ds, lon_name)
            result["nx"]   = int(len(lon_arr))
            result["lon0"] = float(round(lon_arr[0], 8))
            if len(lon_arr) > 1:
                result["dlon"] = float(round(lon_arr[1] - lon_arr[0], 8))

        if lat_name:
            lat_arr = _nc_coord_1d(ds, lat_name)
            result["ny"]   = int(len(lat_arr))
            result["lat0"] = float(round(lat_arr[0], 8))
            if len(lat_arr) > 1:
                result["dlat"] = float(round(lat_arr[1] - lat_arr[0], 8))

        # ── Tempo ─────────────────────────────────────────────────────────────
        if time_name:
            time_var = ds.variables[time_name]
            t_arr = time_var[:]
            result["ntimes"]   = int(len(t_arr))
            result["dt_hours"] = _nc_infer_dt(time_var, backend)

        # ── Variaveis de dados ────────────────────────────────────────────────
        # Determina dimensoes espaciais esperadas
        lon_dims  = set(ds.variables[lon_name].dimensions)  if lon_name  else set()
        lat_dims  = set(ds.variables[lat_name].dimensions)  if lat_name  else set()
        time_dims = set(ds.variables[time_name].dimensions) if time_name else set()
        lev_dims  = set(ds.variables[lev_name].dimensions)  if lev_name  else set()
        spatial_dims = lon_dims | lat_dims
        coord_names  = {n for n in [lon_name, lat_name, time_name, lev_name] if n}
        if lev_name:
            import numpy as _np2
            _lev_raw = _np2.array(ds.variables[lev_name][:], dtype=float).ravel()
            zlevels_nc = sorted(float(x) for x in _lev_raw)
        else:
            zlevels_nc = []

        # Variaveis a ignorar (dimensoes, coordenadas, metadados comuns)
        _skip = coord_names | set(getattr(ds, "dimensions", {}).keys())
        _skip.update({"lon_bnds", "lat_bnds", "time_bnds", "lon_bounds", "lat_bounds",
                      "time_bounds", "crs", "projection", "Lambert_Conformal"})

        undef_found = None

        for varname, var in ds.variables.items():
            if varname in _skip:
                continue
            # Deve ter dimensoes espaciais
            if spatial_dims and not spatial_dims.issubset(set(var.dimensions)):
                continue
            # Apenas tipos numericos float/int
            try:
                kind = var.dtype.kind
            except Exception:
                continue
            if kind not in ("f", "i", "u"):
                continue
            # Ignora variaveis 1-D que provavelmente sao coordenadas auxiliares
            if var.ndim == 1:
                continue

            # Atributos da variavel
            long_name = (getattr(var, "long_name",    None)
                      or getattr(var, "description",  None)
                      or getattr(var, "standard_name", None)
                      or varname)
            units = str(getattr(var, "units", "") or "")

            # _FillValue / missing_value
            for fv_attr in ("_FillValue", "missing_value"):
                fv = getattr(var, fv_attr, None)
                if fv is not None:
                    try:
                        fv_float = float(np.array(fv).ravel()[0])
                        if undef_found is None:
                            undef_found = fv_float
                    except Exception:
                        pass
                    break

            # dtype (usa a primeira variavel float encontrada)
            if result["dtype"] == ">f4":
                result["dtype"] = _nc_dtype(var)

            is_3d   = bool(lev_name and lev_name in set(var.dimensions))
            nlev_nc = len(zlevels_nc) if is_3d else 0
            meta    = _infer_var_meta(varname, units, str(long_name), nlev=nlev_nc)
            entry   = dict(
                name=varname,
                description=str(long_name).strip(),
                units=units,
                nlev=nlev_nc,
                ndim=3 if is_3d else 2,
                **meta,
            )
            if is_3d:
                entry["levels"] = list(zlevels_nc)
                pl = entry.get("plot_levels", [])
                entry["plot_levels"] = pl if pl else [int(x) for x in zlevels_nc[:6]]
            result["variables"].append(entry)

        if undef_found is not None:
            result["undef"] = undef_found

    finally:
        if hasattr(ds, "close"):
            ds.close()

    # Prefix/suffix a partir do nome do arquivo
    prefix, suffix = _nc_filename_to_prefix_suffix(pathlib.Path(path).name)
    result["file_prefix"] = prefix
    result["file_suffix"] = suffix

    return result


# ─────────────────────────────────────────────────────────────────────────────
# PONTO DE ENTRADA UNIFICADO
# ─────────────────────────────────────────────────────────────────────────────

def parse_descriptor(path: str, fmt: str = "auto") -> dict:
    """
    Parseia um arquivo descritor (CTL ou NetCDF) e retorna o dicionario padrao.

    Parameters
    ----------
    path : caminho do arquivo
    fmt  : "auto" (detecta pela extensao), "ctl" ou "netcdf"
    """
    if fmt == "auto":
        fmt = _detect_format(path)

    if fmt == "netcdf":
        return parse_netcdf(path)
    return parse_ctl(path)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _print_summary(data: dict, source: str, fmt: str):
    """Imprime o resumo do parse no terminal."""
    print(f"\nResumo de '{pathlib.Path(source).name}' [{fmt.upper()}]:")
    if data.get("title"):
        print(f"  Titulo   : {data['title']}")
    if fmt == "netcdf" and data.get("_backend"):
        print(f"  Backend  : {data['_backend']}")
    print(f"  Grade    : {data['nx']} x {data['ny']} pontos")
    if data['nx'] and data['ny']:
        print(f"  Lon/Lat  : lon0={data['lon0']}  dlon={data['dlon']} | "
              f"lat0={data['lat0']}  dlat={data['dlat']}")
    print(f"  Tempo    : {data['ntimes']} passos x {data['dt_hours']}h "
          f"= {data['ntimes'] * data['dt_hours']}h")
    print(f"  dtype    : {data['dtype']}  |  undef={data['undef']:.3e}")
    if fmt == "ctl":
        print(f"  SEQUENTIAL: {data['sequential']}")
    n2d = sum(1 for v in data["variables"] if v.get("ndim", 2) == 2)
    n3d = sum(1 for v in data["variables"] if v.get("ndim", 2) == 3)
    if n3d:
        print(f"  Variaveis: {len(data['variables'])} ({n2d} 2D + {n3d} 3D)")
    else:
        print(f"  Variaveis: {len(data['variables'])}")
    if data["variables"]:
        names = [v["name"] for v in data["variables"]]
        preview = ", ".join(names[:12])
        if len(names) > 12:
            preview += f", ... (+{len(names)-12})"
        print(f"             {preview}")
    known = sum(1 for v in data["variables"]
                if v["name"].upper() in _VAR_META or v["name"].upper() in _VAR3D_META)
    if data["variables"]:
        unk = len(data["variables"]) - known
        print(f"  Colormaps: {known}/{len(data['variables'])} da tabela interna"
              f" ({unk} com viridis/automatico)")
    for w in data.get("_warnings", []):
        print(f"  [AVISO] {w}")


def main():
    parser = argparse.ArgumentParser(
        description="Gera config.yaml e variables.yaml a partir de CTL ou NetCDF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Exemplos:
              python ctl_to_yaml.py Eta03_BESM_2026060600+000_2D.ctl
              python ctl_to_yaml.py saida_modelo.nc
              python ctl_to_yaml.py saida.nc --list-vars
              python ctl_to_yaml.py saida.nc --next-to-ctl --force
              python ctl_to_yaml.py saida.nc --config /rodadas/run2/config.yaml
        """),
    )
    parser.add_argument("input", help="Arquivo de entrada: CTL GrADS ou NetCDF (.nc)")
    parser.add_argument("--format", choices=["auto", "ctl", "netcdf"], default="auto",
        help="Formato do arquivo (padrao: auto-detecta pela extensao)")
    parser.add_argument("--config", default=None,
        help="Caminho de saida para config.yaml (padrao: ./config.yaml)")
    parser.add_argument("--vars", default=None,
        help="Caminho de saida para variables.yaml (padrao: ./variables.yaml)")
    parser.add_argument("--next-to-ctl", "--next-to-input", dest="next_to_input",
        action="store_true",
        help="Salva os YAMLs na mesma pasta do arquivo de entrada")
    parser.add_argument("--stdout", action="store_true",
        help="Imprime os YAMLs no terminal, nao grava arquivos")
    parser.add_argument("--dry-run", action="store_true",
        help="Mostra o que seria gerado sem gravar nada")
    parser.add_argument("--list-vars", action="store_true",
        help="Lista as variaveis encontradas com metadados e sai (sem gerar YAMLs)")
    parser.add_argument("--force", action="store_true",
        help="Sobrepoe arquivos existentes sem perguntar")

    args = parser.parse_args()

    # Parseia o arquivo de entrada
    fmt = args.format
    if fmt == "auto":
        fmt = _detect_format(args.input)

    try:
        data = parse_descriptor(args.input, fmt)
    except FileNotFoundError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        sys.exit(1)
    except (CTLParseError, ImportError) as e:
        print(f"ERRO: {e}", file=sys.stderr)
        sys.exit(1)

    data["_source_file"] = pathlib.Path(args.input).name
    data["_source_path"] = str(pathlib.Path(args.input).resolve())

    # Modo --list-vars: lista variaveis e sai
    if args.list_vars:
        print(f"\nVariaveis em '{pathlib.Path(args.input).name}' ({len(data['variables'])} total):\n")
        fmt_row = "{:<12} {:<4} {:<10} {:<12} {:>8} {:>8}  {}"
        print(fmt_row.format("Nome", "Dim", "Cmap", "Unidade", "vmin", "vmax", "Descricao"))
        print("-" * 78)
        for v in data["variables"]:
            vmin = str(v.get("vmin", "~")) if v.get("vmin") is not None else "~"
            vmax = str(v.get("vmax", "~")) if v.get("vmax") is not None else "~"
            vmin = str(v.get("vmin")) if v.get("vmin") is not None else "~"
            vmax = str(v.get("vmax")) if v.get("vmax") is not None else "~"
            ndim_s = "3D" if v.get("ndim") == 3 else "2D"
            print(fmt_row.format(
                v["name"][:12],
                ndim_s,
                v.get("cmap", "viridis")[:10],
                str(v.get("units", ""))[:12],
                vmin[:8], vmax[:8],
                str(v.get("description", ""))[:45],
            ))
        print()
        _print_summary(data, args.input, fmt)
        return

    config_content = generate_config_yaml(data)
    vars_content   = generate_variables_yaml(data)

    base_dir = (pathlib.Path(args.input).parent
                if args.next_to_input else pathlib.Path("."))
    config_path = pathlib.Path(args.config) if args.config else base_dir / "config.yaml"
    vars_path   = pathlib.Path(args.vars)   if args.vars   else base_dir / "variables.yaml"

    if args.stdout or args.dry_run:
        sep   = "=" * 72
        label = "(DRY-RUN)" if args.dry_run else ""
        print(f"\n{sep}\n  config.yaml  {label}\n{sep}")
        print(config_content)
        print(f"\n{sep}\n  variables.yaml  {label}\n{sep}")
        print(vars_content)
        if args.dry_run:
            _print_summary(data, args.input, fmt)
            return

    if not args.stdout:
        for fpath, content, name in [
            (config_path, config_content, "config.yaml"),
            (vars_path,   vars_content,   "variables.yaml"),
        ]:
            if fpath.exists() and not args.force:
                resp = input(f"'{fpath}' ja existe. Sobrescrever? [s/N] ").strip().lower()
                if resp not in ("s", "sim", "y", "yes"):
                    print(f"Pulando {name}.")
                    continue
            fpath.write_text(content, encoding="utf-8")
            print(f"Gerado: {fpath}")

    _print_summary(data, args.input, fmt)


if __name__ == "__main__":
    main()
