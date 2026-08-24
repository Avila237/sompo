"""
Trilha de auditoria (RF-08).

Grava na tabela 'auditoria' quem pediu, quando, sobre qual equipamento, qual
score saiu e qual versao do modelo decidiu. E a evidencia consultavel de
"rastrear entradas, saidas e decisoes do sistema".
"""

import logging

from backend.db.repository import get_client

logger = logging.getLogger("safefield.auditoria")


def registrar(
    usuario: str,
    perfil: str,
    acao: str,
    status: str,
    equipamento_id: str | None = None,
    avaliacao_id: int | None = None,
    score_gerado: float | None = None,
    modelo_versao: str | None = None,
    detalhe: str | None = None,
) -> None:
    """
    Nunca propaga excecao: falha ao auditar nao pode derrubar a operacao que
    ja foi concluida. Mas tambem nunca falha em silencio — o erro vai para o
    log com nivel ERROR.
    """
    registro = {
        "usuario": usuario,
        "perfil": perfil,
        "acao": acao,
        "status": status,
        "equipamento_id": equipamento_id,
        "avaliacao_id": avaliacao_id,
        "score_gerado": score_gerado,
        "modelo_versao": modelo_versao,
        "detalhe": detalhe,
    }
    try:
        get_client().table("auditoria").insert(registro).execute()
    except Exception as e:
        logger.error(
            "falha ao gravar auditoria (acao=%s usuario=%s): %s", acao, usuario, e
        )
