"""Ingestao de leituras e geracao de score."""

from fastapi import APIRouter, Depends

from backend.api.deps import usuario_atual
from backend.api.schemas import LeituraTelemetria, RespostaScore
from backend.services.scoring import processar_leitura

router = APIRouter(tags=["avaliacoes"])


@router.post("/avaliacoes", response_model=RespostaScore, status_code=201)
def criar_avaliacao(
    leitura: LeituraTelemetria,
    usuario: dict = Depends(usuario_atual),
) -> RespostaScore:
    """
    Recebe uma leitura de campo, persiste, roda o modelo e devolve o score
    acompanhado da decomposicao SHAP.
    """
    resultado = processar_leitura(leitura.model_dump())
    return RespostaScore(**resultado)
