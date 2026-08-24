"""
Emissao e validacao de JWT.

Divida D1 (docs/spec-implementacao-entrega-03.md): as credenciais vivem em
variavel de ambiente, sem tabela de usuarios com hash. A comparacao usa
secrets.compare_digest para nao vazar informacao por tempo de resposta.
"""

import secrets
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from backend.core import config
from backend.core.exceptions import CredenciaisInvalidas


def autenticar(usuario: str, senha: str) -> str:
    """Valida credenciais e devolve o perfil. Levanta CredenciaisInvalidas."""
    registro = config.DEMO_USERS.get(usuario)
    # Compara mesmo com usuario inexistente, para nao revelar quais existem.
    esperado = registro["senha"] if registro else ""
    confere = secrets.compare_digest(senha, esperado)
    if not registro or not confere:
        raise CredenciaisInvalidas()
    return registro["perfil"]


def criar_token(usuario: str, perfil: str) -> tuple[str, int]:
    """Devolve (token, minutos_ate_expirar)."""
    expira = datetime.now(timezone.utc) + timedelta(minutes=config.JWT_EXPIRE_MINUTES)
    payload = {"sub": usuario, "perfil": perfil, "exp": expira}
    token = jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)
    return token, config.JWT_EXPIRE_MINUTES


def decodificar_token(token: str) -> dict:
    """Valida assinatura e expiracao. Levanta CredenciaisInvalidas se invalido."""
    try:
        dados = jwt.decode(
            token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM]
        )
    except JWTError as e:
        raise CredenciaisInvalidas() from e
    if "sub" not in dados or "perfil" not in dados:
        raise CredenciaisInvalidas()
    return {"usuario": dados["sub"], "perfil": dados["perfil"]}
