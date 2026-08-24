"""Rotas de leitura consumidas pelo dashboard (RF-09)."""

from fastapi import APIRouter, Depends, Query

from backend.api.deps import usuario_atual
from backend.core.exceptions import EquipamentoNaoEncontrado
from backend.services import consultas

router = APIRouter(tags=["consultas"])


@router.get("/equipamentos")
def listar_equipamentos(
    faixa: str | None = Query(None, pattern="^(baixo|medio|alto)$"),
    busca: str | None = Query(None, min_length=1, max_length=60),
    usuario: dict = Depends(usuario_atual),
) -> dict:
    itens = consultas.listar_equipamentos()
    if faixa:
        itens = [e for e in itens if e["faixa_risco"] == faixa]
    if busca:
        alvo = busca.lower()
        itens = [
            e for e in itens
            if alvo in e["equipamento_id"].lower()
            or alvo in (e["modelo_equipamento"] or "").lower()
        ]
    return {"total": len(itens), "itens": itens}


@router.get("/equipamentos/{equipamento_id}")
def detalhe_equipamento(
    equipamento_id: str,
    usuario: dict = Depends(usuario_atual),
) -> dict:
    detalhe = consultas.detalhe_equipamento(equipamento_id)
    if detalhe is None:
        raise EquipamentoNaoEncontrado(equipamento_id)
    return detalhe


@router.get("/alertas")
def listar_alertas(
    limite: int = Query(7, ge=1, le=100),
    faixa_minima: str = Query("medio", pattern="^(baixo|medio|alto)$"),
    usuario: dict = Depends(usuario_atual),
) -> dict:
    itens = consultas.alertas(limite=limite, faixa_minima=faixa_minima)
    return {"total": len(itens), "itens": itens}


@router.get("/kpis")
def obter_kpis(
    dias: int = Query(30, ge=1, le=365, description="janela da serie de tendencia"),
    usuario: dict = Depends(usuario_atual),
) -> dict:
    return {
        "kpis": consultas.kpis(),
        "por_operacao": consultas.agregado_por_operacao(),
        "por_regiao": consultas.agregado_por_regiao(),
        "tendencia": consultas.tendencia(dias),
    }
