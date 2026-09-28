"""Disponibilidade do servico e dos artefatos do modelo."""

from fastapi import APIRouter

from backend.core import config
from backend.services import scoring

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Aberto (sem token): usado para checar se a API subiu."""
    modelo = scoring.status_modelo()
    return {
        "status": "ok" if modelo["carregado"] else "degradado",
        "modelo": modelo,
        "modelo_versao": config.MODELO_VERSAO,
    }
