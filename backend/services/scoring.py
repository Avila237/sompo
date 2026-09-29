"""
Orquestracao do fluxo de ponta a ponta (RF-01).

    leitura validada -> dados cadastrais -> derivacoes -> persiste avaliacao
                     -> modelo + SHAP -> persiste predicao -> resposta

Regra de camada: services importa de ml e db; nunca o contrario.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone

from backend.core import config
from backend.core.exceptions import (
    AcessoNegado,
    ClimaIndisponivel,
    EquipamentoNaoEncontrado,
    LeituraInconsistente,
    LeituraReutilizada,
    ModeloIndisponivel,
    OperadorNaoEncontrado,
    SafeFieldError,
)
from backend.db import repository as repo
from backend.ml.predictor import get_predictor
from backend.services import auditoria, clima, consultas
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


def hash_do_payload(leitura: dict) -> str:
    """
    Impressao digital do que o cliente enviou, sem a propria chave. Calculada
    antes do enriquecimento climatico: um retry nao pode mudar de hash so
    porque a Open-Meteo respondeu outro valor na segunda vez.
    """
    # Opcional nulo e opcional ausente sao o mesmo payload: sem isto, um campo
    # opcional novo no schema mudaria o hash de um retry que atravessa o deploy.
    sem_chave = {k: v for k, v in leitura.items() if k != "leitura_id" and v is not None}
    canonico = json.dumps(sem_chave, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def autorizar_envio(quem: dict, leitura: dict) -> AcessoNegado | None:
    """
    Matriz perfil x rota (S4-18): o analista envia por qualquer operador
    (integracao, simulador); o operador so em nome proprio; gestor e tecnico
    so leem.
    """
    if quem["perfil"] == "analista":
        return None
    if quem["perfil"] == "operador":
        if leitura["operador_id"] != quem.get("operador_id"):
            return AcessoNegado(
                f"Operador {quem.get('operador_id')} so envia leituras em nome proprio, "
                f"nao de {leitura['operador_id']}."
            )
        # So para equipamento que ja esta no recorte: senao, uma leitura num
        # equipamento alheio o poria no recorte. Vem antes de buscar o
        # equipamento, para inexistente e alheio responderem igual.
        # ponytail: o primeiro vinculo de um operador novo entra pelo analista
        #   (integracao); tabela de alocacao operador x equipamento se isso pesar.
        if leitura["equipamento_id"] not in consultas.equipamentos_do_operador(quem["operador_id"]):
            return AcessoNegado(f"Equipamento '{leitura['equipamento_id']}' fora do seu recorte.")
        return None
    return AcessoNegado(f"Perfil '{quem['perfil']}' nao envia leituras.")


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

    Clima medido em campo prevalece: com o payload completo, a Open-Meteo nem
    e consultada. Incompleto, a Open-Meteo preenche o que falta, e umidade e
    condicao ausentes sao derivadas da chuva final (Regras 3 e 5), para nao
    misturar a chuva medida com a condicao que a API derivou de outra chuva.
    Sem payload completo e sem API, a leitura e recusada: nao se inventa clima.
    """
    leitura = dict(leitura)
    medidos = {c for c in CAMPOS_CLIMA if leitura.get(c) is not None}
    if medidos == set(CAMPOS_CLIMA):
        return leitura, "payload"

    externo = clima.buscar(
        leitura["latitude"], leitura["longitude"], leitura["tipo_solo"]
    )
    if externo is None:
        raise ClimaIndisponivel([c for c in CAMPOS_CLIMA if c not in medidos])

    for campo in ("temperatura_ar", "precipitacao_mm", "velocidade_vento"):
        if campo not in medidos:
            leitura[campo] = externo[campo]
    if "umidade_solo" not in medidos:
        leitura["umidade_solo"] = clima.derivar_umidade_solo(
            leitura["precipitacao_mm"], leitura["tipo_solo"]
        )
    if "condicao_clima" not in medidos:
        leitura["condicao_clima"] = clima.derivar_condicao_clima(leitura["precipitacao_mm"])
    return leitura, ("misto" if medidos else "open-meteo")


def processar_leitura(leitura: dict, usuario: dict) -> tuple[dict, bool]:
    """
    Executa o fluxo completo e devolve (payload da resposta, reenvio).

    Avaliacao e predicao sao gravadas numa transacao so (RF-03). reenvio=True
    quando o leitura_id ja estava gravado com o mesmo payload: nada e gravado
    e a resposta e a original.
    """
    quem = usuario
    # Autorizacao antes do reenvio: sem isto, gestor e tecnico receberiam 200
    # com o resultado gravado, e um operador leria a leitura de outro.
    negado = autorizar_envio(quem, leitura)
    if negado:
        raise _recusar(quem, leitura, negado)

    payload_hash = hash_do_payload(leitura)

    # Reenvio decidido antes de qualquer trabalho: o retry chega justamente
    # quando algo falhou, e nao pode depender de a Open-Meteo ou o modelo
    # estarem de pe. A funcao SQL segue como garantia na corrida.
    if leitura.get("leitura_id"):
        anterior = repo.buscar_por_leitura(leitura["leitura_id"])
        if anterior is not None:
            if anterior["payload_hash"] != payload_hash:
                raise _recusar(quem, leitura, LeituraReutilizada(leitura["leitura_id"]))
            return _resposta_do_reenvio(anterior["avaliacao_id"], quem), True

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
    linha_avaliacao["payload_hash"] = payload_hash

    explicacao = predictor.prever(registro)

    # O score do modelo e a fonte da verdade tambem para a coluna de target.
    linha_avaliacao["risco_score"] = explicacao.risco_score
    linha_avaliacao["faixa_risco"] = explicacao.faixa_risco

    predicao = {
        "risco_score_predito": explicacao.risco_score,
        "faixa_predita": explicacao.faixa_risco,
        "top_fatores_shap": explicacao.top_fatores,
        "contribuicoes_por_grupo": explicacao.contribuicoes_por_grupo,
        "modelo_versao": config.MODELO_VERSAO,
    }
    try:
        # Uma transacao so no banco: sem avaliacao orfa se a predicao falhar.
        avaliacao_id, reenvio = repo.registrar_avaliacao(linha_avaliacao, predicao)
    except LeituraReutilizada as e:
        raise _recusar(quem, leitura, e) from e
    except Exception as e:
        logger.error("gravacao falhou para %s: %s", leitura["equipamento_id"], e)
        auditoria.registrar(
            quem["usuario"], quem["perfil"], "avaliacao", "erro",
            equipamento_id=leitura["equipamento_id"],
            detalhe=f"gravacao falhou: {type(e).__name__}",
        )
        raise

    if reenvio:
        return _resposta_do_reenvio(avaliacao_id, quem), True

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
    }, False


def _resposta_do_reenvio(avaliacao_id: int, quem: dict) -> dict:
    """
    O cliente reenviou uma leitura ja gravada: devolve o resultado original,
    lido do banco, em vez de gravar de novo.
    """
    avaliacao = repo.buscar_avaliacao(avaliacao_id)
    equipamento = repo.buscar_equipamento(avaliacao["equipamento_id"]) or {}
    predicao = repo.predicao_de(avaliacao_id) or {}
    top = predicao.get("top_fatores_shap") or []
    faixa = avaliacao["faixa_risco"]
    # O X-Request-ID do 200 leva a avaliacao por esta linha, como o do 201
    # leva pela linha de sucesso.
    logger.info(
        "reenvio avaliacao %s: %s leitura_id=%s usuario=%s",
        avaliacao_id, avaliacao["equipamento_id"], avaliacao.get("leitura_id"), quem["usuario"],
    )
    auditoria.registrar(
        quem["usuario"], quem["perfil"], "avaliacao", "reenvio",
        equipamento_id=avaliacao["equipamento_id"],
        avaliacao_id=avaliacao_id,
        score_gerado=float(avaliacao["risco_score"]),
        modelo_versao=predicao.get("modelo_versao"),
        detalhe=f"reenvio da leitura_id {avaliacao.get('leitura_id')}",
    )
    return {
        "avaliacao_id": avaliacao_id,
        "equipamento_id": avaliacao["equipamento_id"],
        "risco_score": float(avaliacao["risco_score"]),
        "faixa_risco": faixa,
        "clima_origem": avaliacao["clima_origem"],
        "contribuicoes_por_grupo": predicao.get("contribuicoes_por_grupo") or {},
        "top_fatores": top,
        "recomendacoes": recomendar({**equipamento, **avaliacao}, faixa, top),
        "modelo_versao": predicao.get("modelo_versao") or config.MODELO_VERSAO,
        "timestamp": avaliacao["timestamp"],
    }
