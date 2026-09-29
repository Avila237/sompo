"""
Evidencia de confiabilidade da coleta contra a API e o banco reais (S4-28, R4-07).

O que faz:
  1. le do banco pares equipamento x operador que ja tem avaliacao;
  2. envia N leituras pela API em execucao, cada uma com o seu leitura_id,
     geradas pelo gerador do simulador e enviadas pela funcao de retry dele
     (scripts/simulate_telemetry.py: enviar_com_retry);
  3. injeta falha do lado do cliente: em 1 de cada k leituras a primeira
     resposta de sucesso e descartada, como se a rede caisse depois de a API
     gravar, e a leitura e reenviada com a mesma chave;
  4. consulta o banco pelos leitura_id enviados e confere: uma avaliacao por
     leitura, uma predicao por avaliacao, nenhuma orfa, nenhuma duplicata, a
     entrada gravada igual a enviada, e a trilha request_id -> linha de log ->
     avaliacao_id -> clima_origem, modelo_versao, usuario e horario.

So le o banco. O que fica gravado e o que a propria API grava: N avaliacoes,
N predicoes e as linhas de auditoria. A contraparte offline, que roda na CI
com falhas de Open-Meteo e de banco tambem, e tests/test_confiabilidade_coleta.py.

Autenticacao (perfil analista, o unico que envia leitura por qualquer operador):
  - padrao: login em /auth/token. Usuario em --usuario (default:
    SAFEFIELD_USUARIO, ou 'analista'); senha em SAFEFIELD_SENHA ou pedida no
    terminal, sem eco. O usuario precisa ter perfil analista, e a auditoria
    tem de mostrar exatamente ele;
  - --token-local: token assinado aqui com criar_token('analista', 'analista')
    e o JWT_SECRET_KEY do .env, que precisa ser o da API em execucao. Nao
    passa pelo login; so para desenvolvimento. O relatorio registra o modo.

Log correlacionado: suba a API com a saida num arquivo, ex.
    uvicorn backend.api.main:app --port 8000 2>&1 | tee /tmp/safefield-api.log
e passe --log-api /tmp/safefield-api.log. Cada 201 precisa ter no log a linha
"[<request_id>] safefield.scoring: avaliacao <id>: ...", e cada 200 de reenvio
"[<request_id>] safefield.scoring: reenvio avaliacao <id>: ...". Sem --log-api
a checagem do log sai FALHOU (nao conferida), e o resultado tambem.

O JSON de saida nao leva latitude nem longitude: a leitura enviada fica so em
memoria, para a conferencia contra o banco, e das respostas de erro so sai o
motivo, sem o valor recebido.

Uso:
    python scripts/evidencias/coleta_real.py --log-api /tmp/safefield-api.log --saida /tmp/coleta_real.json
    python scripts/evidencias/coleta_real.py --n 30 --k 3 --api http://127.0.0.1:8000 --log-api ...

Codigo de saida: 0 se todas as checagens passarem, 1 se alguma falhar, 2 se
a API ou o banco estiverem inacessiveis nos pontos de controle (health, login,
leitura do banco, arquivo de log). Falha de rede durante a coleta nao
interrompe: fica registrada na tentativa e reprova as checagens.
"""

import argparse
import getpass
import json
import os
import random
import re
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone

import httpx
import requests
from postgrest.exceptions import APIError

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.core.security import criar_token  # noqa: E402
from backend.db import repository as repo  # noqa: E402
from backend.services.clima import derivar_condicao_clima, derivar_umidade_solo  # noqa: E402
from scripts import simulate_telemetry as simulador  # noqa: E402

TIMEOUT_S = 30
PERFIL_EXIGIDO = "analista"
SEM_LOG = "nao conferida (sem --log-api)"

# Falha do banco vista pelo cliente Supabase: transporte (httpx) ou PostgREST.
ERROS_DO_BANCO = (httpx.HTTPError, APIError)

# Linha do scoring que liga um request_id a um avaliacao_id: a de sucesso
# (201) ou a de reenvio (200). Formato de backend/core/logging.py.
RE_LINHA_DE_LOG = re.compile(
    r"\[(?P<rid>[^\]\s]+)\] safefield\.scoring: (?P<reenvio>reenvio )?avaliacao (?P<aid>\d+): "
)


class Interrompido(Exception):
    """API ou banco inacessivel: nao ha coleta para conferir (codigo de saida 2)."""


class RespostaDescartada(requests.ConnectionError):
    """A API respondeu, e o cliente age como se a rede tivesse caido na volta."""


# --- Geracao ---------------------------------------------------------------

def clima_de_campo(tipo_solo: str, rng=random) -> dict:
    """
    O bloco de --sem-clima-externo do simulador: clima medido em campo, com
    umidade e condicao pelas mesmas Regras 3 e 5 do servico e do treino.
    """
    chuva = round(rng.uniform(0, 90), 1)
    return {
        "temperatura_ar": round(rng.uniform(12, 38), 1),
        "precipitacao_mm": chuva,
        "umidade_solo": derivar_umidade_solo(chuva, tipo_solo),
        "velocidade_vento": round(rng.uniform(0, 45), 1),
        "condicao_clima": derivar_condicao_clima(chuva),
    }


def gerar_envios(n: int, k: int, pares: list[tuple[str, str]], cadastro: dict[str, dict]) -> list[dict]:
    """
    N leituras com leitura_id, cada uma num par equipamento x operador real.
    A cada 3 leituras, uma leva o clima no payload (clima_origem 'payload');
    as demais deixam a API buscar na Open-Meteo. A cada k, a primeira
    resposta sera descartada. A leitura vai em 'leitura': quem chama a tira
    do envio antes de gravar o relatorio.
    """
    # gerar_leitura sorteia o operador desta lista; o par real o substitui.
    simulador._OPERADORES[:] = sorted({op for _, op in pares})
    envios = []
    for i in range(1, n + 1):
        equipamento_id, operador_id = random.choice(pares)
        leitura, _ = simulador.gerar_leitura([cadastro[equipamento_id]], "normal")
        leitura["operador_id"] = operador_id
        clima_no_payload = i % 3 == 0
        if clima_no_payload:
            leitura.update(clima_de_campo(leitura["tipo_solo"]))
        # Chave gerada antes do primeiro envio e reusada no retry.
        leitura["leitura_id"] = str(uuid.uuid4())
        envios.append({
            "leitura_id": leitura["leitura_id"],
            "equipamento_id": equipamento_id,
            "operador_id": operador_id,
            "clima_no_payload": clima_no_payload,
            "descartar_primeira": i % k == 0,
            "leitura": leitura,
        })
    return envios


# --- Envio -----------------------------------------------------------------

def motivo_do_erro(r) -> str:
    """
    Motivo de uma resposta de erro, sem o valor recebido: o 422 do Pydantic
    ecoa o campo invalido em 'input', que pode ser a posicao.
    """
    try:
        detalhe = r.json().get("detail")
    except (ValueError, AttributeError):
        return f"corpo nao e o JSON de erro da API ({len(r.text)} bytes)"
    if isinstance(detalhe, list):
        return "; ".join(
            f"{'.'.join(str(p) for p in d.get('loc', []))}: {d.get('msg')}"
            for d in detalhe if isinstance(d, dict)
        )[:200]
    return str(detalhe)[:200]


def _tentativa(numero: int, r) -> dict:
    """O que o relatorio guarda de uma resposta. Sem o corpo: ele traz valores da leitura."""
    t = {"tentativa": numero, "status": r.status_code, "request_id": r.headers.get("X-Request-ID"),
         "avaliacao_id": None, "descartada": False}
    if r.status_code not in (200, 201):
        t["erro"] = motivo_do_erro(r)
        return t
    try:
        t["avaliacao_id"] = r.json()["avaliacao_id"]
    except (ValueError, KeyError, TypeError) as e:
        t["erro"] = f"resposta {r.status_code} sem avaliacao_id legivel ({type(e).__name__})"
    return t


def enviar(post, url: str, cabecalho: dict, leitura: dict, descartar_primeira: bool) -> list[dict]:
    """
    Envia pela funcao de retry do simulador, registrando cada tentativa.
    `post` tem a assinatura de requests.post. Com descartar_primeira, a
    primeira resposta de sucesso vira RespostaDescartada, que e uma
    requests.ConnectionError: para o retry, a rede caiu depois de a API gravar.
    """
    tentativas: list[dict] = []

    def post_registrado(url, **kw):
        numero = len(tentativas) + 1
        try:
            r = post(url, **kw)
        except requests.RequestException as e:
            tentativas.append({"tentativa": numero, "status": None, "request_id": None,
                               "avaliacao_id": None, "descartada": False, "erro": type(e).__name__})
            raise
        t = _tentativa(numero, r)
        tentativas.append(t)
        if descartar_primeira and numero == 1 and r.status_code in (200, 201):
            t["descartada"] = True
            raise RespostaDescartada("primeira resposta descartada (falha injetada no cliente)")
        return r

    simulador.enviar_com_retry(post_registrado, url, leitura, cabecalho, timeout=TIMEOUT_S)
    return tentativas


# --- Leitura do banco ------------------------------------------------------

def ler_pares(limite: int = 1000) -> tuple[list[tuple[str, str]], dict[str, dict]]:
    """Pares equipamento x operador que ja tem avaliacao, e o cadastro desses equipamentos."""
    try:
        cliente = repo.get_client()
        linhas = (
            cliente.table("avaliacoes").select("equipamento_id,operador_id")
            .order("avaliacao_id").limit(limite).execute().data or []
        )
        pares = {(a["equipamento_id"], a["operador_id"]) for a in linhas if a.get("operador_id")}
        if not pares:
            raise Interrompido("Banco sem avaliacoes com operador. Rode o seed antes.")
        ids = sorted({e for e, _ in pares})
        equipamentos = (
            cliente.table("equipamentos").select("equipamento_id,tipo_equipamento,tem_iot")
            .in_("equipamento_id", ids).execute().data or []
        )
    except ERROS_DO_BANCO as e:
        raise Interrompido(f"banco inacessivel ao ler os pares: {type(e).__name__}: {e}") from e
    cadastro = {e["equipamento_id"]: e for e in equipamentos}
    return sorted(p for p in pares if p[0] in cadastro), cadastro


def consultar_banco(leitura_ids: list[str]) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Avaliacoes (todas as colunas, para comparar com a leitura enviada),
    predicoes e auditoria das leituras enviadas nesta execucao.
    """
    try:
        cliente = repo.get_client()
        avaliacoes = (
            cliente.table("avaliacoes").select("*")
            .in_("leitura_id", leitura_ids).execute().data or []
        )
        ids = [a["avaliacao_id"] for a in avaliacoes]
        if not ids:
            return avaliacoes, [], []
        predicoes = (
            cliente.table("predicoes")
            .select("predicao_id,avaliacao_id,modelo_versao,timestamp_predicao")
            .in_("avaliacao_id", ids).execute().data or []
        )
        auditoria = (
            cliente.table("auditoria")
            .select("auditoria_id,timestamp,usuario,perfil,acao,status,avaliacao_id,modelo_versao")
            .in_("avaliacao_id", ids).execute().data or []
        )
    except ERROS_DO_BANCO as e:
        raise Interrompido(f"banco inacessivel ao conferir a coleta: {type(e).__name__}: {e}") from e
    return avaliacoes, predicoes, auditoria


# --- Checagens (funcoes puras, testadas em tests/test_confiabilidade_coleta.py) --

def _checagem(nome: str, ok: bool, detalhe: str) -> dict:
    return {"nome": nome, "ok": bool(ok), "detalhe": detalhe}


def _ids_respondidos(envio: dict) -> set:
    return {t["avaliacao_id"] for t in envio["tentativas"] if t["status"] in (200, 201)}


def _ids_por_status(envios: list[dict], status: int) -> Counter:
    return Counter(t["avaliacao_id"] for e in envios for t in e["tentativas"] if t["status"] == status)


def _mesmo_valor(gravado, enviado) -> bool:
    """NUMERIC volta como numero JSON; a tolerancia so absorve a representacao em float."""
    numeros = (int, float)
    if (isinstance(gravado, numeros) and isinstance(enviado, numeros)
            and not isinstance(gravado, bool) and not isinstance(enviado, bool)):
        return abs(gravado - enviado) <= 1e-9
    return gravado == enviado


def _checar_contagens(envios, avaliacoes, predicoes) -> list[dict]:
    enviados = [e["leitura_id"] for e in envios]
    por_leitura = Counter(a["leitura_id"] for a in avaliacoes)
    faltando = sorted(set(enviados) - set(por_leitura))
    duplicadas = sorted(lid for lid, n in por_leitura.items() if n > 1)
    ids = {a["avaliacao_id"] for a in avaliacoes}
    por_avaliacao = Counter(p["avaliacao_id"] for p in predicoes)
    orfas = sorted(i for i in ids if por_avaliacao[i] == 0)
    multiplas = sorted(i for i, n in por_avaliacao.items() if n > 1)
    return [
        # Sem isto, todas as checagens abaixo passariam sobre um conjunto vazio.
        _checagem("conjunto_nao_vazio", enviados and avaliacoes,
                  f"{len(enviados)} leituras enviadas, {len(avaliacoes)} avaliacoes lidas"),
        _checagem("chaves_distintas", len(set(enviados)) == len(enviados),
                  f"{len(set(enviados))} leitura_id distintos em {len(enviados)} envios"),
        _checagem("uma_avaliacao_por_leitura",
                  enviados and not faltando and not duplicadas and len(avaliacoes) == len(enviados),
                  f"faltando={faltando} duplicadas={duplicadas}"),
        _checagem("uma_predicao_por_avaliacao",
                  ids and not orfas and not multiplas and len(predicoes) == len(ids),
                  f"orfas (avaliacao sem predicao)={orfas} com mais de uma={multiplas}"),
    ]


def _checar_respostas(envios, avaliacoes) -> list[dict]:
    id_gravado = {a["leitura_id"]: a["avaliacao_id"] for a in avaliacoes}
    sem_resultado = [e["leitura_id"] for e in envios
                     if not e["tentativas"] or e["tentativas"][-1]["status"] not in (200, 201)]
    divergentes = [e["leitura_id"] for e in envios
                   if _ids_respondidos(e) != {id_gravado.get(e["leitura_id"])}]
    injetadas = [e for e in envios if any(t["descartada"] for t in e["tentativas"])]
    sem_reenvio = [e["leitura_id"] for e in injetadas if e["tentativas"][-1]["status"] != 200]
    return [
        _checagem("toda_leitura_terminou_com_resultado", envios and not sem_resultado,
                  f"sem 200/201 na ultima tentativa: {sem_resultado}"),
        _checagem("resposta_aponta_para_a_avaliacao_gravada", envios and not divergentes,
                  f"avaliacao_id da resposta diferente do gravado: {divergentes}"),
        _checagem("retry_apos_resposta_perdida_e_reenvio",
                  injetadas and not sem_reenvio,
                  f"{len(injetadas)} respostas descartadas; sem 200 no reenvio: {sem_reenvio}"),
    ]


def _checar_auditoria(envios, avaliacoes, predicoes, auditoria, usuario: str) -> list[dict]:
    """
    Toda avaliacao tem um 'sucesso' ou, se a resposta do banco se perdeu
    depois do commit, um 'reenvio' com o seu avaliacao_id. Cada 201 audita
    um 'sucesso' e cada 200 um 'reenvio'.
    """
    ids = [a["avaliacao_id"] for a in avaliacoes]
    sucessos = Counter(x["avaliacao_id"] for x in auditoria if x["status"] == "sucesso")
    reenvios = Counter(x["avaliacao_id"] for x in auditoria if x["status"] == "reenvio")
    sem_trilha = sorted(i for i in ids if not (sucessos[i] == 1 or (sucessos[i] == 0 and reenvios[i] >= 1)))
    por_201, por_200 = _ids_por_status(envios, 201), _ids_por_status(envios, 200)
    da_trilha = [x for x in auditoria if x["status"] in ("sucesso", "reenvio")]
    outro_usuario = sorted({x["avaliacao_id"] for x in da_trilha
                            if x["usuario"] != usuario or not x["perfil"]})
    versao = {p["avaliacao_id"]: p["modelo_versao"] for p in predicoes}
    versao_divergente = sorted({x["avaliacao_id"] for x in da_trilha
                                if not x["modelo_versao"] or x["modelo_versao"] != versao.get(x["avaliacao_id"])})
    return [
        _checagem("auditoria_sucesso_ou_reenvio_por_avaliacao", ids and not sem_trilha,
                  f"sem exatamente um 'sucesso' e sem 'reenvio': {sem_trilha}"),
        _checagem("auditoria_bate_com_as_respostas",
                  (por_201 or por_200) and sucessos == por_201 and reenvios == por_200,
                  f"'sucesso' {dict(sucessos)} x respostas 201 {dict(por_201)}; "
                  f"'reenvio' {dict(reenvios)} x respostas 200 {dict(por_200)}"),
        _checagem("auditoria_do_usuario_autenticado", da_trilha and not outro_usuario,
                  f"{len(da_trilha)} linhas de sucesso/reenvio; de outro usuario que nao "
                  f"'{usuario}', ou sem perfil: {outro_usuario}"),
        _checagem("modelo_versao_da_predicao_na_auditoria", da_trilha and not versao_divergente,
                  f"modelo_versao da auditoria diferente do da predicao: {versao_divergente}"),
    ]


def _checar_entrada(envios, avaliacoes, leituras: dict[str, dict]) -> list[dict]:
    """A linha gravada e a leitura enviada, campo a campo. O detalhe so cita nomes de campo."""
    divergentes = []
    for a in avaliacoes:
        enviada = leituras.get(a["leitura_id"])
        if enviada is None:
            divergentes.append({"leitura_id": a["leitura_id"], "campos": ["<leitura nao enviada aqui>"]})
            continue
        campos = sorted(k for k, v in enviada.items() if not _mesmo_valor(a.get(k), v))
        if campos:
            divergentes.append({"leitura_id": a["leitura_id"], "campos": campos})
    esperada = {e["leitura_id"]: ("payload" if e["clima_no_payload"] else "open-meteo") for e in envios}
    procedencia_errada = sorted(
        a["leitura_id"] for a in avaliacoes
        if a.get("fonte") != "telemetria" or a.get("clima_origem") != esperada.get(a["leitura_id"])
    )
    return [
        _checagem("entrada_gravada_confere", avaliacoes and leituras and not divergentes,
                  f"{len(avaliacoes)} avaliacoes comparadas com a leitura enviada; divergentes: {divergentes}"),
        _checagem("procedencia_gravada", avaliacoes and not procedencia_errada,
                  f"fonte != telemetria ou clima_origem inesperado: {procedencia_errada}"),
    ]


def checar(envios: list[dict], avaliacoes: list[dict], predicoes: list[dict],
           auditoria: list[dict], *, leituras: dict[str, dict], usuario: str) -> list[dict]:
    """
    Confere a coleta. Cada checagem agregada exige conjunto nao vazio: sobre
    zero linhas, "nenhuma duplicata" seria verdade por vacuidade.

    Orfa = avaliacao sem predicao. Predicao sem avaliacao nao aparece aqui: a
    consulta parte das avaliacoes, e a chave estrangeira do banco a impede.
    `leituras` sao as leituras enviadas, por leitura_id; `usuario`, o
    autenticado, que a auditoria tem de mostrar.
    """
    return (
        _checar_contagens(envios, avaliacoes, predicoes)
        + _checar_respostas(envios, avaliacoes)
        + _checar_auditoria(envios, avaliacoes, predicoes, auditoria, usuario)
        + _checar_entrada(envios, avaliacoes, leituras)
    )


def ler_log(caminho: str) -> list[str]:
    try:
        with open(caminho, encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()
    except OSError as e:
        raise Interrompido(f"log da API ilegivel em {caminho}: {e}") from e


def _linhas_por_request_id(linhas: list[str]) -> dict[str, list[tuple[int, bool, str]]]:
    por_rid: dict[str, list[tuple[int, bool, str]]] = defaultdict(list)
    for linha in linhas:
        m = RE_LINHA_DE_LOG.search(linha)
        if m:
            por_rid[m["rid"]].append((int(m["aid"]), bool(m["reenvio"]), linha))
    return por_rid


def checar_log(linhas: list[str] | None, envios: list[dict]) -> tuple[dict, dict[str, str]]:
    """
    Cada resposta 201 e 200 tem no log exatamente uma linha do scoring com o
    seu request_id e o seu avaliacao_id: a de sucesso no 201, a de reenvio no
    200. Devolve a checagem e, por request_id, a linha que casou. `linhas`
    None = sem log: a checagem sai reprovada, nunca pulada.
    """
    nome = "log_correlacionado_por_request_id"
    if linhas is None:
        return _checagem(nome, False, SEM_LOG), {}
    por_rid = _linhas_por_request_id(linhas)
    respostas = [t for e in envios for t in e["tentativas"] if t["status"] in (200, 201)]
    casadas: dict[str, str] = {}
    sem_linha = []
    for t in respostas:
        achadas = por_rid.get(t["request_id"], [])
        if [(aid, reenvio) for aid, reenvio, _ in achadas] == [(t["avaliacao_id"], t["status"] == 200)]:
            casadas[t["request_id"]] = achadas[0][2]
        else:
            sem_linha.append(t["request_id"])
    return _checagem(nome, respostas and not sem_linha,
                     f"{len(respostas)} respostas 200/201, {len(casadas)} com a linha do seu "
                     f"avaliacao_id; sem linha ou com linha divergente: {sem_linha}"), casadas


# --- Relatorio -------------------------------------------------------------

def trilhas(envios: list[dict], avaliacoes: list[dict], predicoes: list[dict],
            auditoria: list[dict], linhas_de_log: dict[str, str] | None, quantas: int = 3) -> list[dict]:
    """
    Trilha completa de algumas avaliacoes: uma com resposta descartada, uma
    com clima do payload e uma com clima da Open-Meteo, quando houver.
    `linhas_de_log` e o que checar_log casou; None = log nao conferido.
    """
    por_leitura = {a["leitura_id"]: a for a in avaliacoes}
    criterios = (
        lambda e: any(t["descartada"] for t in e["tentativas"]),
        lambda e: e["clima_no_payload"],
        lambda e: not e["clima_no_payload"],
    )
    escolhidos: list[dict] = []
    for criterio in criterios:
        e = next((e for e in envios if criterio(e) and e not in escolhidos
                  and e["leitura_id"] in por_leitura), None)
        if e is not None:
            escolhidos.append(e)
    return [_trilha(e, por_leitura[e["leitura_id"]], predicoes, auditoria, linhas_de_log)
            for e in escolhidos[:quantas]]


def _linha_de_log(t: dict, linhas_de_log: dict[str, str] | None) -> str | None:
    if t["status"] not in (200, 201):
        return None
    if linhas_de_log is None:
        return SEM_LOG
    return linhas_de_log.get(t["request_id"], "NAO ENCONTRADA no log")


def _trilha(envio: dict, avaliacao: dict, predicoes: list[dict], auditoria: list[dict],
            linhas_de_log: dict[str, str] | None) -> dict:
    aid = avaliacao["avaliacao_id"]
    predicao = next((p for p in predicoes if p["avaliacao_id"] == aid), {})
    return {
        "leitura_id": envio["leitura_id"],
        "tentativas": [
            {**{k: t.get(k) for k in ("tentativa", "status", "request_id", "descartada")},
             "linha_de_log": _linha_de_log(t, linhas_de_log)}
            for t in envio["tentativas"]
        ],
        "avaliacao_id": aid,
        "equipamento_id": avaliacao["equipamento_id"],
        "clima_origem": avaliacao["clima_origem"],
        "timestamp_avaliacao": avaliacao["timestamp"],
        "modelo_versao": predicao.get("modelo_versao"),
        "auditoria": [
            {k: x.get(k) for k in ("status", "usuario", "perfil", "modelo_versao", "timestamp")}
            for x in auditoria if x["avaliacao_id"] == aid and x["status"] in ("sucesso", "reenvio")
        ],
    }


def resumo(envios, avaliacoes, predicoes) -> dict:
    por_leitura = Counter(a["leitura_id"] for a in avaliacoes)
    por_avaliacao = Counter(p["avaliacao_id"] for p in predicoes)
    status = Counter(
        "sem_resposta" if t["status"] is None else str(t["status"])
        for e in envios for t in e["tentativas"]
    )
    return {
        "leituras_enviadas": len(envios),
        "respostas_descartadas": sum(t["descartada"] for e in envios for t in e["tentativas"]),
        "respostas_por_status": dict(sorted(status.items())),
        "status_final": dict(sorted(Counter(
            str(e["tentativas"][-1]["status"]) for e in envios if e["tentativas"]
        ).items())),
        # {quantidade de avaliacoes: quantas leituras} -- esperado {1: N}
        "avaliacoes_por_leitura": dict(Counter(por_leitura.get(e["leitura_id"], 0) for e in envios)),
        # {quantidade de predicoes: quantas avaliacoes} -- esperado {1: N}
        "predicoes_por_avaliacao": dict(Counter(por_avaliacao[a["avaliacao_id"]] for a in avaliacoes)),
        "orfas": sorted(a["avaliacao_id"] for a in avaliacoes if por_avaliacao[a["avaliacao_id"]] == 0),
        "duplicatas": sorted(lid for lid, n in por_leitura.items() if n > 1),
    }


def _imprimir_trilha(t: dict) -> None:
    print(f"  leitura {t['leitura_id']}")
    for x in t["tentativas"]:
        print(f"    tentativa {x['tentativa']}: {x['status']}"
              f"{' (descartada)' if x['descartada'] else ''} rid={x['request_id']}")
        if x["linha_de_log"] is not None:
            print(f"      linha de log: {x['linha_de_log']}")
    print(f"    banco    : avaliacao {t['avaliacao_id']} {t['equipamento_id']} "
          f"clima_origem={t['clima_origem']} em {t['timestamp_avaliacao']}")
    print(f"    predicao : modelo_versao={t['modelo_versao']}")
    for a in t["auditoria"]:
        print(f"    auditoria: {a['status']} por {a['usuario']} ({a['perfil']}) "
              f"modelo_versao={a['modelo_versao']} em {a['timestamp']}")


def _imprimir(relatorio: dict) -> None:
    print()
    print("Resumo")
    for chave, valor in relatorio["resumo"].items():
        print(f"  {chave:<28}: {valor}")
    print()
    print("Checagens")
    for c in relatorio["checagens"]:
        print(f"  [{'OK' if c['ok'] else 'FALHOU'}] {c['nome']}: {c['detalhe']}")
    print()
    print("Trilhas (request_id -> linha de log -> avaliacao_id -> clima_origem, modelo_versao, usuario, horario)")
    for t in relatorio["trilhas"]:
        _imprimir_trilha(t)
    print()
    print("RESULTADO:", "todas as checagens passaram" if relatorio["ok"] else "HA CHECAGEM FALHANDO")


# --- Execucao --------------------------------------------------------------

def autenticar(api: str, usuario: str, token_local: bool) -> tuple[str, str, dict]:
    """(token, usuario que a auditoria deve mostrar, registro do modo para o relatorio)."""
    if token_local:
        token, _ = criar_token(PERFIL_EXIGIDO, PERFIL_EXIGIDO)
        return token, PERFIL_EXIGIDO, {
            "modo": "token-local", "usuario": PERFIL_EXIGIDO,
            "como": "criar_token('analista', 'analista') com o JWT_SECRET_KEY do .env; sem login",
        }
    # Nunca por argumento: ficaria no historico do shell e na lista de processos.
    senha = os.getenv("SAFEFIELD_SENHA") or getpass.getpass(f"Senha de {usuario}: ")
    try:
        r = requests.post(f"{api}/auth/token", json={"usuario": usuario, "senha": senha}, timeout=TIMEOUT_S)
        dados = r.json() if r.status_code == 200 else None
    except (requests.RequestException, ValueError) as e:
        raise Interrompido(f"login em {api}/auth/token falhou: {type(e).__name__}: {e}") from e
    if not isinstance(dados, dict) or not dados.get("access_token"):
        raise Interrompido(f"login de {usuario} recusado ({r.status_code}): {r.text[:200]}")
    if dados.get("perfil") != PERFIL_EXIGIDO:
        raise Interrompido(f"{usuario} tem perfil '{dados.get('perfil')}'; a coleta exige '{PERFIL_EXIGIDO}'.")
    return dados["access_token"], usuario, {"modo": "login", "usuario": usuario, "como": "POST /auth/token"}


def _conferir_api(api: str) -> None:
    try:
        r = requests.get(f"{api}/health", timeout=TIMEOUT_S)
        saude = r.json()
    except (requests.RequestException, ValueError) as e:
        raise Interrompido(f"API inacessivel ou /health ilegivel em {api}: {type(e).__name__}: {e}") from e
    if r.status_code != 200 or not isinstance(saude, dict) or saude.get("status") != "ok":
        raise Interrompido(f"API em {api} nao esta pronta: {r.status_code} {r.text[:200]}")


def executar(args) -> dict:
    if args.log_api and not os.path.isfile(args.log_api):
        raise Interrompido(f"--log-api {args.log_api} nao existe: suba a API com a saida nesse arquivo.")
    _conferir_api(args.api)
    token, usuario, autenticacao = autenticar(args.api, args.usuario, args.token_local)
    cabecalho = {"Authorization": f"Bearer {token}"}
    pares, cadastro = ler_pares()
    envios = gerar_envios(args.n, args.k, pares, cadastro)
    # Em memoria so: a leitura tem latitude e longitude e nao vai para o JSON.
    leituras = {e["leitura_id"]: e.pop("leitura") for e in envios}

    for i, envio in enumerate(envios, start=1):
        envio["tentativas"] = enviar(requests.post, f"{args.api}/avaliacoes", cabecalho,
                                     leituras[envio["leitura_id"]], envio["descartar_primeira"])
        passos = " -> ".join(
            f"{t['status'] or t.get('erro')}{' (descartada)' if t['descartada'] else ''}"
            for t in envio["tentativas"]
        )
        print(f"  [{i:>3}/{len(envios)}] {envio['equipamento_id']} {envio['operador_id']} "
              f"clima={'payload' if envio['clima_no_payload'] else 'open-meteo'}  {passos}")

    avaliacoes, predicoes, auditoria = consultar_banco(list(leituras))
    checagens = checar(envios, avaliacoes, predicoes, auditoria, leituras=leituras, usuario=usuario)
    linhas = ler_log(args.log_api) if args.log_api else None
    checagem_log, casadas = checar_log(linhas, envios)
    checagens.append(checagem_log)
    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "api": args.api,
        "autenticacao": autenticacao,
        "parametros": {"n": args.n, "k": args.k, "seed": args.seed, "log_api": args.log_api},
        "resumo": resumo(envios, avaliacoes, predicoes),
        "checagens": checagens,
        "trilhas": trilhas(envios, avaliacoes, predicoes, auditoria, casadas if linhas is not None else None),
        "envios": envios,
        "ok": all(c["ok"] for c in checagens),
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Confiabilidade da coleta contra a API e o banco reais (S4-28).",
        epilog="Detalhes no docstring do arquivo.",
    )
    p.add_argument("--api", default="http://127.0.0.1:8000", help="URL da API ja de pe")
    p.add_argument("--n", type=int, default=20, help="leituras enviadas (default 20)")
    p.add_argument("--k", type=int, default=4,
                   help="descarta a primeira resposta de 1 a cada k leituras (default 4)")
    p.add_argument("--seed", type=int, default=None, help="semente do gerador de leituras")
    p.add_argument("--saida", default=None, help="arquivo JSON do relatorio")
    p.add_argument("--log-api", default=None,
                   help="arquivo com o log da API; sem ele a checagem do log sai reprovada")
    p.add_argument("--usuario", default=os.getenv("SAFEFIELD_USUARIO", PERFIL_EXIGIDO),
                   help="usuario do login (perfil analista); senha em SAFEFIELD_SENHA ou no terminal")
    p.add_argument("--token-local", action="store_true",
                   help="assina o token aqui com o JWT_SECRET_KEY do .env, sem login (desenvolvimento)")
    args = p.parse_args(argv)
    if args.n < 1 or args.k < 1:
        p.error("--n e --k precisam ser >= 1")
    if args.seed is None:
        args.seed = random.randrange(2**31)
    random.seed(args.seed)

    print("=" * 62)
    print("SafeField - confiabilidade da coleta (API e banco reais)")
    print("=" * 62)
    print(f"  API: {args.api}   N={args.n}   k={args.k}   seed={args.seed}")
    print(f"  autenticacao: {'token local' if args.token_local else f'login de {args.usuario}'}"
          f"   log da API: {args.log_api or SEM_LOG}")
    try:
        relatorio = executar(args)
    except Interrompido as e:
        print(f"\nINTERROMPIDO: {e}", file=sys.stderr)
        return 2
    _imprimir(relatorio)
    if args.saida:
        with open(args.saida, "w", encoding="utf-8") as f:
            json.dump(relatorio, f, ensure_ascii=False, indent=2, default=str)
        print(f"Relatorio JSON: {args.saida}")
    return 0 if relatorio["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
