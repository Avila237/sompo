"""Dependencias compartilhadas dos routers."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.exceptions import CredenciaisInvalidas
from backend.core.security import decodificar_token

_bearer = HTTPBearer(auto_error=False)


def usuario_atual(
    credencial: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """
    Exige Bearer token valido. Aplicada a toda rota que le ou escreve dado.
    Sem token ou com token invalido: 401.
    """
    if credencial is None or not credencial.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token ausente.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return decodificar_token(credencial.credentials)
    except CredenciaisInvalidas:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido ou expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
