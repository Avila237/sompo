"""Emissao de token."""

import math
import threading
import time
from collections import defaultdict, deque

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.api.schemas import TokenRequest, TokenResponse
from backend.core.security import criar_token
from backend.services.autenticacao import autenticar

router = APIRouter(tags=["auth"])

# Limite de tentativas: MAX_FALHAS senhas erradas por IP dentro de JANELA_S
# bloqueiam o login daquele IP ate a falha mais antiga sair da janela.
# ponytail: estado em memoria, por processo. Com mais de um worker ou mais de
#   uma instancia, cada um conta separado; mover para um contador compartilhado
#   (tabela ou Redis) quando houver mais de um processo servindo a API.
MAX_FALHAS = 5
JANELA_S = 60.0
_falhas: dict[str, deque[float]] = defaultdict(deque)
_trava = threading.Lock()


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
    # A tentativa conta ANTES do hash, que leva ~0,1-0,3 s: contando so depois,
    # requisicoes simultaneas passariam todas pela checagem. O sucesso devolve.
    with _trava:
        espera = _segundos_de_bloqueio(ip)
        if not espera:
            marca = _relogio()
            _falhas[ip].append(marca)
    if espera:
        return JSONResponse(
            status_code=429,
            content={"detail": "Muitas tentativas de login. Tente novamente mais tarde."},
            headers={"Retry-After": str(espera)},
        )
    conta = autenticar(req.usuario, req.senha)
    with _trava:
        _falhas[ip].remove(marca)
    token, minutos = criar_token(req.usuario, conta["perfil"], conta["operador_id"])
    return TokenResponse(
        access_token=token, perfil=conta["perfil"], operador_id=conta["operador_id"],
        expira_em_minutos=minutos,
    )
