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
    global SISMOM_DATA_BASE, DATA_DIR
    global OUTPUT_DIR, ACCUM_DIR, COG_DIR, LOG_DIR
    global DPI, FIG_EXT
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

    # ── Caminhos ──────────────────────────────────────────────────────────────
    p                = cfg.get("paths", {})
    data_base_yaml   = p.get("data_base", "")
    SISMOM_DATA_BASE = os.environ.get("SISMOM_DATA_BASE", data_base_yaml)
    OUTPUT_DIR       = _resolve(p.get("output_dir", "figuras/campos"))
    ACCUM_DIR        = _resolve(p.get("accum_dir",  "figuras/acumulados"))
    COG_DIR          = _resolve(p.get("cog_dir",    "cog"))
    LOG_DIR          = _resolve(p.get("log_dir",    "logs"))
    DATA_DIR         = build_data_dir(RUN_TAG)

    # ── Figura ────────────────────────────────────────────────────────────────
    fig     = cfg.get("figure", {})
    DPI     = int(fig.get("dpi", 120))
    FIG_EXT = str(fig.get("ext", "png"))

    # ── Variaveis ─────────────────────────────────────────────────────────────
    # Inclui todas as definidas no YAML (enabled ou nao) para que a leitura
    # binaria continue correta (a posicao no arquivo depende da ordem do CTL).
    VARIABLES = [(v["name"], v["description"], v["units"]) for v in vars_raw]
    VAR_NAMES = [v["name"] for v in vars_raw]
    VAR_DESC  = {v["name"]: v["description"] for v in vars_raw}
    VAR_UNITS = {v["name"]: v["units"]       for v in vars_raw}
    VAR_INDEX = {v["name"]: i for i, v in enumerate(vars_raw)}
    CMAP_CONFIG = {
        v["name"]: (v.get("cmap", "viridis"), v.get("vmin"), v.get("vmax"))
        for v in vars_raw
    }

    # ── Acumulados ────────────────────────────────────────────────────────────
    accum       = cfg.get("accumulation", {})
    PRECIP_VARS = list(accum.get("precip_vars", ["PREC", "PRCV", "PRGE"]))
    PRECIP_SET  = set(PRECIP_VARS)


def _resolve(rel_or_abs: str) -> str:
    """Retorna caminho absoluto: absoluto se comecar com /, relativo ao projeto."""
    p = pathlib.Path(rel_or_abs)
    return str(p if p.is_absolute() else PROJECT_ROOT / p)


# ──────────────────────────────────────────────────────────────────────────────
# UTILITARIOS DE CAMINHO
# ──────────────────────────────────────────────────────────────────────────────

def build_data_dir(run: str, base: str = "") -> str:
    """
    Constroi o caminho completo para os arquivos .bin de um run.

    Prioridade:
      1. Argumento `base` (CLI --data_base)
      2. Variavel de ambiente SISMOM_DATA_BASE
      3. Campo paths.data_base em config.yaml
      4. Diretorio local data/ do projeto

    Exemplos:
      build_data_dir("2026060400", "/dados/sismom/SisMOM/sismom_forecast")
      -> "/dados/sismom/SisMOM/sismom_forecast/2026060400/regional/eta/2D"
    """
    effective = base or os.environ.get("SISMOM_DATA_BASE", "")
    if not effective:
        # Tenta pegar o valor carregado do yaml (pode nao estar inicializado ainda)
        effective = globals().get("SISMOM_DATA_BASE", "")
    if effective:
        return os.path.join(effective, run, "regional", "eta", "2D")
    return str(PROJECT_ROOT / "data")


def enabled_vars(vars_file=None):
    """
    Retorna a lista de nomes de variaveis com enabled=true no YAML.
    Util para filtrar quais variaveis processar por padrao.
    """
    vf = pathlib.Path(vars_file or _VARS_FILE)
    raw = _load_yaml(vf).get("variables", [])
    return [v["name"] for v in raw if v.get("enabled", True)]


# ──────────────────────────────────────────────────────────────────────────────
# INICIALIZACAO AUTOMATICA NA IMPORTACAO
# ──────────────────────────────────────────────────────────────────────────────
# Se RUN_TAG nao estiver disponivel (nem env nem config.yaml), a inicializacao
# e adiada — main.py chamara init_config(run_tag=...) antes de usar os valores.
try:
    init_config()
except ValueError:
    pass   # run_tag ausente; main.py vai inicializar com --run
