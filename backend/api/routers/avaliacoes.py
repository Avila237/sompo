"""Ingestao de leituras e geracao de score."""

from fastapi import APIRouter, Depends, Response

from backend.api.deps import usuario_atual
from backend.api.schemas import LeituraTelemetria, RespostaScore
from backend.services.scoring import processar_leitura

router = APIRouter(tags=["avaliacoes"])


@router.post(
    "/avaliacoes",
    response_model=RespostaScore,
    status_code=201,
    responses={
        200: {"model": RespostaScore, "description": "Reenvio: leitura_id ja gravado com o mesmo payload"},
        409: {"description": "leitura_id ja gravado com outro payload"},
    },
)
def criar_avaliacao(
    leitura: LeituraTelemetria,
    response: Response,
    usuario: dict = Depends(usuario_atual),
) -> RespostaScore:
    """
    Recebe uma leitura de campo, persiste, roda o modelo e devolve o score
    acompanhado da decomposicao SHAP.
    """
    # mode=json: leitura_id vira texto, pronto para o JSON da funcao SQL.
    resultado, reenvio = processar_leitura(leitura.model_dump(mode="json"), usuario)
    if reenvio:
        # Leitura ja gravada: 200 com o resultado original, nada novo criado.
        response.status_code = 200
    return RespostaScore(**resultado)
