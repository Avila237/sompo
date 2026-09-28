"""Rotas de leitura consumidas pelo dashboard (RF-09)."""

from typing import Literal

from fastapi import APIRouter, Depends, Query

from backend.api.deps import perfil_entre, usuario_atual
from backend.core.exceptions import AcessoNegado, EquipamentoNaoEncontrado
from backend.services import consultas
# Importada pelo nome: a minimizacao roda mesmo quando o modulo consultas e
# substituido por um falso (testes da matriz de perfis).
from backend.services.consultas import minimizar_para_operador

router = APIRouter(tags=["consultas"])

# Matriz perfil x rota (S4-18): estes veem a frota inteira; o operador so os
# equipamentos que ja operou, e nao ve as agregacoes da frota.
FROTA = ("analista", "gestor", "tecnico")


def _recorte(usuario: dict) -> set[str] | None:
    """None = sem recorte. Para o operador, os equipamentos que ele operou."""
    if usuario["perfil"] in FROTA:
        return None
    return consultas.equipamentos_do_operador(usuario["operador_id"])


def _minimizado(resposta: dict, usuario: dict) -> dict:
    """LGPD: para o operador, avaliacao de outro operador sai sem quem operou e onde."""
    if usuario["perfil"] in FROTA:
        return resposta
    return minimizar_para_operador(resposta, usuario["operador_id"])


@router.get("/equipamentos")
def listar_equipamentos(
    faixa: str | None = Query(None, pattern="^(baixo|medio|alto)$"),
    busca: str | None = Query(None, min_length=1, max_length=60),
    usuario: dict = Depends(usuario_atual),
) -> dict:
    itens = consultas.listar_equipamentos()
    recorte = _recorte(usuario)
    if recorte is not None:
        itens = [e for e in itens if e["equipamento_id"] in recorte]
    if faixa:
        itens = [e for e in itens if e["faixa_risco"] == faixa]
    if busca:
        alvo = busca.lower()
        itens = [
            e for e in itens
            if alvo in e["equipamento_id"].lower()
            or alvo in (e["modelo_equipamento"] or "").lower()
        ]
    return _minimizado({"total": len(itens), "itens": itens}, usuario)


@router.get("/equipamentos/{equipamento_id}")
def detalhe_equipamento(
    equipamento_id: str,
    usuario: dict = Depends(usuario_atual),
) -> dict:
    recorte = _recorte(usuario)
    # 403 antes de buscar: o operador nao descobre se um equipamento alheio existe.
    if recorte is not None and equipamento_id not in recorte:
        raise AcessoNegado(f"Equipamento '{equipamento_id}' fora do seu recorte.")
    detalhe = consultas.detalhe_equipamento(equipamento_id)
    if detalhe is None:
        raise EquipamentoNaoEncontrado(equipamento_id)
    return _minimizado(detalhe, usuario)


@router.get("/alertas")
def listar_alertas(
    limite: int = Query(7, ge=1, le=100),
    faixa_minima: str = Query("medio", pattern="^(baixo|medio|alto)$"),
    usuario: dict = Depends(usuario_atual),
) -> dict:
    itens = consultas.alertas(
        limite=limite, faixa_minima=faixa_minima, equipamentos=_recorte(usuario)
    )
    return _minimizado({"total": len(itens), "itens": itens}, usuario)


@router.get("/kpis")
def obter_kpis(
    dias: int = Query(30, ge=1, le=365, description="janela da serie de tendencia"),
    usuario: dict = Depends(perfil_entre(*FROTA)),
) -> dict:
    return {
        "kpis": consultas.kpis(),
        "por_operacao": consultas.agregado_por_operacao(),
        "por_regiao": consultas.agregado_por_regiao(),
        "tendencia": consultas.tendencia(dias),
    }


@router.get("/tendencias")
def obter_tendencias(
    eixo: Literal["equipamento", "regiao", "operacao"],
    dias: int = Query(30, ge=1, le=365, description="janela em dias com dados"),
    limite: int = Query(5, ge=1, le=20, description="quantos grupos devolver"),
    chave: str | None = Query(None, min_length=1, max_length=60),
    usuario: dict = Depends(perfil_entre(*FROTA)),
) -> dict:
    return consultas.tendencias(eixo=eixo, dias=dias, limite=limite, chave=chave)
