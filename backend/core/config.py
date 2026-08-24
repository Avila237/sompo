"""
Configuracao lida do ambiente. Nao importa nenhum outro modulo do projeto —
`core` e a camada de baixo e nunca aponta para cima.
"""

import os

from dotenv import load_dotenv

load_dotenv()


def _req(nome: str) -> str:
    """Le uma variavel obrigatoria. Falha alto e cedo se faltar."""
    valor = os.getenv(nome)
    if not valor:
        raise EnvironmentError(
            f"Variavel de ambiente obrigatoria ausente: {nome}. "
            f"Use .env.example como referencia."
        )
    return valor


def _lista(nome: str, default: str = "") -> list[str]:
    bruto = os.getenv(nome, default)
    return [p.strip() for p in bruto.split(",") if p.strip()]


# --- Supabase -------------------------------------------------------------
SUPABASE_URL = _req("SUPABASE_URL")
# service_role bypassa RLS: e o unico caminho de escrita e vive so no servidor.
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or _req("SUPABASE_KEY")

# --- Seguranca ------------------------------------------------------------
JWT_SECRET_KEY = _req("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))

PERFIS_VALIDOS = ("operador", "gestor", "analista")


def _parse_demo_users(bruto: str) -> dict[str, dict[str, str]]:
    """
    Formato: usuario:senha:perfil,usuario:senha:perfil

    Divida 14: credenciais em variavel de ambiente, sem tabela de usuarios com
    hash. Registrado como divida D1 em docs/spec-implementacao-entrega-03.md.
    """
    usuarios: dict[str, dict[str, str]] = {}
    for entrada in bruto.split(","):
        entrada = entrada.strip()
        if not entrada:
            continue
        partes = entrada.split(":")
        if len(partes) != 3:
            raise ValueError(
                f"DEMO_USERS malformado em '{entrada}': esperado usuario:senha:perfil"
            )
        usuario, senha, perfil = (p.strip() for p in partes)
        if perfil not in PERFIS_VALIDOS:
            raise ValueError(
                f"Perfil invalido '{perfil}' para o usuario '{usuario}'. "
                f"Validos: {', '.join(PERFIS_VALIDOS)}"
            )
        usuarios[usuario] = {"senha": senha, "perfil": perfil}
    if not usuarios:
        raise ValueError("DEMO_USERS nao definiu nenhum usuario.")
    return usuarios


DEMO_USERS = _parse_demo_users(_req("DEMO_USERS"))

# --- API externa ----------------------------------------------------------
OPENMETEO_BASE_URL = os.getenv("OPENMETEO_BASE_URL", "https://api.open-meteo.com/v1")
OPENMETEO_TIMEOUT_S = float(os.getenv("OPENMETEO_TIMEOUT_S", "5"))

# --- API ------------------------------------------------------------------
API_CORS_ORIGINS = _lista(
    "API_CORS_ORIGINS", "http://localhost:5173,http://localhost:5175"
)

# --- Modelo ---------------------------------------------------------------
MODELS_DIR = os.getenv("MODELS_DIR", "models")
MODELO_VERSAO = os.getenv("MODELO_VERSAO", "xgboost-v1-baseline")
