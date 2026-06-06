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
from datetime import datetime, timedelta

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

def init_config(config_file=None, vars_file=None):
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
    run      = cfg["run"]
    RUN_TAG  = str(run["tag"])
    t0_str   = run.get("t0") or (
        f"{RUN_TAG[:4]}-{RUN_TAG[4:6]}-{RUN_TAG[6:8]}"
        f"T{RUN_TAG[8:10]}:00:00"
    )
    T0       = datetime.fromisoformat(t0_str)
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
    FILE_PREFIX = str(m["file_prefix"]).replace("{run_tag}", RUN_TAG)
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

    # ── Acumulados ─────�