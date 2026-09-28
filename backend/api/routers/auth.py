"""Emissao de token."""

import math
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.api.schemas import TokenRequest, TokenResponse
from backend.core.exceptions import CredenciaisInvalidas
from backend.core.security import autenticar, criar_token

router = APIRouter(tags=["auth"])

# Limite de tentativas: MAX_FALHAS senhas erradas por IP dentro de JANELA_S
# bloqueiam o login daquele IP ate a falha mais antiga sair da janela.
# ponytail: estado em memoria, por processo. Com mais de um worker ou mais de
#   uma instancia, cada um conta separado; mover para um contador compartilhado
#   (tabela ou Redis) quando houver mais de um processo servindo a API.
MAX_FALHAS = 5
JANELA_S = 60.0
_falhas: dict[str, deque[float]] = defaultdict(deque)


def _relogio() -> float:
    return time.monotonic()


def limpar_tentativas() -> None:
    _falhas.clear()


def _segundos_de_bloqueio(ip: str) -> int:
    """0 se o IP pode tentar; senao, quantos segundos faltam para liberar."""
    agora = _relogio()
    falhas = _falhas[ip]
    while falhas and agora - falhas[0] >= JANELA_S:
        falhas.popleft()
    if len(falhas) < MAX_FALHAS:
        return 0
    return max(1, math.ceil(JANELA_S - (agora - falhas[0])))


@router.post("/auth/token", response_model=TokenResponse)
def emitir_token(req: TokenRequest, request: Request):
    ip = request.client.host if request.client else "desconhecido"
    espera = _segundos_de_bloqueio(ip)
    if espera:
        return JSONResponse(
            status_code=429,
            content={"detail": "Muitas tentativas de login. Tente novamente mais tarde."},
            headers={"Retry-After": str(espera)},
        )
    try:
        perfil = autenticar(req.usuario, req.senha)
    except CredenciaisInvalidas:
        _falhas[ip].append(_relogio())
        raise
    token, minutos = criar_token(req.usuario, perfil)
    return TokenResponse(access_token=token, perfil=perfil, expira_em_minutos=minutos)
