"""
Orquestracao do fluxo de ponta a ponta (RF-01).

    leitura validada -> dados cadastrais -> derivacoes -> persiste avaliacao
                     -> modelo + SHAP -> persiste predicao -> resposta

Regra de camada: services importa de ml e db; nunca o contrario.
"""

import logging
from datetime import datetime, timezone

from backend.core import config
from backend.core.exceptions import (
    ClimaIndisponivel,
    EquipamentoNaoEncontrado,
    LeituraInconsistente,
    ModeloIndisponivel,
    OperadorNaoEncontrado,
    SafeFieldError,
)
from backend.db import repository as repo
from backend.ml.predictor import get_predictor
from backend.services import auditoria, clima
from backend.services.recomendacoes import recomendar

logger = logging.getLogger("safefield.scoring")


def carregar_modelo():
    """Predictor carregado, ou ModeloIndisponivel (503) se os artefatos faltam."""
    try:
        return get_predictor(config.MODELS_DIR)
    except Exception as e:
        logger.error("modelo indisponivel em %s: %s", config.MODELS_DIR, e)
        raise ModeloIndisponivel() from e


def status_modelo() -> dict:
    """Para o /health, que e publico: diz se carregou, nunca o motivo da falha."""
    try:
        return {"carregado": True, "n_features": len(carregar_modelo().features)}
    except ModeloIndisponivel:
        return {"carregado": False}


def _recusar(quem: dict, leitura: dict, erro: SafeFieldError) -> SafeFieldError:
    """Registra a recusa na auditoria e devolve o erro para ser levantado."""
    auditoria.registrar(
        quem["usuario"], quem["perfil"], "avaliacao", "erro",
        equipamento_id=leitura["equipamento_id"],
        detalhe=erro.mensagem,
    )
    return erro


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


def conferir_com_cadastro(leitura: dict, equipamento: dict) -> str | None:
    """
    Regras 1 e 10 de docs/data schema.md: so equipamento com IoT mede a
    temperatura do motor, e implemento nao tem motor proprio. Devolve a
    mensagem da inconsistencia, ou None se a leitura confere com o cadastro.
    """
    if leitura.get("temperatura_motor") is None:
        return None
    if not equipamento["tem_iot"]:
        return (
            f"temperatura_motor enviada para {equipamento['equipamento_id']}, "
            "que nao tem IoT (Regra 1)"
        )
    if equipamento["tipo_equipamento"] == "implemento":
        return (
            f"temperatura_motor enviada para {equipamento['equipamento_id']}, "
            "um implemento sem motor proprio (Regra 10)"
        )
    return None


# Colunas cadastrais: vivem em 'equipamentos', nao se repetem em 'avaliacoes'.
_SO_DO_EQUIPAMENTO = {
    "tipo_equipamento",
    "idade_equipamento",
    "historico_sinistros",
    "tem_iot",
    "intervalo_manut_recomendado_dias",
    "intervalo_manut_recomendado_horas",
}


CAMPOS_CLIMA = (
    "temperatura_ar",
    "precipitacao_mm",
    "umidade_solo",
    "velocidade_vento",
    "condicao_clima",
)


def resolver_clima(leitura: dict) -> tuple[dict, str]:
    """
    Decide a procedencia do bloco climatico e devolve (leitura, clima_origem).

    Open-Meteo e preferencial. Se ela falhar, cai para o que veio no payload.
    Se nem isso existir, a leitura e recusada — nao se inventa clima para
    alimentar o modelo.
    """
    leitura = dict(leitura)
    do_payload = {c: leitura.get(c) for c in CAMPOS_CLIMA}
    payload_completo = all(v is not None for v in do_payload.values())

    externo = clima.buscar(
        leitura["latitude"], leitura["longitude"], leitura["tipo_solo"]
    )
    if externo is not None:
        leitura.update(externo)
        return leitura, "open-meteo"

    if payload_completo:
        logger.warning(
            "clima da Open-Meteo indisponivel; usando os valores do payload para %s",
            leitura["equipamento_id"],
        )
        return leitura, "payload"

    faltando = [c for c, v in do_payload.items() if v is None]
    raise ClimaIndisponivel(faltando)


def processar_leitura(leitura: dict, usuario: dict | None = None) -> dict:
    """
    Executa o fluxo completo e devolve o payload da resposta.

    Se a predicao falhar depois de a avaliacao ter sido gravada, a avaliacao e
    removida: o registro nao pode ficar orfao, sem predicao, em silencio (RF-03).
    """
    quem = usuario or {"usuario": "-", "perfil": "-"}

    equipamento = repo.buscar_equipamento(leitura["equipamento_id"])
    if equipamento is None:
        raise _recusar(quem, leitura, EquipamentoNaoEncontrado(leitura["equipamento_id"]))
    if not repo.operador_existe(leitura["operador_id"]):
        raise _recusar(quem, leitura, OperadorNaoEncontrado(leitura["operador_id"]))

    inconsistencia = conferir_com_cadastro(leitura, equipamento)
    if inconsistencia:
        raise _recusar(quem, leitura, LeituraInconsistente(inconsistencia))

    try:
        leitura, clima_origem = resolver_clima(leitura)
        predictor = carregar_modelo()
    except (ClimaIndisponivel, ModeloIndisponivel) as e:
        raise _recusar(quem, leitura, e) from e
    registro = montar_registro(leitura, equipamento)
    agora = datetime.now(timezone.utc)

    linha_avaliacao = {
        k: v for k, v in registro.items() if k not in _SO_DO_EQUIPAMENTO
    }
    linha_avaliacao["timestamp"] = agora.isoformat()
    # Procedencia: distingue o dado de ingestao do populado pelo seed em lote.
    linha_avaliacao["fonte"] = "telemetria"
    linha_avaliacao["clima_origem"] = clima_origem

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
    except Exception as e:
        repo.remover_avaliacao(avaliacao_id)
        logger.error(
            "predicao falhou para %s; avaliacao %s removida: %s",
            leitura["equipamento_id"], avaliacao_id, e,
        )
        auditoria.registrar(
            quem["usuario"], quem["perfil"], "avaliacao", "erro",
            equipamento_id=leitura["equipamento_id"],
            detalhe=f"predicao falhou, avaliacao {avaliacao_id} revertida",
        )
        raise

    # A leitura agregada passa a enxergar a linha nova imediatamente.
    repo.invalidar_cache()

    logger.info(
        "avaliacao %s: %s score=%.2f faixa=%s usuario=%s",
        avaliacao_id, leitura["equipamento_id"], explicacao.risco_score,
        explicacao.faixa_risco, quem["usuario"],
    )
    auditoria.registrar(
        quem["usuario"], quem["perfil"], "avaliacao", "sucesso",
        equipamento_id=leitura["equipamento_id"],
        avaliacao_id=avaliacao_id,
        score_gerado=explicacao.risco_score,
        modelo_versao=config.MODELO_VERSAO,
    )

    return {
        "avaliacao_id": avaliacao_id,
        "equipamento_id": leitura["equipamento_id"],
        "risco_score": explicacao.risco_score,
        "faixa_risco": explicacao.faixa_risco,
        "clima_origem": clima_origem,
        "contribuicoes_por_grupo": explicacao.contribuicoes_por_grupo,
        "top_fatores": explicacao.top_fatores,
        "recomendacoes": recomendar(registro, explicacao.faixa_risco, explicacao.top_fatores),
        "modelo_versao": config.MODELO_VERSAO,
        "timestamp": agora.isoformat(),
    }
