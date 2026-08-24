"""Emissao de token."""

from fastapi import APIRouter

from backend.api.schemas import TokenRequest, TokenResponse
from backend.core.security import autenticar, criar_token

router = APIRouter(tags=["auth"])


@router.post("/auth/token", response_model=TokenResponse)
def emitir_token(req: TokenRequest) -> TokenResponse:
    perfil = autenticar(req.usuario, req.senha)
    token, minutos = criar_token(req.usuario, perfil)
    return TokenResponse(access_token=token, perfil=perfil, expira_em_minutos=minutos)
