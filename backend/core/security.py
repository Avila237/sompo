"""
Hash de senha, emissao e validacao de JWT.

As senhas vivem na tabela `usuarios` (S4-18), com hash scrypt da stdlib: KDF
lenta, com sal e custo de memoria, sem dependencia nova e sem o limite de 72
bytes do bcrypt. Os parametros ficam gravados no proprio hash, entao subir o
custo depois nao invalida as senhas ja cadastradas.
"""

import base64
import hashlib
import hmac
import secrets
import threading
from datetime import datetime, timedelta, timezone

import jwt
from jwt import InvalidTokenError

from backend.core import config
from backend.core.exceptions import CredenciaisInvalidas

# Uma das combinacoes equivalentes recomendadas pela OWASP (N=2^14, r=8, p=5):
# 16 MiB por calculo, ~0,1 s. O login ja tem limite de tentativas por IP.
_N, _R, _P = 2**14, 8, 5
_MAXMEM = 64 * 1024 * 1024
# Teto de hashes simultaneos: sem ele, uma rajada de logins alocaria 16 MiB
# por thread do pool (~40) de uma vez.
_SIMULTANEOS = threading.BoundedSemaphore(4)


def _scrypt(senha: str, sal: bytes, n: int, r: int, p: int) -> bytes:
    with _SIMULTANEOS:
        return hashlib.scrypt(
            senha.encode("utf-8"), salt=sal, n=n, r=r, p=p, maxmem=_MAXMEM, dklen=32
        )


def _b64(dados: bytes) -> str:
    return base64.b64encode(dados).decode("ascii")


def gerar_hash(senha: str) -> str:
    """Formato: scrypt$n$r$p$sal$hash (base64)."""
    sal = secrets.token_bytes(16)
    return f"scrypt${_N}${_R}${_P}${_b64(sal)}${_b64(_scrypt(senha, sal, _N, _R, _P))}"


def senha_confere(senha: str, armazenado: str) -> bool:
    try:
        algoritmo, n, r, p, sal, esperado = armazenado.split("$")
        if algoritmo != "scrypt":
            return False
        calculado = _scrypt(senha, base64.b64decode(sal), int(n), int(r), int(p))
        return hmac.compare_digest(calculado, base64.b64decode(esperado))
    except (ValueError, TypeError, OverflowError):
        # Hash malformado ou adulterado no banco (ex.: n negativo ou gigante):
        # recusa, nao 500. O login continua negado.
        return False


def criar_token(usuario: str, perfil: str, operador_id: str | None = None) -> tuple[str, int]:
    """Devolve (token, minutos_ate_expirar)."""
    expira = datetime.now(timezone.utc) + timedelta(minutes=config.JWT_EXPIRE_MINUTES)
    payload = {"sub": usuario, "perfil": perfil, "operador_id": operador_id, "exp": expira}
    token = jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)
    return token, config.JWT_EXPIRE_MINUTES


def decodificar_token(token: str) -> dict:
    """
    Valida assinatura, expiracao e o conteudo. Levanta CredenciaisInvalidas.

    Perfil fora de PERFIS_VALIDOS, ou operador sem operador_id, e token
    invalido: sem isso a autorizacao por perfil recusaria por acaso, nao por regra.
    """
    try:
        dados = jwt.decode(
            token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM]
        )
    except InvalidTokenError as e:
        raise CredenciaisInvalidas() from e
    perfil = dados.get("perfil")
    operador_id = dados.get("operador_id")
    if "sub" not in dados or perfil not in config.PERFIS_VALIDOS:
        raise CredenciaisInvalidas()
    if perfil == "operador" and not operador_id:
        raise CredenciaisInvalidas()
    return {"usuario": dados["sub"], "perfil": perfil, "operador_id": operador_id}
