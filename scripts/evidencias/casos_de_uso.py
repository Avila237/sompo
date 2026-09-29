"""
Casos de uso roteirizados, um por persona (S4-28, R4-14), contra a API real.

Cada persona executa as chamadas da sua historia (README, secao 3) e o
roteiro imprime o que ela ve e o que lhe e negado, conferindo o status de cada
chamada contra a matriz perfil x rota de docs/contrato-api.md:

  operador: ve so o recorte. LGPD: da ultima avaliacao de outro operador nao
      recebe operador_id, latitude, longitude nem a posicao nos valores SHAP
      do detalhe; sem esse caso no recorte o passo sai reprovado ("nao
      demonstrado"), nunca pulado. Envia leitura propria (201); /alertas so
      do recorte (vazio = nao demonstrado); /kpis, /tendencias e equipamento
      fora do recorte dao 403.
  gestor: KPIs, ranking da frota e tendencias por regiao e por operacao;
      enviar leitura da 403 (e a recusa vai para a auditoria).
  tecnico: frota ordenada pelo estado de manutencao e as recomendacoes de
      manutencao; enviar leitura da 403.
  analista: detalhe com SHAP e recomendacoes da leitura que o operador acabou
      de enviar, com a identidade visivel, e a auditoria da execucao.

Grava no maximo uma avaliacao por execucao: a do operador. As recusas de
gestor e tecnico em POST /avaliacoes gravam uma linha de auditoria cada
(status 'erro'), que e a evidencia do controle de acesso. A auditoria nao tem
rota na API: o passo do analista a consulta direto no banco, so leitura,
filtrando pelo equipamento da leitura recusada e pelo instante do header Date
da primeira resposta da API; exige exatamente um 'erro' por perfil recusado.

Autenticacao:
  - padrao: login em /auth/token, um usuario por perfil. Usuario em
    SAFEFIELD_USUARIO_<PERFIL> (default: o nome do perfil, ex. 'gestor');
    senha em SAFEFIELD_SENHA_<PERFIL> ou pedida no terminal, sem eco. O
    perfil devolvido pelo login tem de ser o esperado, e o operador_id do
    perfil operador vem do login (--operador e ignorado);
  - --token-local: criar_token(<perfil>, <perfil>) com o JWT_SECRET_KEY do
    .env, que precisa ser o da API em execucao, e o operador em --operador.
    Sem login; so para desenvolvimento. O relatorio registra o modo.

Uso:
    python scripts/evidencias/casos_de_uso.py --saida /tmp/casos_de_uso.json
    python scripts/evidencias/casos_de_uso.py --token-local --operador OP-0015

Codigo de saida: 0 se todo passo conferiu, 1 se algum nao, 2 se a API ou o
banco estiverem inacessiveis, ou o login falhar.
"""

import argparse
import getpass
import json
import os
import random
import sys
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.core.security import criar_token  # noqa: E402
from backend.db import repository as repo  # noqa: E402
from scripts import simulate_telemetry as simulador  # noqa: E402
from scripts.evidencias.coleta_real import ERROS_DO_BANCO, TIMEOUT_S, motivo_do_erro  # noqa: E402

PERFIS = ("operador", "gestor", "tecnico", "analista")
# Perfis so de leitura: tentam enviar e tem de ser recusados e auditados.
RECUSADOS = ("gestor", "tecnico")
# LGPD, minimizacao: o que o operador nao recebe da avaliacao de outro operador.
CAMPOS_PESSOAIS = ("operador_id", "latitude", "longitude")
# Detalhes de equipamento mascarado conferidos, no maximo.
MAX_DETALHES = 5

HISTORIAS = {
    "operador": "Operador de equipamento: alertas diretos e objetivos para ajustar a conducao "
                "em tempo real (README 3.3).",
    "gestor": "Gestor de frota: ranking de risco por equipamento e area, e comparacao entre "
              "modos de uso, campo x transporte (README 3.3).",
    "tecnico": "Tecnico de manutencao: identificar padroes que antecedem danos, para atuar "
               "preventivamente (README 3.3).",
    "analista": "Sompo, subscricao e corretor: score explicavel, fatores de risco, acoes "
                "preventivas e trilha de auditoria (README 3.1 e 3.3).",
}


class Interrompido(Exception):
    """API ou banco inacessivel, ou login recusado: nao ha caso de uso para rodar (saida 2)."""


class Roteiro:
    def __init__(self, api: str, tokens: dict[str, str], usuarios: dict[str, str], operador_id: str):
        self.api = api
        self.tokens = tokens
        self.usuarios = usuarios
        self.operador_id = operador_id

    def _cabecalho(self, perfil: str) -> dict:
        return {"Authorization": f"Bearer {self.tokens[perfil]}"}

    def chamar(self, perfil: str, metodo: str, rota: str, esperado: int, **kw) -> tuple[dict, object]:
        try:
            r = requests.request(metodo, f"{self.api}{rota}", timeout=TIMEOUT_S,
                                 headers=self._cabecalho(perfil), **kw)
        except requests.RequestException as e:
            raise Interrompido(f"{metodo} {rota} sem resposta: {type(e).__name__}: {e}") from e
        return _passo(r, f"{metodo} {rota}", esperado)

    def postar_leitura(self, perfil: str, leitura: dict, esperado: int) -> tuple[dict, object]:
        """Pela funcao de retry do simulador: mesma chave, repete 502, 503 e falha de rede."""
        tentativas = []

        def post(url, **kw):
            tentativas.append(url)
            return requests.post(url, **kw)

        r = simulador.enviar_com_retry(post, f"{self.api}/avaliacoes", leitura,
                                       self._cabecalho(perfil), timeout=TIMEOUT_S)
        if r is None:
            raise Interrompido(f"POST /avaliacoes sem resposta em {len(tentativas)} tentativas")
        passo, corpo = _passo(r, "POST /avaliacoes", esperado)
        passo["tentativas"] = len(tentativas)
        return passo, corpo


def _passo(r, chamada: str, esperado: int) -> tuple[dict, object]:
    passo = {"chamada": chamada, "esperado": esperado, "obtido": r.status_code,
             "ok": r.status_code == esperado, "request_id": r.headers.get("X-Request-ID")}
    try:
        corpo = r.json()
    except ValueError:
        corpo = None
        passo["ok"] = False
    if not passo["ok"]:
        # Sem o valor recebido: o 422 ecoa o campo invalido, que pode ser a posicao.
        passo["detalhe"] = motivo_do_erro(r)
    return passo, corpo


def _inspecao(descricao: str, ok: bool, visto: str) -> dict:
    """Passo que confere uma resposta ja recebida ou o banco, sem chamada nova a API."""
    return {"chamada": descricao, "esperado": None, "obtido": None, "ok": bool(ok),
            "request_id": None, "visto": visto}


def _caso(perfil: str, titulo: str) -> dict:
    return {"perfil": perfil, "persona": titulo, "historia": HISTORIAS[perfil], "passos": []}


def _leitura_para(equipamento: dict, operador_id: str) -> dict:
    """Leitura do gerador do simulador para um equipamento do recorte, com chave propria."""
    simulador._OPERADORES[:] = [operador_id]
    leitura, _ = simulador.gerar_leitura([equipamento], "normal")
    leitura["operador_id"] = operador_id
    leitura["leitura_id"] = str(uuid.uuid4())
    return leitura


def _recomendacoes(corpo: dict, publico: str) -> list[str]:
    return [f"{r['acao']} ({r['criterio']})" for r in corpo.get("recomendacoes", [])
            if r["publico"] == publico]


# --- Conferencias (funcoes puras, testadas em tests/test_confiabilidade_coleta.py) --

def de_outro_operador(itens: list[dict], operador_id: str) -> list[str]:
    """Equipamentos do recorte cuja ultima avaliacao nao e do proprio operador (mascarada ou nao)."""
    return [e["equipamento_id"] for e in itens
            if (e.get("total_avaliacoes") or 0) > 0 and e.get("operador_id") != operador_id]


def vazamentos_no_detalhe(detalhe: dict) -> tuple[list[str], int]:
    """
    (o que vazou, quantos fatores de posicao ha no top SHAP) do detalhe de um
    equipamento mascarado, visto pelo operador. Detalhe sem ultima_avaliacao
    nao demonstra nada e conta como problema.
    """
    ultima = detalhe.get("ultima_avaliacao")
    if not ultima:
        return ["ultima_avaliacao ausente"], 0
    vazou = [c for c in CAMPOS_PESSOAIS if ultima.get(c) is not None]
    fatores = [f for f in ((detalhe.get("predicao") or {}).get("top_fatores_shap") or [])
               if f.get("feature") in CAMPOS_PESSOAIS]
    vazou += [f"shap:{f['feature']}" for f in fatores if f.get("valor") is not None]
    return vazou, len(fatores)


def conferir_lgpd(itens: list[dict], detalhes: dict[str, dict], operador_id: str) -> dict:
    """
    OK so com pelo menos um equipamento de outro operador no recorte, o
    detalhe de pelo menos um deles conferido, e nenhum vazamento na lista nem
    nos detalhes. Sem caso mascaravel: reprovado como 'nao demonstrado'.
    """
    descricao = "LGPD: ultima avaliacao de outro operador, na lista e no detalhe"
    alheios = de_outro_operador(itens, operador_id)
    if not alheios:
        return _inspecao(descricao, False,
                         "nao demonstrado: nenhum equipamento do recorte tem a ultima avaliacao de "
                         "outro operador, entao a mascara nao foi exercitada")
    por_id = {e["equipamento_id"]: e for e in itens}
    problemas = [f"lista {eq}: {c}" for eq in alheios for c in CAMPOS_PESSOAIS
                 if por_id[eq].get(c) is not None]
    fatores_de_posicao = 0
    for eq, detalhe in detalhes.items():
        vazou, n = vazamentos_no_detalhe(detalhe or {})
        fatores_de_posicao += n
        problemas += [f"detalhe {eq}: {c}" for c in vazou]
    ok = bool(detalhes) and not problemas
    visto = (f"{len(alheios)} equipamentos com a ultima avaliacao de outro operador; detalhe "
             f"conferido em {len(detalhes)}; fatores de posicao no top SHAP: {fatores_de_posicao}; "
             f"vazamentos: {problemas or 'nenhum'}")
    if not detalhes:
        visto += " (nenhum detalhe conferido: nao demonstrado)"
    return _inspecao(descricao, ok, visto)


def conferir_alertas(passo: dict, alertas, recorte: set[str]) -> dict:
    """Alertas so do recorte. Lista vazia nao demonstra o recorte: reprovado."""
    itens = alertas.get("itens", []) if isinstance(alertas, dict) else []
    fora = [a["equipamento_id"] for a in itens if a["equipamento_id"] not in recorte]
    if not itens:
        passo["ok"] = False
        passo["visto"] = "nao demonstrado: /alertas vazio para o recorte"
        return passo
    passo["ok"] = passo["ok"] and not fora
    passo["visto"] = f"{len(itens)} alertas; fora do recorte: {fora}"
    return passo


def conferir_auditoria(sucessos: list[dict], recusas: list[dict], usuarios: dict[str, str],
                       avaliacao_id) -> tuple[bool, str]:
    """
    Um 'sucesso' do operador para a avaliacao gravada, com modelo_versao, e
    exatamente um 'erro' por perfil recusado, com o motivo de perfil.
    """
    do_operador = [x for x in sucessos if x["status"] == "sucesso"
                   and x["usuario"] == usuarios["operador"] and x["modelo_versao"]]
    por_perfil = {
        p: sum(1 for x in recusas if x["usuario"] == usuarios[p] and x["perfil"] == p
               and x["status"] == "erro" and f"Perfil '{p}'" in (x.get("detalhe") or ""))
        for p in RECUSADOS
    }
    ok = avaliacao_id is not None and len(do_operador) == 1 and all(n == 1 for n in por_perfil.values())
    visto = (f"avaliacao {avaliacao_id}: {len(do_operador)} 'sucesso' de {usuarios['operador']} com "
             f"modelo_versao; 'erro' por perfil recusado (exige 1 cada): {por_perfil}")
    return ok, visto


def instante_do_servidor(r) -> datetime | None:
    """Header Date da resposta (relogio do servidor da API), ou None se faltar ou nao ler."""
    try:
        return parsedate_to_datetime(r.headers["Date"]).astimezone(timezone.utc)
    except (KeyError, TypeError, ValueError):
        return None


# --- Personas ----------------------------------------------------------------

def _lgpd_do_operador(rt: Roteiro, itens: list[dict], estado: dict, passos: list[dict]) -> None:
    detalhes: dict[str, dict] = {}
    for eq in de_outro_operador(itens, rt.operador_id)[:MAX_DETALHES]:
        p, detalhe = rt.chamar("operador", "GET", f"/equipamentos/{eq}", 200)
        if p["ok"] and isinstance(detalhe, dict):
            detalhes[eq] = detalhe
            ultima = detalhe.get("ultima_avaliacao") or {}
            p["visto"] = (f"ultima avaliacao {ultima.get('avaliacao_id')}: operador_id="
                          f"{ultima.get('operador_id')}, latitude e longitude "
                          f"{'null' if ultima.get('latitude') is None and ultima.get('longitude') is None else 'PRESENTES'}")
            estado.setdefault("mascarado", eq)
        passos.append(p)
    passos.append(conferir_lgpd(itens, detalhes, rt.operador_id))


def caso_operador(rt: Roteiro, frota: list[dict], estado: dict) -> dict:
    caso = _caso("operador", f"Operador ({rt.operador_id}, usuario {rt.usuarios['operador']})")
    passos = caso["passos"]

    p, lista = rt.chamar("operador", "GET", "/equipamentos", 200)
    itens = lista["itens"] if isinstance(lista, dict) else []
    recorte = {e["equipamento_id"] for e in itens}
    p["ok"] = p["ok"] and 0 < len(itens) < len(frota)
    p["visto"] = f"{len(itens)} equipamentos no recorte (a frota tem {len(frota)}): {sorted(recorte)}"
    passos.append(p)

    _lgpd_do_operador(rt, itens, estado, passos)

    proprios = [e for e in itens if e["operador_id"] == rt.operador_id] or itens
    if proprios:
        alvo = proprios[0]
        p, corpo = rt.postar_leitura("operador", _leitura_para(alvo, rt.operador_id), 201)
        if p["ok"]:
            estado.update(alvo=alvo["equipamento_id"], avaliacao_id=corpo["avaliacao_id"])
            p["visto"] = (f"avaliacao {corpo['avaliacao_id']} em {alvo['equipamento_id']}: score "
                          f"{corpo['risco_score']} ({corpo['faixa_risco']}), clima_origem="
                          f"{corpo['clima_origem']}; para o operador: "
                          f"{_recomendacoes(corpo, 'operador') or 'nenhuma recomendacao'}")
        passos.append(p)

    p, alertas = rt.chamar("operador", "GET", "/alertas", 200)
    passos.append(conferir_alertas(p, alertas, recorte))

    for rota in ("/kpis", "/tendencias?eixo=regiao"):
        p, corpo = rt.chamar("operador", "GET", rota, 403)
        p["visto"] = f"negado: {(corpo or {}).get('detail')}"
        passos.append(p)

    alheio = next((e["equipamento_id"] for e in frota if e["equipamento_id"] not in recorte), None)
    if alheio:
        p, corpo = rt.chamar("operador", "GET", f"/equipamentos/{alheio}", 403)
        p["visto"] = f"negado: {(corpo or {}).get('detail')}"
        passos.append(p)
    return caso


def _post_negado(rt: Roteiro, perfil: str, estado: dict) -> dict:
    """Perfil so de leitura tentando enviar: 403 antes de qualquer gravacao, e auditado."""
    leitura = dict(estado["leitura_modelo"], leitura_id=str(uuid.uuid4()))
    p, corpo = rt.chamar(perfil, "POST", "/avaliacoes", 403, json=leitura)
    p["visto"] = (f"negado em {leitura['equipamento_id']} (auditado com status 'erro'): "
                  f"{(corpo or {}).get('detail')}")
    return p


def caso_gestor(rt: Roteiro, estado: dict) -> dict:
    caso = _caso("gestor", f"Gestor de frota (usuario {rt.usuarios['gestor']})")
    passos = caso["passos"]

    p, corpo = rt.chamar("gestor", "GET", "/kpis", 200)
    if p["ok"]:
        k = corpo["kpis"]
        por_op = ", ".join(f"{o['tipo_operacao']} {o['score_medio']}" for o in corpo["por_operacao"])
        p["visto"] = (f"{k['total_equipamentos']} equipamentos, {k['total_avaliacoes']} avaliacoes, "
                      f"{k['pct_risco_alto']}% em risco alto; score medio por operacao: {por_op}")
    passos.append(p)

    p, corpo = rt.chamar("gestor", "GET", "/equipamentos", 200)
    if p["ok"]:
        top = corpo["itens"][:5]
        p["visto"] = "ranking: " + ", ".join(
            f"{e['equipamento_id']} {e['risco_score']} ({e['faixa_risco']})" for e in top)
    passos.append(p)

    for eixo in ("regiao", "operacao"):
        p, corpo = rt.chamar("gestor", "GET", f"/tendencias?eixo={eixo}&limite=3", 200)
        if p["ok"]:
            p["visto"] = f"{eixo}, janela {corpo['janela']['inicio']} a {corpo['janela']['fim']}: " + \
                ", ".join(f"{s['chave']} {s['score_medio']}" for s in corpo["series"])
        passos.append(p)

    passos.append(_post_negado(rt, "gestor", estado))
    return caso


def caso_tecnico(rt: Roteiro, estado: dict) -> dict:
    caso = _caso("tecnico", f"Tecnico de manutencao (usuario {rt.usuarios['tecnico']})")
    passos = caso["passos"]

    p, corpo = rt.chamar("tecnico", "GET", "/equipamentos", 200)
    pior = None
    if p["ok"]:
        itens = sorted(
            (e for e in corpo["itens"] if e["total_avaliacoes"] > 0),
            key=lambda e: (bool(e["manutencao_atrasada"]), e["atraso_manutencao_pct"] or 0),
            reverse=True,
        )
        atrasados = sum(1 for e in itens if e["manutencao_atrasada"])
        pior = itens[0]["equipamento_id"] if itens else None
        p["visto"] = f"{atrasados} com manutencao atrasada; os mais atrasados: " + ", ".join(
            f"{e['equipamento_id']} atraso {e['atraso_manutencao_pct']} "
            f"({e['ultima_manutencao_dias']} dias)" for e in itens[:5])
    passos.append(p)

    if pior:
        p, corpo = rt.chamar("tecnico", "GET", f"/equipamentos/{pior}", 200)
        if p["ok"]:
            p["visto"] = (f"{pior}: historico de {len(corpo['historico'])} avaliacoes; para o "
                          f"tecnico: {_recomendacoes(corpo, 'tecnico') or 'nenhuma recomendacao'}")
        passos.append(p)

    passos.append(_post_negado(rt, "tecnico", estado))
    return caso


def _auditoria_da_execucao(rt: Roteiro, estado: dict, inicio: datetime | None) -> dict:
    """A trilha no banco: o sucesso do operador e as recusas de gestor e tecnico desta execucao."""
    descricao = "auditoria no banco (somente leitura; a API nao tem rota de auditoria)"
    if inicio is None:
        return _inspecao(descricao, False, "sem header Date na primeira resposta da API: "
                                           "janela das recusas indefinida, auditoria nao conferida")
    colunas = "timestamp,usuario,perfil,acao,status,equipamento_id,avaliacao_id,modelo_versao,detalhe"
    # Formato com Z: o '+00:00' iria como espaco na query string.
    desde = inicio.strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        cliente = repo.get_client()
        sucessos = (cliente.table("auditoria").select(colunas)
                    .eq("avaliacao_id", estado["avaliacao_id"]).execute().data or []
                    if "avaliacao_id" in estado else [])
        recusas = (cliente.table("auditoria").select(colunas)
                   .eq("equipamento_id", estado["leitura_modelo"]["equipamento_id"])
                   .eq("status", "erro")
                   .in_("usuario", [rt.usuarios[p] for p in RECUSADOS])
                   .gte("timestamp", desde).execute().data or [])
    except ERROS_DO_BANCO as e:
        raise Interrompido(f"banco inacessivel ao ler a auditoria: {type(e).__name__}: {e}") from e
    ok, visto = conferir_auditoria(sucessos, recusas, rt.usuarios, estado.get("avaliacao_id"))
    return _inspecao(descricao, ok, f"desde {desde} (Date da primeira resposta), equipamento "
                                    f"{estado['leitura_modelo']['equipamento_id']}: {visto}")


def caso_analista(rt: Roteiro, estado: dict, inicio: datetime | None) -> dict:
    caso = _caso("analista", f"Analista Sompo (usuario {rt.usuarios['analista']})")
    passos = caso["passos"]

    if "alvo" in estado:
        p, corpo = rt.chamar("analista", "GET", f"/equipamentos/{estado['alvo']}", 200)
        if p["ok"]:
            ultima, predicao = corpo["ultima_avaliacao"], corpo["predicao"] or {}
            p["ok"] = (ultima["avaliacao_id"] == estado["avaliacao_id"]
                       and ultima["operador_id"] == rt.operador_id and bool(predicao))
            fatores = ", ".join(f"{f['feature']} {f['shap_value']:+.2f} ({f['grupo']})"
                                for f in predicao.get("top_fatores_shap", [])[:3])
            p["visto"] = (f"avaliacao {ultima['avaliacao_id']} de {ultima['operador_id']}, "
                          f"modelo {predicao.get('modelo_versao')}; SHAP: {fatores}; grupos: "
                          f"{predicao.get('contribuicoes_por_grupo')}; recomendacoes: "
                          + ", ".join(f"{r['publico']}: {r['acao']}" for r in corpo["recomendacoes"]))
        passos.append(p)
    passos.append(_auditoria_da_execucao(rt, estado, inicio))

    if "mascarado" in estado:
        p, corpo = rt.chamar("analista", "GET", f"/equipamentos/{estado['mascarado']}", 200)
        if p["ok"]:
            ultima = corpo["ultima_avaliacao"] or {}
            # A mascara so tem sentido se a avaliacao e mesmo de outro operador.
            p["ok"] = ultima.get("operador_id") not in (None, rt.operador_id)
            p["visto"] = (f"o mesmo equipamento que o operador viu mascarado: operador_id="
                          f"{ultima.get('operador_id')} (visivel para o analista)")
        passos.append(p)

    p, corpo = rt.chamar("analista", "GET", "/kpis", 200)
    if p["ok"]:
        p["visto"] = f"frota inteira: {corpo['kpis']['total_avaliacoes']} avaliacoes"
    passos.append(p)
    return caso


# --- Execucao ----------------------------------------------------------------

def _login(api: str, usuario: str, senha: str) -> dict:
    try:
        r = requests.post(f"{api}/auth/token", json={"usuario": usuario, "senha": senha}, timeout=TIMEOUT_S)
        dados = r.json() if r.status_code == 200 else None
    except (requests.RequestException, ValueError) as e:
        raise Interrompido(f"login de {usuario} falhou: {type(e).__name__}: {e}") from e
    if not isinstance(dados, dict) or not dados.get("access_token"):
        raise Interrompido(f"login de {usuario} recusado ({r.status_code}): {r.text[:200]}")
    return dados


def autenticar(api: str, token_local: bool, operador_id: str) -> tuple[dict, dict, str, dict]:
    """(tokens por perfil, usuarios por perfil, operador_id do perfil operador, registro do modo)."""
    if token_local:
        tokens = {p: criar_token(p, p, operador_id if p == "operador" else None)[0] for p in PERFIS}
        return tokens, {p: p for p in PERFIS}, operador_id, {
            "modo": "token-local", "usuarios": {p: p for p in PERFIS},
            "como": "criar_token(<perfil>, <perfil>) com o JWT_SECRET_KEY do .env; sem login",
        }
    tokens, usuarios, do_login = {}, {}, None
    for perfil in PERFIS:
        usuario = os.getenv(f"SAFEFIELD_USUARIO_{perfil.upper()}", perfil)
        # Nunca por argumento: ficaria no historico do shell e na lista de processos.
        senha = (os.getenv(f"SAFEFIELD_SENHA_{perfil.upper()}")
                 or getpass.getpass(f"Senha de {usuario} ({perfil}): "))
        dados = _login(api, usuario, senha)
        if dados.get("perfil") != perfil:
            raise Interrompido(f"{usuario} tem perfil '{dados.get('perfil')}', esperado '{perfil}'.")
        tokens[perfil], usuarios[perfil] = dados["access_token"], usuario
        if perfil == "operador":
            do_login = dados.get("operador_id")
    if not do_login:
        raise Interrompido("o login do operador nao trouxe operador_id")
    return tokens, usuarios, do_login, {"modo": "login", "usuarios": usuarios, "como": "POST /auth/token"}


def executar(api: str, token_local: bool, operador_id: str) -> dict:
    try:
        saude = requests.get(f"{api}/health", timeout=TIMEOUT_S)
        corpo = saude.json()
    except (requests.RequestException, ValueError) as e:
        raise Interrompido(f"API inacessivel ou /health ilegivel em {api}: {type(e).__name__}: {e}") from e
    if saude.status_code != 200 or not isinstance(corpo, dict) or corpo.get("status") != "ok":
        raise Interrompido(f"API em {api} nao esta pronta: {saude.status_code} {saude.text[:200]}")
    # Relogio do servidor, nao o local: a janela das recusas na auditoria parte daqui.
    inicio = instante_do_servidor(saude)

    tokens, usuarios, operador_id, autenticacao = autenticar(api, token_local, operador_id)
    rt = Roteiro(api, tokens, usuarios, operador_id)
    p, lista = rt.chamar("analista", "GET", "/equipamentos", 200)
    if not p["ok"] or not isinstance(lista, dict) or not lista.get("itens"):
        raise Interrompido(f"GET /equipamentos como analista deu {p['obtido']}: {p.get('detalhe')}")
    frota = lista["itens"]
    # Payload valido para as recusas de gestor e tecnico (403 antes de qualquer gravacao).
    estado: dict = {"leitura_modelo": _leitura_para(frota[0], operador_id)}

    personas = [caso_operador(rt, frota, estado), caso_gestor(rt, estado), caso_tecnico(rt, estado),
                caso_analista(rt, estado, inicio)]
    return {
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "inicio_no_servidor": inicio.isoformat() if inicio else None,
        "api": api,
        "autenticacao": autenticacao,
        "operador_id": operador_id,
        "avaliacao_gravada": estado.get("avaliacao_id"),
        "personas": personas,
        "ok": all(passo["ok"] for c in personas for passo in c["passos"]),
    }


def _imprimir(relatorio: dict) -> None:
    for caso in relatorio["personas"]:
        print()
        print(f"== {caso['persona']} (perfil {caso['perfil']}) ==")
        print(f"   {caso['historia']}")
        for p in caso["passos"]:
            marca = "OK" if p["ok"] else "FALHOU"
            status = "" if p["esperado"] is None else f" -> {p['obtido']} (esperado {p['esperado']})"
            rid = f"  rid={p['request_id']}" if p["request_id"] else ""
            print(f"   [{marca}] {p['chamada']}{status}{rid}")
            if p.get("visto"):
                print(f"        {p['visto']}")
            if p.get("detalhe") and not p["ok"]:
                print(f"        detalhe: {p['detalhe']}")
    print()
    print(f"Autenticacao: {relatorio['autenticacao']['modo']} {relatorio['autenticacao']['usuarios']}")
    print(f"Avaliacao gravada nesta execucao: {relatorio['avaliacao_gravada']}")
    print("RESULTADO:", "todos os casos de uso conferem" if relatorio["ok"] else "HA PASSO FALHANDO")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Casos de uso por persona contra a API real (S4-28).",
        epilog="Detalhes no docstring do arquivo.",
    )
    p.add_argument("--api", default="http://127.0.0.1:8000", help="URL da API ja de pe")
    p.add_argument("--operador", default="OP-0015",
                   help="operador_id do perfil operador; so com --token-local (no login vem do usuario)")
    p.add_argument("--token-local", action="store_true",
                   help="assina os tokens aqui com o JWT_SECRET_KEY do .env, sem login (desenvolvimento)")
    p.add_argument("--seed", type=int, default=None, help="semente do gerador de leituras")
    p.add_argument("--saida", default=None, help="arquivo JSON do relatorio")
    args = p.parse_args(argv)
    random.seed(args.seed)

    print("=" * 62)
    print("SafeField - casos de uso por persona (API real)")
    print("=" * 62)
    print(f"  API: {args.api}   autenticacao: {'token local' if args.token_local else 'login por perfil'}")
    try:
        relatorio = executar(args.api, args.token_local, args.operador)
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
