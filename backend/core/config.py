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


# 32 bytes = 256 bits, o tamanho da chave do HS256. Abaixo disso o segredo
# cabe num ataque de forca bruta offline sobre qualquer token capturado.
SEGREDO_JWT_MINIMO = 32


def validar_segredo_jwt(valor: str | None) -> str:
    """
    Recusa segredo ausente ou curto. Os placeholders do .env.example tem menos
    de 32 bytes de proposito: copiar o exemplo sem trocar o valor impede a API
    de subir, em vez de rodar com um segredo que qualquer um conhece.
    """
    if not valor or not valor.strip():
        raise EnvironmentError(
            "Variavel de ambiente obrigatoria ausente: JWT_SECRET_KEY. "
            "Use .env.example como referencia."
        )
    if len(valor.encode("utf-8")) < SEGREDO_JWT_MINIMO:
        raise EnvironmentError(
            f"JWT_SECRET_KEY tem menos de {SEGREDO_JWT_MINIMO} bytes. Gere um com: "
            'python -c "import secrets; print(secrets.token_hex(32))"'
        )
    return valor


# --- Supabase -------------------------------------------------------------
SUPABASE_URL = _req("SUPABASE_URL")
# service_role bypassa RLS: e o unico caminho de escrita e vive so no servidor.
# SUPABASE_KEY e o nome antigo, aceito para nao quebrar .env ja existentes.
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or _req("SUPABASE_KEY")

# --- Seguranca ------------------------------------------------------------
JWT_SECRET_KEY = validar_segredo_jwt(os.getenv("JWT_SECRET_KEY"))
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))

# Usuarios e senhas vivem na tabela `usuarios` (S4-18), nao em variavel de
# ambiente. Cadastro: scripts/criar_usuario.py. O que cada perfil acessa esta
# em docs/contrato-api.md (matriz perfil x rota).
PERFIS_VALIDOS = ("analista", "gestor", "tecnico", "operador")

# --- API externa ----------------------------------------------------------
OPENMETEO_BASE_URL = os.getenv("OPENMETEO_BASE_URL", "https://api.open-meteo.com/v1")
OPENMETEO_TIMEOUT_S = float(os.getenv("OPENMETEO_TIMEOUT_S", "5"))

# --- API ------------------------------------------------------------------
API_CORS_ORIGINS = _lista(
    "API_CORS_ORIGINS", "http://localhost:5173,http://localhost:5175"
)

# --- Modelo ---------------------------------------------------------------
MODELS_DIR = os.getenv("MODELS_DIR", "models")
MODELO_VERSAO = os.getenv("MODELO_VERSAO", "xgboost-v1.1")
