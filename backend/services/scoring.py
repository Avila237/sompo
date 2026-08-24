"""
Orquestracao do fluxo de ponta a ponta (RF-01).

    leitura validada -> dados cadastrais -> derivacoes -> persiste avaliacao
                     -> modelo + SHAP -> persiste predicao -> resposta

Regra de camada: services importa de ml e db; nunca o contrario.
"""

from datetime import datetime, timezone

from backend.core import config
from backend.core.exceptions import EquipamentoNaoEncontrado, OperadorNaoEncontrado
from backend.db import repository as repo
from backend.ml.predictor import get_predictor


def derivar_manutencao(
    ultima_dias: int,
    ultima_horas: float,
    intervalo_dias: int,
    intervalo_horas: int,
) -> tuple[float, bool]:
    """
    Regra 14 de docs/data schema.md: o atraso e o maior entre a razao em dias e a
    razao em horas. Nunca gerar 'manutencao_atrasada' independentemente do pct.
    """
    razao_dias = ultima_dias / intervalo_dias if intervalo_dias else 0.0
    razao_horas = ultima_horas / intervalo_horas if intervalo_horas else 0.0
    atraso = max(razao_dias, razao_horas)
    atraso = round(min(atraso, 3.0), 3)
    return atraso, atraso > 1.0


def montar_registro(leitura: dict, equipamento: dict) -> dict:
    """Combina o que veio do campo com o que e cadastral e o que e derivado."""
    atraso, atrasada = derivar_manutencao(
        leitura["ultima_manutencao_dias"],
        leitura["ultima_manutencao_horas_op"],
        equipamento["intervalo_manut_recomendado_dias"],
        equipamento["intervalo_manut_recomendado_horas"],
    )

    registro = dict(leitura)
    registro.update(
        {
            "tipo_equipamento": equipamento["tipo_equipamento"],
            "idade_equipamento": equipamento["idade_equipamento"],
            "historico_sinistros": equipamento["historico_sinistros"],
            "tem_iot": equipamento["tem_iot"],
            "intervalo_manut_recomendado_dias": equipamento["intervalo_manut_recomendado_dias"],
            "intervalo_manut_recomendado_horas": equipamento["intervalo_manut_recomendado_horas"],
            "atraso_manutencao_pct": atraso,
            "manutencao_atrasada": atrasada,
        }
    )
    return registro


# Colunas cadastrais: vivem em 'equipamentos', nao se repetem em 'avaliacoes'.
_SO_DO_EQUIPAMENTO = {
    "tipo_equipamento",
    "idade_equipamento",
    "historico_sinistros",
    "tem_iot",
    "intervalo_manut_recomendado_dias",
    "intervalo_manut_recomendado_horas",
}


def processar_leitura(leitura: dict) -> dict:
    """
    Executa o fluxo completo e devolve o payload da resposta.

    Se a predicao falhar depois de a avaliacao ter sido gravada, a avaliacao e
    removida: o registro nao pode ficar orfao, sem predicao, em silencio (RF-03).
    """
    equipamento = repo.buscar_equipamento(leitura["equipamento_id"])
    if equipamento is None:
        raise EquipamentoNaoEncontrado(leitura["equipamento_id"])
    if not repo.operador_existe(leitura["operador_id"]):
        raise OperadorNaoEncontrado(leitura["operador_id"])

    registro = montar_registro(leitura, equipamento)
    agora = datetime.now(timezone.utc)

    linha_avaliacao = {
        k: v for k, v in registro.items() if k not in _SO_DO_EQUIPAMENTO
    }
    linha_avaliacao["timestamp"] = agora.isoformat()

    predictor = get_predictor(config.MODELS_DIR)
    explicacao = predictor.prever(registro)

    # O score do modelo e a fonte da verdade tambem para a coluna de target.
    linha_avaliacao["risco_score"] = explicacao.risco_score
    linha_avaliacao["faixa_risco"] = explicacao.faixa_risco

    avaliacao_id = repo.inserir_avaliacao(linha_avaliacao)

    try:
        repo.inserir_predicao(
            {
                "avaliacao_id": avaliacao_id,
                "risco_score_predito": explicacao.risco_score,
                "faixa_predita": explicacao.faixa_risco,
                "top_fatores_shap": explicacao.top_fatores,
                "modelo_versao": config.MODELO_VERSAO,
            }
        )
    except Exception:
        repo.remover_avaliacao(avaliacao_id)
        raise

    # A leitura agregada passa a enxergar a linha nova imediatamente.
    repo.invalidar_cache()

    return {
        "avaliacao_id": avaliacao_id,
        "equipamento_id": leitura["equipamento_id"],
        "risco_score": explicacao.risco_score,
        "faixa_risco": explicacao.faixa_risco,
        "contribuicoes_por_grupo": explicacao.contribuicoes_por_grupo,
        "top_fatores": explicacao.top_fatores,
        "modelo_versao": config.MODELO_VERSAO,
        "timestamp": agora.isoformat(),
    }
