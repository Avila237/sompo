"""Disponibilidade do servico e dos artefatos do modelo."""

from fastapi import APIRouter

from backend.core import config
from backend.ml.predictor import get_predictor

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Aberto (sem token): usado para checar se a API subiu."""
    try:
        p = get_predictor(config.MODELS_DIR)
        modelo = {"carregado": True, "n_features": len(p.features)}
    except Exception as e:
        modelo = {"carregado": False, "erro": str(e)}
    return {
        "status": "ok" if modelo["carregado"] else "degradado",
        "modelo": modelo,
        "modelo_versao": config.MODELO_VERSAO,
    }
