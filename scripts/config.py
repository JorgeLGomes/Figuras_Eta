"""
config.py — Configurações globais do modelo Eta
Baseado em: Eta03_BESM_2026060400_2D.ctl
"""

from datetime import datetime, timedelta
import numpy as np

# ──────────────────────────────────────────────
# GRID
# ──────────────────────────────────────────────
NX     = 2399
NY     = 1671
LON0   = -90.99252
LAT0   = -38.12884
DLON   = 0.03
DLAT   = 0.03

LONS   = np.linspace(LON0, LON0 + (NX - 1) * DLON, NX)
LATS   = np.linspace(LAT0, LAT0 + (NY - 1) * DLAT, NY)

UNDEF  = 1.e+20

# ──────────────────────────────────────────────
# TEMPO
# ──────────────────────────────────────────────
T0          = datetime(2026, 6, 4, 0)   # 00Z04Jun2026
DT_HOURS    = 1                          # passo de 1 hora
NTIMES      = 121                        # 121 passos

TIMESTAMPS  = [T0 + timedelta(hours=i) for i in range(NTIMES)]

# ──────────────────────────────────────────────
# ARQUIVO BINÁRIO (template GrADS)
# ──────────────────────────────────────────────
# Padrão do CTL: Eta03_BESM_2026060400+%y4%m2%d2%h2_2D.bin
# Prefixo fixo (run): Eta03_BESM_2026060400
RUN_TAG     = "2026060400"
FILE_PREFIX = f"Eta03_BESM_{RUN_TAG}+"
FILE_SUFFIX = "_2D.bin"

# Leitura: big-endian float32, sem marcadores Fortran (stream/direct)
DTYPE       = ">f4"       # big-endian float32
# Se os dados forem little-endian, trocar para "<f4"
# Se houver marcadores Fortran (SEQUENTIAL), use reader.py com opção sequential=True

# ──────────────────────────────────────────────
# VARIÁVEIS (ordem exata do CTL)
# ──────────────────────────────────────────────
VARIABLES = [
    # nome   , descrição                         , unidade
    ("PSLM"  , "Pressão ao Nível do Mar (Mesinger)", "hPa"),
    ("PSLC"  , "Pressão de Superfície"             , "hPa"),
    ("TP2M"  , "Temperatura 2 m"                   , "K"),
    ("MXTP"  , "Temperatura Máxima"                , "K"),
    ("MNTP"  , "Temperatura Mínima"                , "K"),
    ("DP2M"  , "Temperatura de Orvalho 2 m"        , "K"),
    ("US2M"  , "Umidade Específica 2 m"            , "%"),
    ("UR2M"  , "Umidade Relativa 2 m"              , "kg/kg"),
    ("U10M"  , "Componente U do Vento 10 m"        , "m/s"),
    ("V10M"  , "Componente V do Vento 10 m"        , "m/s"),
    ("MAGV"  , "Magnitude do Vento 10 m"           , "m/s"),
    ("U100"  , "Componente U do Vento 100 m"       , "m/s"),
    ("V100"  , "Componente V do Vento 100 m"       , "m/s"),
    ("PREC"  , "Precipitação Total Acum. 6h"       , "mm"),
    ("PRCV"  , "Precipitação Convectiva Acum. 6h"  , "mm"),
    ("PRGE"  , "Precipitação Estratiforme Acum. 6h", "mm"),
    ("NEVE"  , "Neve Acum. 6h"                     , "mm"),
    ("CLSF"  , "Fluxo de Calor Latente Sup."       , "W/m²"),
    ("CSSF"  , "Fluxo de Calor Sensível Sup."      , "W/m²"),
    ("GHFL"  , "Fluxo de Calor no Solo"            , "W/m²"),
    ("TSFC"  , "Temperatura de Superfície (skin)"  , "K"),
    ("TSOIL" , "Temperatura do Solo"               , "K"),
    ("USOIL" , "Umidade do Solo"                   , "0-1"),
    ("SMAV"  , "Disponibilidade de Água no Solo"   , "-"),
    ("RNOF"  , "Escoamento Superficial 6h"         , "-"),
    ("RNSG"  , "Escoamento Subsuperficial 6h"      , "-"),
    ("USST"  , "Tensão de Cisalhamento U Sup."     , "N/m²"),
    ("VSST"  , "Tensão de Cisalhamento V Sup."     , "N/m²"),
    ("LWNV"  , "Fração de Nuvens Baixas"           , "-"),
    ("MDNV"  , "Fração de Nuvens Médias"           , "-"),
    ("HINV"  , "Fração de Nuvens Altas"            , "-"),
    ("CLD"   , "Nebulosidade Total"                , "-"),
    ("OCIS"  , "Radiação SW Incidente Sup."        , "W/m²"),
    ("OLIS"  , "Radiação LW Incidente Sup."        , "W/m²"),
    ("OCES"  , "Radiação SW Sainte Sup."           , "W/m²"),
    ("OLES"  , "Radiação LW Sainte Sup."           , "W/m²"),
    ("ROCE"  , "Radiação SW Sainte TOA"            , "W/m²"),
    ("ROLE"  , "Radiação LW Sainte TOA"            , "W/m²"),
    ("ALBE"  , "Albedo"                            , "-"),
    ("CAPE"  , "CAPE"                              , "J/kg"),
    ("AGPL"  , "Água Precipitável"                 , "kg/m²"),
    ("QUINT" , "Transporte Integrado de Q×U"       , "kg/m/s"),
    ("QVINT" , "Transporte Integrado de Q×V"       , "kg/m/s"),
    ("CWINT" , "Água Líquida de Nuvem Integrada"   , "kg/m²"),
    ("CIINT" , "Gelo de Nuvem Integrado"           , "kg/m²"),
    ("HPBL"  , "Altura da CLP"                     , "m"),
]

# Dicionários de acesso rápido
VAR_NAMES   = [v[0] for v in VARIABLES]
VAR_DESC    = {v[0]: v[1] for v in VARIABLES}
VAR_UNITS   = {v[0]: v[2] for v in VARIABLES}
VAR_INDEX   = {v[0]: i for i, v in enumerate(VARIABLES)}

# Variáveis de precipitação para acumulado 24h
PRECIP_VARS = ["PREC", "PRCV", "PRGE"]

# ──────────────────────────────────────────────
# CAMINHOS DO PROJETO
# ──────────────────────────────────────────────
# scripts/ fica dentro de <PROJETO_ROOT>/scripts/
# Os demais diretórios ficam em <PROJETO_ROOT>/
import pathlib
SCRIPTS_DIR  = pathlib.Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPTS_DIR.parent

DATA_DIR    = str(PROJECT_ROOT / "data")
OUTPUT_DIR  = str(PROJECT_ROOT / "figuras" / "campos")
ACCUM_DIR   = str(PROJECT_ROOT / "figuras" / "acumulados_24h")
LOG_DIR     = str(PROJECT_ROOT / "logs")

DPI         = 120
FIG_EXT     = "png"
