"""
config.py — Carrega configuracao de config.yaml e variables.yaml

Os arquivos YAML ficam na raiz do projeto (um nivel acima de scripts/).
Para usar arquivos alternativos, chame init_config() antes de importar
qualquer outro modulo do projeto:

    import config
    config.init_config("/caminho/para/meu_config.yaml",
                       "/caminho/para/minhas_variaveis.yaml")

Ordem de busca dos arquivos padrao:
  1. Variavel de ambiente CONFIG_FILE / VARIABLES_FILE
  2. <PROJECT_ROOT>/config.yaml e <PROJECT_ROOT>/variables.yaml
"""

import os
import pathlib
import numpy as np
from datetime import datetime, timedelta, date as _date

# ── Caminhos base ─────────────────────────────────────────────────────────────
SCRIPTS_DIR  = pathlib.Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPTS_DIR.parent

_DEFAULT_CONFIG    = PROJECT_ROOT / "config.yaml"
_DEFAULT_VARIABLES = PROJECT_ROOT / "variables.yaml"


# ──────────────────────────────────────────────────────────────────────────────
# CARREGAMENTO YAML
# ──────────────────────────────────────────────────────────────────────────────

def _load_yaml(path):
    """Carrega um arquivo YAML; lanca FileNotFoundError com mensagem util."""
    try:
        import yaml
    except ImportError:
        raise ImportError(
            "PyYAML e necessario para ler os arquivos de configuracao.\n"
            "Instale com: pip install pyyaml"
        )
    path = pathlib.Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Arquivo de configuracao nao encontrado: {path}\n"
            f"Crie o arquivo ou passe --config / --vars-file no CLI."
        )
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ──────────────────────────────────────────────────────────────────────────────
# INICIALIZACAO DAS CONSTANTES GLOBAIS
# ──────────────────────────────────────────────────────────────────────────────

def resolve_run_tag(run_input: str, ref_date: _date = None) -> str:
    """
    Resolve o identificador da rodada para o formato completo YYYYMMDDHH.

    Formatos aceitos
    ----------------
    "2026060600"  -> "2026060600"   (YYYYMMDDHH, 10 digitos)
    "00"          -> hoje + "00"    (HH, 2 digitos — usa data do sistema ou ref_date)
    "0"           -> hoje + "00"    (H, 1 digito  — completado com zero)
    "12"          -> hoje + "12"

    Parameters
    ----------
    run_input : tag completo ou apenas a hora (HH)
    ref_date  : data de referencia (padrao: hoje, datetime.date.today())

    Raises
    ------
    ValueError se o formato nao for reconhecido.
    """
    run_input = str(run_input).strip()

    if len(run_input) == 10 and run_input.isdigit():
        return run_input                          # formato completo

    if run_input.isdigit() and len(run_input) <= 2:
        hour     = run_input.zfill(2)            # "0" -> "00", "12" -> "12"
        today    = ref_date or _date.today()
        return today.strftime("%Y%m%d") + hour    # "2026060600"

    raise ValueError(
        f"Formato de rodada invalido: '{run_input}'.\n"
        f"Use YYYYMMDDHH (ex: 2026060600) ou HH (ex: 00 ou 12)."
    )


# ── Defaults de modulo (sobrescritos por init_config) ────────────────────────
RUN_TAG = ""; T0 = None; NTIMES = 0; DT_HOURS = 1; TIMESTAMPS = []
NX = 0; NY = 0; LON0 = 0.0; LAT0 = 0.0; DLON = 0.03; DLAT = 0.03
LONS = []; LATS = []
UNDEF = 1e20; DTYPE = ">f4"; FILE_PREFIX = ""; FILE_SUFFIX = ".bin"
SISMOM_DATA_BASE = ""; DATA_DIR = ""; DATA_DIR_TEMPLATE = ""
# DATA_DIR_TEMPLATE aceita: {data}/{run_tag} = YYYYMMDDHH, {yyyy}, {mm}, {dd}, {hh}
OUTPUT_DIR = "saida"
LOG_DIR = "logs"
DPI = 120; FIG_EXT = "png"
COG_COMPRESS = "DEFLATE"; COG_ZLEVEL = 1; COG_PREDICTOR = 2; COG_TILE_SIZE = 512
VARIABLES = []; VAR_NAMES = []; VAR_DESC = {}; VAR_UNITS = {}; VAR_INDEX = {}
PRECIP_VARS = []; PRECIP_SET = set(); CMAP_CONFIG = {}
_CONFIG_FILE = None; _VARS_FILE = None


def init_config(config_file=None, vars_file=None, run_tag=None):
    """
    Inicializa (ou reinicializa) todas as constantes a partir dos arquivos YAML.

    Chamado automaticamente na importacao do modulo com os arquivos padrao.
    Pode ser chamado novamente pelo main.py quando o usuario passa --config
    ou --vars-file, ANTES de importar reader, export_cog etc.

    Parameters
    ----------
    config_file : str | Path | None
        Caminho para config.yaml (None = usa padrao ou env CONFIG_FILE)
    vars_file   : str | Path | None
        Caminho para variables.yaml (None = usa padrao ou env VARIABLES_FILE)
    """
    global RUN_TAG, T0, NTIMES, DT_HOURS, TIMESTAMPS
    global NX, NY, LON0, LAT0, DLON, DLAT, LONS, LATS
    global UNDEF, DTYPE, FILE_PREFIX, FILE_SUFFIX
    global SISMOM_DATA_BASE, DATA_DIR, DATA_DIR_TEMPLATE
    global OUTPUT_DIR, LOG_DIR
    global DPI, FIG_EXT
    global COG_COMPRESS, COG_ZLEVEL, COG_PREDICTOR, COG_TILE_SIZE
    global VARIABLES, VAR_NAMES, VAR_DESC, VAR_UNITS, VAR_INDEX
    global PRECIP_VARS, PRECIP_SET
    global CMAP_CONFIG
    global _CONFIG_FILE, _VARS_FILE

    # Resolucao dos caminhos
    config_file = config_file or os.environ.get("CONFIG_FILE", _DEFAULT_CONFIG)
    vars_file   = vars_file   or os.environ.get("VARIABLES_FILE", _DEFAULT_VARIABLES)
    _CONFIG_FILE = pathlib.Path(config_file)
    _VARS_FILE   = pathlib.Path(vars_file)

    cfg      = _load_yaml(_CONFIG_FILE)
    vars_raw = _load_yaml(_VARS_FILE).get("variables", [])

    # ── Run ───────────────────────────────────────────────────────────────────
    run = cfg["run"]

    # Prioridade para run_tag: parametro > env RUN_TAG > config.yaml run.tag
    raw_tag = (
        run_tag
        or os.environ.get("RUN_TAG", "")
        or str(run.get("tag", ""))
    )
    if not raw_tag:
        raise ValueError(
            "Tag da rodada nao definido.\n"
            "Use --run YYYYMMDDHH ou --run HH (ex: --run 00 usa hoje 00Z),\n"
            "ou defina a variavel de ambiente RUN_TAG."
        )
    RUN_TAG  = resolve_run_tag(raw_tag)
    T0       = datetime(int(RUN_TAG[:4]), int(RUN_TAG[4:6]), int(RUN_TAG[6:8]),
                        int(RUN_TAG[8:10]))
    NTIMES   = int(run["ntimes"])
    DT_HOURS = int(run["dt_hours"])
    TIMESTAMPS = [T0 + timedelta(hours=i * DT_HOURS) for i in range(NTIMES)]

    # ── Grade ─────────────────────────────────────────────────────────────────
    g    = cfg["grid"]
    NX   = int(g["nx"])
    NY   = int(g["ny"])
    LON0 = float(g["lon0"])
    LAT0 = float(g["lat0"])
    DLON = float(g["dlon"])
    DLAT = float(g["dlat"])
    LONS = np.linspace(LON0, LON0 + (NX - 1) * DLON, NX)
    LATS = np.linspace(LAT0, LAT0 + (NY - 1) * DLAT, NY)

    # ── Modelo ────────────────────────────────────────────────────────────────
    m           = cfg["model"]
    UNDEF       = float(m["undef"])
    DTYPE       = str(m["dtype"])
    FILE_PREFIX = str(m["file_prefix"]).replace("{run_tag}", RUN_TAG)  # usa RUN_TAG ja resolvido
    FILE_SUFFIX = str(m["file_suffix"])

    # ── Caminhos ───────────────────────────────────────────────────────
    p    = cfg["paths"]
    SISMOM_DATA_BASE  = str(p.get("data_base", "")) or os.environ.get("SISMOM_DATA_BASE", "")
    DATA_DIR_TEMPLATE = str(p.get("data_dir", ""))   # suporta {data}, {yyyy}, {mm}, {dd}, {hh}
    DATA_DIR          = _resolve_path_template(DATA_DIR_TEMPLATE, RUN_TAG) if DATA_DIR_TEMPLATE else ""
    OUTPUT_DIR = str(p.get("output_dir", "saida"))
    LOG_DIR    = str(p.get("log_dir",    "logs"))

    # ── Figura ────────────────────────────────────────────────────────────────
    fig = cfg.get("figure", {})
    DPI     = int(fig.get("dpi", 120))
    FIG_EXT = str(fig.get("ext", "png"))

    # ── COG GeoTIFF ───────────────────────────────────────────────────────────
    cog = cfg.get("cog", {})
    COG_COMPRESS  = str(cog.get("compress",  "DEFLATE"))
    COG_ZLEVEL    = int(cog.get("zlevel",    1))
    COG_PREDICTOR = int(cog.get("predictor", 2))
    COG_TILE_SIZE = int(cog.get("tile_size", 512))

    # ── Variaveis ─────────────────────────────────────────────────────────────
    VARIABLES  = vars_raw
    VAR_NAMES  = [v["name"] for v in VARIABLES]
    VAR_DESC   = {v["name"]: v.get("description", v["name"]) for v in VARIABLES}
    VAR_UNITS  = {v["name"]: v.get("units", "")               for v in VARIABLES}
    VAR_INDEX  = {v["name"]: i                                   for i, v in enumerate(VARIABLES)}
    PRECIP_VARS = [v["name"] for v in VARIABLES if v.get("precip", False)]
    PRECIP_SET  = set(PRECIP_VARS)
    CMAP_CONFIG = {
        v["name"]: {
            "cmap" : v.get("cmap",  "viridis"),
            "vmin" : v.get("vmin",  None),
            "vmax" : v.get("vmax",  None),
            "precip": v.get("precip", False),
        }
        for v in VARIABLES
    }


def enabled_vars():
    """Retorna lista de nomes de variaveis com enabled=true em variables.yaml."""
    return [v["name"] for v in VARIABLES if v.get("enabled", True)]


def _resolve_path_template(template: str, run_tag: str) -> str:
    """
    Substitui variaveis de template em um caminho de dados.

    Variaveis suportadas
    --------------------
    {data}     -> YYYYMMDDHH  (run_tag completo)
    {run_tag}  -> YYYYMMDDHH  (alias de {data})
    {yyyy}     -> YYYY (ano 4 digitos)
    {mm}       -> MM   (mes 2 digitos)
    {dd}       -> DD   (dia 2 digitos)
    {hh}       -> HH   (hora 2 digitos)

    Exemplos
    --------
    template = "/dados/sismom/sismom_forecast/{data}/regional/eta/2D"
    run_tag  = "2026060600"
    -> "/dados/sismom/sismom_forecast/2026060600/regional/eta/2D"

    template = "/dados/sismom/sismom_forecast/{yyyy}{mm}{dd}{hh}/regional/eta/2D"
    -> "/dados/sismom/sismom_forecast/2026060600/regional/eta/2D"
    """
    if not template or not run_tag or len(run_tag) < 10:
        return template
    return (
        template
        .replace("{data}",    run_tag)
        .replace("{run_tag}", run_tag)
        .replace("{yyyy}",    run_tag[:4])
        .replace("{mm}",      run_tag[4:6])
        .replace("{dd}",      run_tag[6:8])
        .replace("{hh}",      run_tag[8:10])
    )


def build_data_dir(run_tag: str, base: str = "") -> str:
    """
    Resolve o caminho dos dados para uma rodada.

    Prioridade
    ----------
    1. --data_base CLI  (base != "")  — retrocompat ou template
    2. data_dir no config.yaml        — suporta template ou caminho fixo
    3. SISMOM_DATA_BASE env            — base fixa (retrocompat)
    4. data/ local                    — fallback de desenvolvimento
    """
    if base:
        # Suporta template ou caminho-base fixo (retrocompat)
        if "{" in base:
            return _resolve_path_template(base, run_tag)
        return os.path.join(base, run_tag, "regional", "eta", "2D")
    if DATA_DIR_TEMPLATE:
        return _resolve_path_template(DATA_DIR_TEMPLATE, run_tag)
    if SISMOM_DATA_BASE:
        return os.path.join(SISMOM_DATA_BASE, run_tag, "regional", "eta", "2D")
    return os.path.join("data", run_tag)


# ── Inicializacao automatica na importacao (com arquivos padrao) ───────────────
# Permite usar config.VAR_NAMES etc. sem chamar init_config() explicitamente.
# main.py vai chamar init_config() de novo se --config/--vars-file/--run forem
# passados, sobrescrevendo estes valores.
try:
    init_config()
except Exception:
    # Falha silenciosa na inicializacao automatica (arquivos YAML ausentes).
    # main.py vai chamar init_config() com os caminhos corretos.
    pass
