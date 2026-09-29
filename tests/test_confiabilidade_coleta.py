"""
Confiabilidade da coleta (S4-28, R4-07): N leituras enviadas com falhas
injetadas chegam ao banco exatamente uma vez, cada uma com a sua predicao,
com trilha de auditoria e log correlacionado pelo request_id.

Offline, roda na CI. Reais: a API, o scoring, o modelo, a auditoria, o
cliente da Open-Meteo (clima.buscar), o handler de log de producao
(backend.core.logging.configurar, com o stdout trocado por um buffer), a
funcao de envio com retry do simulador (simulate_telemetry.enviar_com_retry)
e o envio e as checagens do script de evidencia (scripts/evidencias/coleta_real.py).
Falsos: o repositorio e a resposta HTTP da Open-Meteo.

O repositorio falso imita a semantica da funcao SQL registrar_avaliacao()
(supabase/migrations/20260928120000_sprint04_integridade.sql): avaliacao e
predicao juntas ou nada, UNIQUE em leitura_id, mesmo leitura_id com o mesmo
payload_hash e reenvio, com outro e conflito. No retry sequencial quem
deduplica e o pre-check do scoring (buscar_por_leitura antes de qualquer
trabalho); o ramo de reenvio do registrar_avaliacao falso so e alcancado na
corrida, em que o pre-check nao ve a linha, injetada no retry de duas
leituras. O falso nao prova a atomicidade do Postgres (a funcao SQL foi
testada contra o banco real na S4-13); prova que a API em volta dela nao
perde nem duplica leitura quando o cliente repete o envio, e que cada
avaliacao e rastreavel.

Falhas injetadas no primeiro envio, deterministicas pelo indice da leitura:
  - clima: a Open-Meteo nao responde; 502 e nada gravado; o retry grava (201);
  - banco: a conexao cai antes do commit; 503 e nada gravado; o retry grava;
  - banco_pos_commit: o banco grava, mas a resposta dele se perde (a API ve
    erro de transporte e responde 503); o retry cai no reenvio (200);
  - postgres_fora: PostgREST de pe e Postgres fora, da gravacao ate o fim
    da requisicao (APIError PGRST000, inclusive na auditoria); 503; o retry
    grava (201);
  - resposta_perdida: a API grava e responde 201, mas o cliente descarta a
    resposta (a rede caiu na volta) e reenvia com a mesma chave (200).

Invariante de auditoria: toda avaliacao tem um 'sucesso' OU um 'reenvio' com
o seu avaliacao_id. No banco_pos_commit nao ha 'sucesso': a API nunca soube
que a gravacao deu certo, auditou 'erro' e so o reenvio registra a avaliacao.
"""

import io
import json
import logging
import os
import random
import re
import sys
import uuid
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest
import requests
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.api.main import app  # noqa: E402
from backend.core import config  # noqa: E402
from backend.core.exceptions import LeituraReutilizada  # noqa: E402
from backend.core.logging import configurar, request_id_atual  # noqa: E402
from backend.core.security import criar_token  # noqa: E402
from backend.db import repository  # noqa: E402
from backend.services.scoring import CAMPOS_CLIMA  # noqa: E402
from scripts import simulate_telemetry as simulador  # noqa: E402
from scripts.evidencias import casos_de_uso, coleta_real  # noqa: E402
from tests.conftest import SENHAS  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)

N_LEITURAS = 24
USUARIO = "analista"
API_FALSA = "http://api.teste"
URL_AVALIACOES = f"{API_FALSA}/avaliacoes"

# Falha injetada no primeiro envio da leitura i, por i % 8: tres de cada tipo
# em 24 leituras. Clima no payload quando i % 4 == 2, e nunca nas leituras com
# falha de clima (com o clima completo a Open-Meteo nem e consultada).
FALHA_POR_RESTO = {0: "clima", 1: "banco_pos_commit", 3: "banco", 5: "resposta_perdida", 6: "postgres_fora"}
DO_SERVIDOR = {"clima", "banco", "banco_pos_commit", "postgres_fora"}
# Leituras em que o pre-check do retry nao ve a linha ja gravada (corrida).
CORRIDA_NO_RETRY = {1, 5}
STATUS_ESPERADOS = {
    None: [201],
    "clima": [502, 201],
    "banco": [503, 201],
    "banco_pos_commit": [503, 200],
    "postgres_fora": [503, 201],
    "resposta_perdida": [201, 200],
}

CADASTRO = {
    "EQ-0001": {"tipo_equipamento": "trator", "tem_iot": True, "idade_equipamento": 5,
                "historico_sinistros": 2, "intervalo_manut_recomendado_dias": 180,
                "intervalo_manut_recomendado_horas": 500},
    "EQ-0002": {"tipo_equipamento": "colheitadeira", "tem_iot": False, "idade_equipamento": 12,
                "historico_sinistros": 4, "intervalo_manut_recomendado_dias": 120,
                "intervalo_manut_recomendado_horas": 400},
    "EQ-0003": {"tipo_equipamento": "implemento", "tem_iot": True, "idade_equipamento": 3,
                "historico_sinistros": 0, "intervalo_manut_recomendado_dias": 300,
                "intervalo_manut_recomendado_horas": 800},
    "EQ-0004": {"tipo_equipamento": "trator", "tem_iot": True, "idade_equipamento": 18,
                "historico_sinistros": 6, "intervalo_manut_recomendado_dias": 200,
                "intervalo_manut_recomendado_horas": 600},
}
for _id, _eq in CADASTRO.items():
    _eq.update({"equipamento_id": _id, "modelo_equipamento": f"Modelo {_id}",
                "categoria_manual": f"{_eq['tipo_equipamento']}_operacao"})
OPERADORES = ("OP-0001", "OP-0002", "OP-0015")

# O que o PostgREST devolve com o Postgres fora (grupo 0 dos codigos dele).
ERRO_SEM_POSTGRES = {"code": "PGRST000", "message": "Database connection error. Retrying the connection.",
                     "details": "connection refused (falha injetada)", "hint": None}

# Linha do formatter de producao: "<asctime> <LEVEL> [<request_id>] <logger>: <mensagem>"
RE_LINHA_FORMATADA = re.compile(
    r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d (?P<nivel>[A-Z]+)\s+\[(?P<rid>[0-9a-f]{12})\] "
    r"(?P<logger>safefield(?:\.\w+)*): (?P<msg>.*)$"
)


# --- Dubles ------------------------------------------------------------------

class Injetor:
    """
    Falha armada antes de um envio e consumida no ponto onde acontece
    (Open-Meteo, banco, pre-check). Falha armada que nao disparou e erro do
    plano do teste, nunca sucesso silencioso.
    """

    def __init__(self):
        self.armada: str | None = None
        self.disparadas: Counter = Counter()

    def armar(self, tipo: str) -> None:
        assert self.armada is None, f"falha '{self.armada}' ainda armada"
        self.armada = tipo

    def disparar(self, tipo: str) -> bool:
        if self.armada != tipo:
            return False
        self.armada = None
        self.disparadas[tipo] += 1
        return True

    def conferir(self) -> None:
        armada, self.armada = self.armada, None
        assert armada is None, f"falha '{armada}' armada e nao disparada: o plano nao exercitou o que diz"


class RepositorioFalso:
    """
    Banco em memoria com a semantica de registrar_avaliacao() e da auditoria.
    A deduplicacao do retry sequencial nao e dele: e do pre-check do scoring.
    O ramo de reenvio do registrar_avaliacao daqui so roda na corrida.
    """

    def __init__(self, injetor: Injetor):
        self.injetor = injetor
        self.avaliacoes: dict[int, dict] = {}
        self.predicoes: list[dict] = []
        self.auditoria: list[dict] = []
        # avaliacao_id -> request_id da requisicao que a gravou (so o teste le)
        self.gravada_por: dict[int, str] = {}
        self.reenvios_na_gravacao = 0
        self._postgres_fora_em: str | None = None
        self._proximo_id = 1001

    def _postgres(self) -> None:
        """Postgres fora da chamada em que a falha disparou ate o fim daquela requisicao."""
        if self._postgres_fora_em is not None and request_id_atual() == self._postgres_fora_em:
            raise APIError(dict(ERRO_SEM_POSTGRES))

    def _achar(self, leitura_id: str | None) -> dict | None:
        for a in self.avaliacoes.values():
            if leitura_id and a.get("leitura_id") == leitura_id:
                return {"avaliacao_id": a["avaliacao_id"], "payload_hash": a["payload_hash"]}
        return None

    # cadastro
    def buscar_equipamento(self, equipamento_id: str) -> dict | None:
        self._postgres()
        return deepcopy(CADASTRO.get(equipamento_id))

    def operador_existe(self, operador_id: str) -> bool:
        self._postgres()
        return operador_id in OPERADORES

    # ingestao
    def buscar_por_leitura(self, leitura_id: str) -> dict | None:
        self._postgres()
        if self.injetor.disparar("corrida"):
            # A linha ja existe, mas o pre-check nao a ve: a gravacao decide.
            return None
        return self._achar(leitura_id)

    def registrar_avaliacao(self, avaliacao: dict, predicao: dict) -> tuple[int, bool]:
        if self.injetor.disparar("postgres_fora"):
            self._postgres_fora_em = request_id_atual()
        self._postgres()
        # Mesma ordem da funcao SQL: chave repetida decide antes de inserir.
        anterior = self._achar(avaliacao.get("leitura_id"))
        if anterior is not None:
            if anterior["payload_hash"] != avaliacao.get("payload_hash"):
                raise LeituraReutilizada(avaliacao.get("leitura_id"))
            self.reenvios_na_gravacao += 1
            return anterior["avaliacao_id"], True
        if self.injetor.disparar("banco"):
            # Transacao abortada antes do commit: nenhuma das duas linhas fica.
            raise httpx.ConnectError("conexao com o banco caiu antes do commit (falha injetada)")
        avaliacao_id = self._proximo_id
        self._proximo_id += 1
        # Commit: as duas linhas de uma vez, copiadas como o banco guardaria.
        self.avaliacoes[avaliacao_id] = {**deepcopy(avaliacao), "avaliacao_id": avaliacao_id}
        self.predicoes.append({
            **deepcopy(predicao), "avaliacao_id": avaliacao_id,
            "predicao_id": len(self.predicoes) + 1,
            "timestamp_predicao": datetime.now(timezone.utc).isoformat(),
        })
        self.gravada_por[avaliacao_id] = request_id_atual()
        if self.injetor.disparar("banco_pos_commit"):
            raise httpx.ReadTimeout("resposta do banco perdida depois do commit (falha injetada)")
        return avaliacao_id, False

    def buscar_avaliacao(self, avaliacao_id: int) -> dict | None:
        self._postgres()
        return deepcopy(self.avaliacoes.get(avaliacao_id))

    def predicao_de(self, avaliacao_id: int) -> dict | None:
        self._postgres()
        dela = [p for p in self.predicoes if p["avaliacao_id"] == avaliacao_id]
        return deepcopy(max(dela, key=lambda p: p["timestamp_predicao"])) if dela else None

    def inserir_auditoria(self, registro: dict) -> None:
        self._postgres()
        # timestamp: DEFAULT NOW() da tabela auditoria
        self.auditoria.append({**deepcopy(registro), "auditoria_id": len(self.auditoria) + 1,
                               "timestamp": datetime.now(timezone.utc)})

    def invalidar_cache(self) -> None:
        return None


def _sem_banco_real():
    raise AssertionError("o teste tentou falar com o Supabase real")


class _RespostaOpenMeteo:
    def __init__(self, dados: dict):
        self._dados = dados

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self._dados


class OpenMeteoFalsa:
    """
    Substitui o requests.get que clima.buscar usa: responde no formato da
    Open-Meteo, ou cai quando o injetor manda. Guarda o que 'informou' por
    coordenada, para conferir o valor gravado contra a fonte (R4-06).
    """

    def __init__(self, injetor: Injetor):
        self.injetor = injetor
        self.chamadas = 0
        self.informado: dict[tuple[float, float], dict] = {}

    def __call__(self, url, params=None, timeout=None):
        assert url.startswith(config.OPENMETEO_BASE_URL), f"requisicao inesperada para {url}"
        self.chamadas += 1
        if self.injetor.disparar("clima"):
            raise requests.ConnectTimeout("Open-Meteo fora do ar (falha injetada)")
        lat, lon = params["latitude"], params["longitude"]
        informado = {
            "temperatura_ar": round(15 + abs(lat) % 20, 1),
            "precipitacao_mm": round(abs(lat * lon) % 40, 1),
            "velocidade_vento": round(abs(lon) % 30, 1),
        }
        self.informado[(lat, lon)] = informado
        return _RespostaOpenMeteo({
            "current": {"temperature_2m": informado["temperatura_ar"],
                        "wind_speed_10m": informado["velocidade_vento"]},
            "hourly": {"precipitation": [informado["precipitacao_mm"]] + [0.0] * 23},
        })


@dataclass
class Ambiente:
    banco: RepositorioFalso
    injetor: Injetor
    open_meteo: OpenMeteoFalsa


@pytest.fixture
def ambiente():
    injetor = Injetor()
    banco = RepositorioFalso(injetor)
    open_meteo = OpenMeteoFalsa(injetor)
    with patch.multiple(
        repository,
        get_client=_sem_banco_real,
        buscar_equipamento=banco.buscar_equipamento,
        operador_existe=banco.operador_existe,
        buscar_por_leitura=banco.buscar_por_leitura,
        registrar_avaliacao=banco.registrar_avaliacao,
        buscar_avaliacao=banco.buscar_avaliacao,
        predicao_de=banco.predicao_de,
        inserir_auditoria=banco.inserir_auditoria,
        invalidar_cache=banco.invalidar_cache,
    ), patch("backend.services.clima.requests.get", open_meteo):
        yield Ambiente(banco, injetor, open_meteo)


@pytest.fixture
def auth():
    token, _ = criar_token(USUARIO, "analista")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def random_intacto():
    """main() dos scripts semeia o random global; o estado volta ao fim."""
    estado = random.getstate()
    yield
    random.setstate(estado)


@pytest.fixture
def log_da_api():
    """
    O handler que backend.core.logging.configurar() monta em producao
    (formatter e filtro do request_id), com o stdout trocado por um buffer.
    configurar() desliga a propagacao do logger 'safefield' e outros testes
    leem esses logs pelo caplog: o estado anterior volta ao fim.
    """
    raiz = logging.getLogger("safefield")
    handlers, nivel, propaga = list(raiz.handlers), raiz.level, raiz.propagate
    for h in handlers:
        raiz.removeHandler(h)
    try:
        configurar()
        (handler,) = raiz.handlers
        buffer = io.StringIO()
        handler.setStream(buffer)
        yield buffer
    finally:
        for h in list(raiz.handlers):
            raiz.removeHandler(h)
        for h in handlers:
            raiz.addHandler(h)
        raiz.setLevel(nivel)
        raiz.propagate = propaga


# --- Cliente: o envio do script real, pela API em memoria --------------------

@dataclass
class Resposta:
    leitura_id: str
    tentativa: int
    status: int
    request_id: str
    corpo: dict


class ApiEmMemoria:
    """
    O `post` que coleta_real.enviar recebe (assinatura de requests.post),
    ligado ao TestClient. Arma a falha do servidor no primeiro envio e a
    corrida no segundo, e guarda cada resposta inteira para o teste.
    """

    def __init__(self, injetor: Injetor):
        self.injetor = injetor
        self.respostas: list[Resposta] = []
        self.plano: dict[int, str] = {}

    def __call__(self, url, json=None, headers=None, timeout=None):
        assert url == URL_AVALIACOES, f"requisicao inesperada para {url}"
        tentativa = 1 + sum(1 for r in self.respostas if r.leitura_id == json["leitura_id"])
        if tentativa in self.plano:
            self.injetor.armar(self.plano[tentativa])
        r = client.post("/avaliacoes", json=json, headers=headers)
        self.injetor.conferir()
        self.respostas.append(Resposta(json["leitura_id"], tentativa, r.status_code,
                                       r.headers["X-Request-ID"], r.json()))
        return r


@dataclass
class Coleta:
    enviadas: dict[str, dict] = field(default_factory=dict)
    falhas: dict[str, str | None] = field(default_factory=dict)
    clima_no_payload: set[str] = field(default_factory=set)
    corridas: set[str] = field(default_factory=set)
    envios: list[dict] = field(default_factory=list)  # formato de coleta_real
    respostas: list[Resposta] = field(default_factory=list)
    log: str = ""

    def tentativas(self, leitura_id: str) -> list[dict]:
        (envio,) = [e for e in self.envios if e["leitura_id"] == leitura_id]
        return envio["tentativas"]

    def resposta(self, request_id: str) -> Resposta:
        (r,) = [r for r in self.respostas if r.request_id == request_id]
        return r


def gerar_leituras(n: int) -> list[tuple[dict, bool]]:
    """
    Leituras do gerador do simulador (scripts/simulate_telemetry.py), com
    semente fixa e sem tocar o random global. A cada 4, o clima vem no
    payload, pelo mesmo bloco de --sem-clima-externo (coleta_real.clima_de_campo).
    """
    rng = random.Random(461)
    saida = []
    with patch.object(simulador, "random", rng), \
         patch.object(simulador, "_OPERADORES", list(OPERADORES)):
        for i in range(n):
            leitura, _ = simulador.gerar_leitura(list(CADASTRO.values()), "normal")
            no_payload = i % 4 == 2
            if no_payload:
                leitura.update(coleta_real.clima_de_campo(leitura["tipo_solo"], rng))
            leitura["leitura_id"] = str(uuid.UUID(int=rng.getrandbits(128), version=4))
            saida.append((leitura, no_payload))
    return saida


def executar_coleta(amb: Ambiente, auth: dict, log: io.StringIO, n: int = N_LEITURAS) -> Coleta:
    """Cada leitura vai por coleta_real.enviar -> simulador.enviar_com_retry -> API em memoria."""
    coleta = Coleta()
    api = ApiEmMemoria(amb.injetor)
    for i, (leitura, no_payload) in enumerate(gerar_leituras(n)):
        lid = leitura["leitura_id"]
        falha = FALHA_POR_RESTO.get(i % 8)
        coleta.enviadas[lid] = leitura
        coleta.falhas[lid] = falha
        if no_payload:
            coleta.clima_no_payload.add(lid)
        api.plano = {}
        if falha in DO_SERVIDOR:
            api.plano[1] = falha
        if i in CORRIDA_NO_RETRY:
            api.plano[2] = "corrida"
            coleta.corridas.add(lid)
        tentativas = coleta_real.enviar(api, URL_AVALIACOES, auth, leitura,
                                        descartar_primeira=falha == "resposta_perdida")
        coleta.envios.append({"leitura_id": lid, "clima_no_payload": no_payload, "tentativas": tentativas})
    coleta.respostas = api.respostas
    coleta.log = log.getvalue()
    return coleta


def _log_por_request_id(texto: str) -> dict[str, list[dict]]:
    por_rid: dict[str, list[dict]] = defaultdict(list)
    for linha in texto.splitlines():
        m = RE_LINHA_FORMATADA.match(linha)
        assert m, f"linha fora do formato de producao: {linha!r}"
        por_rid[m["rid"]].append(m.groupdict())
    return por_rid


# --- Cenario principal ------------------------------------------------------

class TestColetaComFalhasInjetadas:
    """R4-07: N leituras, falhas de Open-Meteo, de banco e de rede; exatamente N de tudo."""

    def test_o_plano_exercita_cada_falha(self, ambiente, auth, log_da_api):
        """Guarda contra a vacuidade: sem falha disparada, o resto nao prova nada."""
        c = executar_coleta(ambiente, auth, log_da_api)
        planejadas = Counter(f for f in c.falhas.values() if f)
        assert set(planejadas) == set(STATUS_ESPERADOS) - {None}
        assert all(n == 3 for n in planejadas.values()), planejadas
        do_servidor = Counter({f: n for f, n in planejadas.items() if f in DO_SERVIDOR})
        assert ambiente.injetor.disparadas == do_servidor + Counter({"corrida": len(CORRIDA_NO_RETRY)})
        descartadas = [t for e in c.envios for t in e["tentativas"] if t["descartada"]]
        assert len(descartadas) == planejadas["resposta_perdida"]
        # A corrida chegou ao ramo de reenvio do registrar_avaliacao falso.
        assert ambiente.banco.reenvios_na_gravacao == len(CORRIDA_NO_RETRY) == len(c.corridas)
        assert len(c.clima_no_payload) == 6
        assert not c.clima_no_payload & {lid for lid, f in c.falhas.items() if f == "clima"}

    def test_sem_perda_n_avaliacoes_e_n_predicoes(self, ambiente, auth, log_da_api):
        c = executar_coleta(ambiente, auth, log_da_api)
        banco = ambiente.banco
        assert len(c.enviadas) == N_LEITURAS >= 20
        assert len(banco.avaliacoes) == N_LEITURAS
        assert len(banco.predicoes) == N_LEITURAS
        assert {a.get("leitura_id") for a in banco.avaliacoes.values()} == set(c.enviadas)

    def test_sem_duplicata_por_leitura_id(self, ambiente, auth, log_da_api):
        c = executar_coleta(ambiente, auth, log_da_api)
        por_leitura = Counter(a.get("leitura_id") for a in ambiente.banco.avaliacoes.values())
        assert por_leitura, "nenhuma avaliacao gravada"
        assert None not in por_leitura, "avaliacao gravada sem a chave de idempotencia"
        assert set(por_leitura.values()) == {1}, [lid for lid, n in por_leitura.items() if n > 1]
        assert len(por_leitura) == len(c.enviadas)

    def test_uma_predicao_por_avaliacao_e_zero_orfas(self, ambiente, auth, log_da_api):
        executar_coleta(ambiente, auth, log_da_api)
        banco = ambiente.banco
        ids = set(banco.avaliacoes)
        assert ids, "nenhuma avaliacao gravada"
        por_avaliacao = Counter(p["avaliacao_id"] for p in banco.predicoes)
        assert set(por_avaliacao) == ids, "predicao orfa ou avaliacao sem predicao"
        assert set(por_avaliacao.values()) == {1}

    def test_cada_falha_termina_gravada_uma_vez_pela_requisicao_certa(self, ambiente, auth, log_da_api):
        """
        502 e 503 antes do commit nao gravam e o retry grava; no banco_pos_commit
        quem gravou foi a requisicao do 503, e o retry devolve o gravado (200);
        a resposta perdida volta como 200 com o mesmo resultado.
        """
        c = executar_coleta(ambiente, auth, log_da_api)
        banco = ambiente.banco
        assert c.envios, "nenhuma leitura enviada"
        for e in c.envios:
            lid = e["leitura_id"]
            assert [t["status"] for t in e["tentativas"]] == STATUS_ESPERADOS[c.falhas[lid]], (lid, c.falhas[lid])

        esperado = {}
        for e in c.envios:
            primeira, ultima = e["tentativas"][0], e["tentativas"][-1]
            quem_gravou = primeira if c.falhas[e["leitura_id"]] in ("banco_pos_commit", "resposta_perdida") else ultima
            esperado[ultima["avaliacao_id"]] = quem_gravou["request_id"]
        assert len(esperado) == N_LEITURAS
        assert banco.gravada_por == esperado

        com_reenvio = [lid for lid, f in c.falhas.items() if f in ("resposta_perdida", "banco_pos_commit")]
        assert len(com_reenvio) == 6
        for lid in com_reenvio:
            reenvio = c.resposta(c.tentativas(lid)[-1]["request_id"]).corpo
            a = banco.avaliacoes[reenvio["avaliacao_id"]]
            assert a["leitura_id"] == lid
            assert (reenvio["risco_score"], reenvio["faixa_risco"], reenvio["clima_origem"]) == \
                (a["risco_score"], a["faixa_risco"], a["clima_origem"]), lid
            if c.falhas[lid] == "resposta_perdida":
                original = c.resposta(c.tentativas(lid)[0]["request_id"]).corpo
                for campo in ("avaliacao_id", "risco_score", "faixa_risco", "clima_origem",
                              "modelo_versao", "timestamp"):
                    assert reenvio[campo] == original[campo], (lid, campo)

    def test_falhas_ficam_no_log_pelo_request_id(self, ambiente, auth, log_da_api):
        """Cada 502/503 deixa no log de producao ao menos uma linha WARNING ou ERROR com o seu request_id."""
        c = executar_coleta(ambiente, auth, log_da_api)
        log = _log_por_request_id(c.log)
        falhas = [r for r in c.respostas if r.status in (502, 503)]
        assert len(falhas) == 12
        for r in falhas:
            niveis = {x["nivel"] for x in log[r.request_id]}
            assert niveis & {"WARNING", "ERROR"}, (r.request_id, niveis)
        # Com o Postgres fora a auditoria do 'erro' nao grava, mas nao some: fica no log.
        sem_postgres = [c.tentativas(lid)[0]["request_id"] for lid, f in c.falhas.items() if f == "postgres_fora"]
        assert len(sem_postgres) == 3
        for rid in sem_postgres:
            msgs = [x["msg"] for x in log[rid] if x["nivel"] == "ERROR"]
            assert [m for m in msgs if m.startswith("falha ao gravar auditoria")], msgs
            assert [m for m in msgs if "PostgREST PGRST000" in m], msgs

    def test_auditoria_sucesso_ou_reenvio_por_avaliacao(self, ambiente, auth, log_da_api):
        c = executar_coleta(ambiente, auth, log_da_api)
        banco = ambiente.banco
        ids = set(banco.avaliacoes)
        assert len(ids) == N_LEITURAS
        sucessos = Counter(x["avaliacao_id"] for x in banco.auditoria if x["status"] == "sucesso")
        reenvios = Counter(x["avaliacao_id"] for x in banco.auditoria if x["status"] == "reenvio")
        assert sucessos and reenvios

        # O invariante: um 'sucesso', ou nenhum e ao menos um 'reenvio'.
        for aid in ids:
            assert sucessos[aid] == 1 or (sucessos[aid] == 0 and reenvios[aid] >= 1), aid
        # Nenhuma linha de trilha aponta para o que nao foi gravado.
        assert set(sucessos) | set(reenvios) <= ids
        # Cada 201 audita um 'sucesso' e cada 200 um 'reenvio'.
        por_status = defaultdict(Counter)
        for e in c.envios:
            for t in e["tentativas"]:
                por_status[t["status"]][t["avaliacao_id"]] += 1
        assert sucessos == por_status[201]
        assert reenvios == por_status[200]
        # banco_pos_commit: a API nunca soube que gravou; so o reenvio registra a avaliacao.
        pos_commit = {c.tentativas(lid)[-1]["avaliacao_id"] for lid, f in c.falhas.items() if f == "banco_pos_commit"}
        assert len(pos_commit) == 3
        assert all(sucessos[aid] == 0 and reenvios[aid] == 1 for aid in pos_commit)

        versao = {p["avaliacao_id"]: p["modelo_versao"] for p in banco.predicoes}
        for x in banco.auditoria:
            if x["status"] in ("sucesso", "reenvio"):
                assert (x["usuario"], x["perfil"], x["acao"]) == (USUARIO, "analista", "avaliacao")
                assert x["modelo_versao"] == versao[x["avaliacao_id"]] == config.MODELO_VERSAO
                assert x["score_gerado"] == banco.avaliacoes[x["avaliacao_id"]]["risco_score"]

        erros = [x for x in banco.auditoria if x["status"] == "erro"]
        # 3 de clima + 3 de banco + 3 de banco_pos_commit; os de postgres_fora nao gravam.
        tipos = Counter("clima" if x["detalhe"].startswith("Open-Meteo indisponivel") else x["detalhe"]
                        for x in erros)
        assert tipos == Counter({"clima": 3, "gravacao falhou: ConnectError": 3,
                                 "gravacao falhou: ReadTimeout": 3})
        assert all(x["avaliacao_id"] is None for x in erros)

    def test_o_log_e_o_do_formatter_de_producao(self, ambiente, auth, log_da_api):
        """Toda linha sai no formato de configurar(), e toda resposta tem linhas com o seu X-Request-ID."""
        c = executar_coleta(ambiente, auth, log_da_api)
        log = _log_por_request_id(c.log)  # falha em qualquer linha fora do formato
        assert log, "nenhuma linha de log capturada"
        assert set(log) == {r.request_id for r in c.respostas}

    def test_rastreabilidade_pelo_log_de_producao(self, ambiente, auth, log_da_api):
        """
        Para cada avaliacao: X-Request-ID da resposta final (201 ou 200) ->
        linha do log de producao que coleta_real.checar_log casou -> avaliacao_id
        -> avaliacoes (entrada, clima_origem), predicoes (modelo_versao) e
        auditoria (usuario, perfil, horario).
        """
        c = executar_coleta(ambiente, auth, log_da_api)
        checagem, casadas = coleta_real.checar_log(c.log.splitlines(), c.envios)
        assert checagem["ok"], checagem
        banco = ambiente.banco
        finais = {e["leitura_id"]: e["tentativas"][-1] for e in c.envios}
        assert len(finais) == N_LEITURAS
        assert {t["status"] for t in finais.values()} == {200, 201}, "um dos caminhos nao foi exercitado"

        vistas = set()
        for lid, t in finais.items():
            # 1. request_id -> linha de log -> avaliacao_id
            m = coleta_real.RE_LINHA_DE_LOG.search(casadas[t["request_id"]])
            aid = int(m["aid"])
            assert aid == t["avaliacao_id"] and bool(m["reenvio"]) == (t["status"] == 200), lid
            vistas.add(aid)

            # 2. avaliacao: a entrada como foi enviada, e a procedencia do clima
            a = banco.avaliacoes[aid]
            enviada = c.enviadas[lid]
            assert {k: a.get(k) for k in enviada} == enviada, lid
            assert a["fonte"] == "telemetria"
            if lid in c.clima_no_payload:
                assert a["clima_origem"] == "payload"
            else:
                assert a["clima_origem"] == "open-meteo"
                informado = ambiente.open_meteo.informado[(enviada["latitude"], enviada["longitude"])]
                assert {k: a[k] for k in informado} == informado, lid
            assert all(a[k] is not None for k in CAMPOS_CLIMA)

            # 3. predicao: a versao do modelo que decidiu
            (p,) = [p for p in banco.predicoes if p["avaliacao_id"] == aid]
            assert p["modelo_versao"] == config.MODELO_VERSAO
            assert p["risco_score_predito"] == a["risco_score"]

            # 4. auditoria: quem pediu e quando; a linha do tipo da resposta final existe
            trilha = [x for x in banco.auditoria
                      if x["avaliacao_id"] == aid and x["status"] in ("sucesso", "reenvio")]
            assert trilha, (lid, aid, "sem sucesso nem reenvio na auditoria")
            assert ("reenvio" if t["status"] == 200 else "sucesso") in {x["status"] for x in trilha}, lid
            for x in trilha:
                assert (x["usuario"], x["perfil"]) == (USUARIO, "analista")
                assert x["timestamp"] >= datetime.fromisoformat(a["timestamp"])
        assert vistas == set(banco.avaliacoes)

    def test_checador_do_script_real_aprova_esta_coleta(self, ambiente, auth, log_da_api):
        """coleta_real.checar() concorda com as assercoes acima sobre a mesma coleta."""
        c = executar_coleta(ambiente, auth, log_da_api)
        banco = ambiente.banco
        checagens = coleta_real.checar(c.envios, list(banco.avaliacoes.values()), banco.predicoes,
                                       banco.auditoria, leituras=c.enviadas, usuario=USUARIO)
        assert len(checagens) >= 10
        assert [ch for ch in checagens if not ch["ok"]] == []


# --- Regressao: o simulador perdia a leitura com a Open-Meteo fora ----------

def _post_pela_api(url, json=None, headers=None, timeout=None):
    """requests.post trocado pelo TestClient: o simulador fala com a API real em memoria."""
    assert url.startswith(API_FALSA), f"requisicao inesperada para {url}"
    return client.post(url[len(API_FALSA):], json=json, headers=headers)


@pytest.mark.usefixtures("random_intacto")
class TestSimuladorNaoPerdeLeitura:
    """
    Regressao (S4-28): o main() do simulador so repetia o envio em falha de
    rede. Com a Open-Meteo fora na primeira tentativa, a API respondia 502, o
    simulador contava falha e a leitura nunca chegava ao banco.
    """

    def test_open_meteo_fora_na_primeira_tentativa_a_leitura_chega(self, ambiente, monkeypatch):
        cliente = MagicMock()
        cliente.table.return_value.select.return_value.execute.return_value.data = [
            {"operador_id": o} for o in OPERADORES
        ]
        repo_do_simulador = SimpleNamespace(
            listar_equipamentos=lambda: list(CADASTRO.values()), get_client=lambda: cliente
        )
        monkeypatch.setenv("SAFEFIELD_SENHA", SENHAS[USUARIO])
        monkeypatch.setattr(sys, "argv", [
            "simulate_telemetry.py", "--n", "1", "--intervalo", "0", "--seed", "7",
            "--api", API_FALSA, "--usuario", USUARIO,
        ])
        ambiente.injetor.armar("clima")
        with patch.object(simulador, "repo", repo_do_simulador), \
             patch.object(simulador, "_OPERADORES", []), \
             patch.object(simulador.requests, "post", _post_pela_api):
            simulador.main()  # sys.exit(1) se contar falha

        ambiente.injetor.conferir()
        assert ambiente.injetor.disparadas["clima"] == 1, "a Open-Meteo nao caiu: o teste nao exercitou a falha"
        assert ambiente.open_meteo.chamadas == 2
        assert len(ambiente.banco.avaliacoes) == 1
        assert len(ambiente.banco.predicoes) == 1
        (gravada,) = ambiente.banco.avaliacoes.values()
        assert gravada["leitura_id"], "gravada sem a chave de idempotencia"
        assert gravada["clima_origem"] == "open-meteo"


class TestEnviarComRetry:
    """simulate_telemetry.enviar_com_retry: o que repete e o que nao repete."""

    def _post(self, *saidas):
        feitas = []

        def post(url, json=None, headers=None, timeout=None):
            feitas.append(json["leitura_id"])
            saida = saidas[len(feitas) - 1]
            if isinstance(saida, Exception):
                raise saida
            return SimpleNamespace(status_code=saida, text="")

        return post, feitas

    @pytest.mark.parametrize("primeira", [502, 503, requests.ConnectionError("caiu")],
                             ids=["502", "503", "rede"])
    def test_repete_com_a_mesma_chave(self, primeira):
        post, feitas = self._post(primeira, 201)
        r = simulador.enviar_com_retry(post, URL_AVALIACOES, {"leitura_id": "k1"}, {})
        assert r.status_code == 201
        assert feitas == ["k1", "k1"]

    @pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422, 500])
    def test_nao_repete_recusa_nem_500(self, status):
        post, feitas = self._post(status, 201)
        assert simulador.enviar_com_retry(post, URL_AVALIACOES, {"leitura_id": "k1"}, {}).status_code == status
        assert feitas == ["k1"]

    def test_esgota_as_tentativas_e_avisa_cada_falha(self):
        post, feitas = self._post(503, requests.ConnectionError("caiu"), 503)
        avisos = []
        r = simulador.enviar_com_retry(post, URL_AVALIACOES, {"leitura_id": "k1"}, {}, tentativas=3,
                                       ao_falhar=lambda n, f: avisos.append(n))
        assert r.status_code == 503
        assert feitas == ["k1"] * 3 and avisos == [1, 2, 3]

    def test_ultima_sem_resposta_devolve_none(self):
        post, _ = self._post(503, requests.ConnectionError("caiu"))
        assert simulador.enviar_com_retry(post, URL_AVALIACOES, {"leitura_id": "k1"}, {}) is None

    def test_sem_chave_recusa_antes_de_enviar(self):
        post, feitas = self._post(201)
        with pytest.raises(ValueError, match="leitura_id"):
            simulador.enviar_com_retry(post, URL_AVALIACOES, {}, {})
        assert feitas == []


# --- Consistencia do payload (S4-14) ----------------------------------------

LEITURA_BASE = {
    "equipamento_id": "EQ-0001",
    "operador_id": "OP-0001",
    "latitude": -12.5453,
    "longitude": -55.7114,
    "tipo_solo": "argiloso",
    "distancia_agua_m": 300.0,
    "declividade": 6.0,
    "tipo_operacao": "colheita",
    "velocidade_kmh": 5.5,
    "horas_operacao": 6.0,
    "horario_operacao": 11,
    "vibracao_g": 1.4,
    "temperatura_motor": 88.0,
    "pct_velocidade_acima_recomendada": 18.0,
    "freq_eventos_bruscos": 3.0,
    "pct_operacoes_noturnas": 12.0,
    "score_operador_historico": 45.0,
    "ultima_manutencao_dias": 120,
    "ultima_manutencao_horas_op": 300.0,
}
CLIMA_COMPLETO = {"temperatura_ar": 25.0, "precipitacao_mm": 10.0, "umidade_solo": 26.0,
                  "velocidade_vento": 12.0, "condicao_clima": "nublado"}
REMOVER = object()

# (alteracao sobre LEITURA_BASE, trecho esperado na auditoria de erro ou None)
INVALIDAS = [
    pytest.param({"velocidade_kmh": 99.0}, None, id="schema-fora-da-faixa"),
    pytest.param({"faixa_risco": "baixo"}, None, id="schema-campo-derivado-enviado"),
    pytest.param({"operador_id": REMOVER}, None, id="schema-obrigatorio-ausente"),
    pytest.param({"leitura_id": "nao-e-uuid"}, None, id="schema-leitura-id-invalido"),
    pytest.param({"tipo_operacao": "parado", "velocidade_kmh": 5.0}, None,
                 id="cruzada-parado-com-velocidade-regra-4"),
    pytest.param({**CLIMA_COMPLETO, "precipitacao_mm": 0.0, "condicao_clima": "tempestade"}, None,
                 id="cruzada-condicao-incompativel-com-a-chuva-regra-5"),
    pytest.param({"equipamento_id": "EQ-0002", "temperatura_motor": 80.0}, "Regra 1",
                 id="cruzada-motor-sem-iot-regra-1"),
    pytest.param({"equipamento_id": "EQ-0003", "temperatura_motor": 80.0}, "Regra 10",
                 id="cruzada-implemento-com-motor-regra-10"),
]


def _leitura(alteracao: dict) -> dict:
    leitura = {**LEITURA_BASE, "leitura_id": str(uuid.uuid4())}
    for campo, valor in alteracao.items():
        if valor is REMOVER:
            leitura.pop(campo)
        else:
            leitura[campo] = valor
    return leitura


class TestConsistenciaDoPayload:
    """S4-14: payload invalido e recusado com 422 e nada e persistido."""

    def test_controle_a_leitura_base_e_gravada(self, ambiente, auth):
        """Sem este controle, 'nada gravado' abaixo poderia ser so um banco falso desligado."""
        r = client.post("/avaliacoes", json=_leitura({}), headers=auth)
        assert r.status_code == 201, r.text
        assert len(ambiente.banco.avaliacoes) == 1
        assert len(ambiente.banco.predicoes) == 1

    @pytest.mark.parametrize("alteracao,regra", INVALIDAS)
    def test_invalido_e_recusado_e_nada_grava(self, ambiente, auth, alteracao, regra):
        r = client.post("/avaliacoes", json=_leitura(alteracao), headers=auth)
        assert r.status_code == 422, r.text
        assert r.headers.get("X-Request-ID")
        banco = ambiente.banco
        assert banco.avaliacoes == {} and banco.predicoes == []
        assert ambiente.open_meteo.chamadas == 0, "recusa depois de consultar o clima"
        if regra is None:
            # Recusado no schema: nem chega ao servico.
            assert banco.auditoria == []
        else:
            (erro,) = banco.auditoria
            assert erro["status"] == "erro" and regra in erro["detalhe"]
            assert erro["avaliacao_id"] is None

    def test_mesma_chave_com_outro_payload_e_conflito_e_nada_grava(self, ambiente, auth):
        leitura = _leitura({})
        assert client.post("/avaliacoes", json=leitura, headers=auth).status_code == 201
        alterada = {**leitura, "velocidade_kmh": leitura["velocidade_kmh"] + 1}
        r = client.post("/avaliacoes", json=alterada, headers=auth)
        assert r.status_code == 409, r.text
        banco = ambiente.banco
        assert len(banco.avaliacoes) == 1 and len(banco.predicoes) == 1
        assert [x["status"] for x in banco.auditoria] == ["sucesso", "erro"]


# --- O checador do script real ----------------------------------------------

LEITURAS_INTEGRAS = {
    "l1": {"leitura_id": "l1", "equipamento_id": "EQ-0001", "latitude": -12.5, "velocidade_kmh": 5.0},
    "l2": {"leitura_id": "l2", "equipamento_id": "EQ-0002", "latitude": -17.8, "velocidade_kmh": 0},
    "l3": {"leitura_id": "l3", "equipamento_id": "EQ-0004", "latitude": -21.6, "velocidade_kmh": 9.5},
}


def _coleta_integra() -> tuple[list, list, list, list]:
    """
    Tres leituras: uma normal; uma com a primeira resposta descartada; e uma
    com a resposta do banco perdida depois do commit (503 e depois 200, so
    'reenvio' na auditoria).
    """
    envios = [
        {"leitura_id": "l1", "clima_no_payload": False, "tentativas": [
            {"status": 201, "request_id": "r1", "avaliacao_id": 1, "descartada": False}]},
        {"leitura_id": "l2", "clima_no_payload": True, "tentativas": [
            {"status": 201, "request_id": "r2", "avaliacao_id": 2, "descartada": True},
            {"status": 200, "request_id": "r3", "avaliacao_id": 2, "descartada": False}]},
        {"leitura_id": "l3", "clima_no_payload": False, "tentativas": [
            {"status": 503, "request_id": "r4", "avaliacao_id": None, "descartada": False},
            {"status": 200, "request_id": "r5", "avaliacao_id": 3, "descartada": False}]},
    ]
    gravada = {"fonte": "telemetria", "timestamp": "2026-09-28T10:00:00+00:00"}
    avaliacoes = [
        {**LEITURAS_INTEGRAS["l1"], **gravada, "avaliacao_id": 1, "clima_origem": "open-meteo"},
        # NUMERIC volta como numero JSON: 0 enviado, 0.0 gravado e o mesmo valor.
        {**LEITURAS_INTEGRAS["l2"], **gravada, "velocidade_kmh": 0.0, "avaliacao_id": 2,
         "clima_origem": "payload"},
        {**LEITURAS_INTEGRAS["l3"], **gravada, "avaliacao_id": 3, "clima_origem": "open-meteo"},
    ]
    predicoes = [{"avaliacao_id": i, "modelo_versao": "v"} for i in (1, 2, 3)]
    trilha = {"usuario": "a", "perfil": "analista", "modelo_versao": "v"}
    auditoria = [
        {"avaliacao_id": 1, "status": "sucesso", **trilha},
        {"avaliacao_id": 2, "status": "sucesso", **trilha},
        {"avaliacao_id": 2, "status": "reenvio", **trilha},
        {"avaliacao_id": 3, "status": "reenvio", **trilha},
    ]
    return envios, avaliacoes, predicoes, auditoria


def _checar(envios, avaliacoes, predicoes, auditoria, leituras=None, usuario="a") -> list[dict]:
    return coleta_real.checar(envios, avaliacoes, predicoes, auditoria,
                              leituras=deepcopy(LEITURAS_INTEGRAS) if leituras is None else leituras,
                              usuario=usuario)


def _falhas(checagens: list[dict]) -> set[str]:
    assert checagens, "checar() nao devolveu nenhuma checagem"
    return {c["nome"] for c in checagens if not c["ok"]}


LOG_INTEGRO = [
    "2026-09-28T10:00:00 INFO    [r1] safefield.scoring: avaliacao 1: EQ-0001 score=1.00 faixa=baixo usuario=a",
    "2026-09-28T10:00:01 INFO    [r2] safefield.scoring: avaliacao 2: EQ-0002 score=2.00 faixa=baixo usuario=a",
    "2026-09-28T10:00:02 INFO    [r3] safefield.scoring: reenvio avaliacao 2: EQ-0002 leitura_id=l2 usuario=a",
    "2026-09-28T10:00:03 ERROR   [r4] safefield.api: banco inacessivel em /avaliacoes: timeout",
    "2026-09-28T10:00:04 INFO    [r5] safefield.scoring: reenvio avaliacao 3: EQ-0004 leitura_id=l3 usuario=a",
]


class TestChecadorDoScriptReal:
    """scripts/evidencias/coleta_real.checar() e checar_log() nao podem dar OK falso contra o banco real."""

    def test_coleta_integra_passa(self):
        assert _falhas(_checar(*_coleta_integra())) == set()

    def test_conjunto_vazio_nao_passa(self):
        falhas = _falhas(coleta_real.checar([], [], [], [], leituras={}, usuario="a"))
        assert {"conjunto_nao_vazio", "auditoria_bate_com_as_respostas", "entrada_gravada_confere"} <= falhas

    def test_duplicata_e_detectada(self):
        envios, avaliacoes, predicoes, auditoria = _coleta_integra()
        avaliacoes.append({**avaliacoes[0], "avaliacao_id": 9})
        assert "uma_avaliacao_por_leitura" in _falhas(_checar(envios, avaliacoes, predicoes, auditoria))

    def test_perda_e_detectada(self):
        envios, avaliacoes, predicoes, auditoria = _coleta_integra()
        assert "uma_avaliacao_por_leitura" in _falhas(
            _checar(envios, avaliacoes[1:], predicoes[1:], auditoria))

    def test_avaliacao_orfa_e_detectada(self):
        envios, avaliacoes, predicoes, auditoria = _coleta_integra()
        assert "uma_predicao_por_avaliacao" in _falhas(_checar(envios, avaliacoes, predicoes[:2], auditoria))

    def test_sem_resposta_descartada_nao_passa(self):
        envios, avaliacoes, predicoes, auditoria = _coleta_integra()
        envios[1]["tentativas"] = envios[1]["tentativas"][:1]
        envios[1]["tentativas"][0]["descartada"] = False
        assert "retry_apos_resposta_perdida_e_reenvio" in _falhas(
            _checar(envios, avaliacoes, predicoes, auditoria))

    def test_avaliacao_sem_sucesso_nem_reenvio_e_detectada(self):
        envios, avaliacoes, predicoes, auditoria = _coleta_integra()
        sem_a_3 = [x for x in auditoria if x["avaliacao_id"] != 3]
        assert "auditoria_sucesso_ou_reenvio_por_avaliacao" in _falhas(
            _checar(envios, avaliacoes, predicoes, sem_a_3))

    def test_sucesso_duplicado_e_detectado(self):
        envios, avaliacoes, predicoes, auditoria = _coleta_integra()
        auditoria.append(dict(auditoria[0]))
        falhas = _falhas(_checar(envios, avaliacoes, predicoes, auditoria))
        assert {"auditoria_sucesso_ou_reenvio_por_avaliacao", "auditoria_bate_com_as_respostas"} <= falhas

    def test_200_sem_reenvio_na_auditoria_e_detectado(self):
        envios, avaliacoes, predicoes, auditoria = _coleta_integra()
        sem_reenvio_da_2 = [x for x in auditoria if not (x["avaliacao_id"] == 2 and x["status"] == "reenvio")]
        assert "auditoria_bate_com_as_respostas" in _falhas(
            _checar(envios, avaliacoes, predicoes, sem_reenvio_da_2))

    def test_auditoria_de_outro_usuario_e_detectada(self):
        assert "auditoria_do_usuario_autenticado" in _falhas(_checar(*_coleta_integra(), usuario="outro"))

    def test_modelo_versao_divergente_da_predicao_e_detectado(self):
        envios, avaliacoes, predicoes, auditoria = _coleta_integra()
        predicoes[2]["modelo_versao"] = "outra"
        assert "modelo_versao_da_predicao_na_auditoria" in _falhas(
            _checar(envios, avaliacoes, predicoes, auditoria))

    def test_entrada_gravada_diferente_da_enviada_e_detectada_sem_expor_valor(self):
        envios, avaliacoes, predicoes, auditoria = _coleta_integra()
        avaliacoes[0]["latitude"] = -12.6
        checagens = _checar(envios, avaliacoes, predicoes, auditoria)
        assert _falhas(checagens) == {"entrada_gravada_confere"}
        (entrada,) = [c for c in checagens if c["nome"] == "entrada_gravada_confere"]
        assert "latitude" in entrada["detalhe"] and "-12.6" not in entrada["detalhe"]
        assert "-12.5" not in entrada["detalhe"]

    def test_resposta_que_aponta_para_outra_avaliacao_e_detectada(self):
        envios, avaliacoes, predicoes, auditoria = _coleta_integra()
        envios[0]["tentativas"][0]["avaliacao_id"] = 99
        assert "resposta_aponta_para_a_avaliacao_gravada" in _falhas(
            _checar(envios, avaliacoes, predicoes, auditoria))

    def test_log_integro_passa_e_devolve_a_linha_que_casou(self):
        envios, *_ = _coleta_integra()
        checagem, casadas = coleta_real.checar_log(list(LOG_INTEGRO), envios)
        assert checagem["ok"], checagem
        assert set(casadas) == {"r1", "r2", "r3", "r5"}
        assert casadas["r3"] == LOG_INTEGRO[2]

    @pytest.mark.parametrize("indice,rid", [(0, "r1"), (2, "r3"), (4, "r5")])
    def test_log_sem_a_linha_do_request_id_e_detectado(self, indice, rid):
        envios, *_ = _coleta_integra()
        linhas = [li for i, li in enumerate(LOG_INTEGRO) if i != indice]
        checagem, casadas = coleta_real.checar_log(linhas, envios)
        assert not checagem["ok"] and rid in checagem["detalhe"]
        assert rid not in casadas

    def test_200_com_a_linha_de_sucesso_em_vez_da_de_reenvio_e_detectado(self):
        envios, *_ = _coleta_integra()
        linhas = [li.replace("reenvio avaliacao 3:", "avaliacao 3:") for li in LOG_INTEGRO]
        checagem, _ = coleta_real.checar_log(linhas, envios)
        assert not checagem["ok"] and "r5" in checagem["detalhe"]

    def test_linha_com_outro_avaliacao_id_e_detectada(self):
        envios, *_ = _coleta_integra()
        linhas = [li.replace("avaliacao 1:", "avaliacao 10:") for li in LOG_INTEGRO]
        checagem, _ = coleta_real.checar_log(linhas, envios)
        assert not checagem["ok"] and "r1" in checagem["detalhe"]

    def test_log_sem_nenhuma_resposta_nao_passa(self):
        assert not coleta_real.checar_log([], [])[0]["ok"]

    def test_sem_log_a_checagem_sai_reprovada_e_a_trilha_diz_nao_conferida(self):
        envios, avaliacoes, predicoes, auditoria = _coleta_integra()
        checagem, casadas = coleta_real.checar_log(None, envios)
        assert not checagem["ok"] and checagem["detalhe"] == coleta_real.SEM_LOG and casadas == {}
        trilhas = coleta_real.trilhas(envios, avaliacoes, predicoes, auditoria, None)
        assert trilhas
        linhas = [t["linha_de_log"] for tr in trilhas for t in tr["tentativas"] if t["status"] in (200, 201)]
        assert linhas and set(linhas) == {coleta_real.SEM_LOG}

    def test_trilha_usa_a_linha_que_casou_no_log(self):
        envios, avaliacoes, predicoes, auditoria = _coleta_integra()
        _, casadas = coleta_real.checar_log(list(LOG_INTEGRO), envios)
        (descartada, *_) = coleta_real.trilhas(envios, avaliacoes, predicoes, auditoria, casadas)
        assert descartada["leitura_id"] == "l2"
        assert [t["linha_de_log"] for t in descartada["tentativas"]] == [LOG_INTEGRO[1], LOG_INTEGRO[2]]
        assert {a["status"] for a in descartada["auditoria"]} == {"sucesso", "reenvio"}

    def test_motivo_do_erro_nao_ecoa_o_valor_recebido(self):
        corpo = {"detail": [{"loc": ["body", "latitude"], "msg": "Input should be less than 5",
                             "input": -12.345678, "type": "less_than"}]}
        r = SimpleNamespace(json=lambda: corpo, text=str(corpo))
        motivo = coleta_real.motivo_do_erro(r)
        assert "body.latitude" in motivo and "-12.345678" not in motivo


@pytest.mark.usefixtures("random_intacto")
class TestPontosDeRedeDoScriptReal:
    """coleta_real sai com 2 (nao 1, nem traceback) quando a API ou o banco estao fora."""

    def _main(self, *extra):
        return coleta_real.main(["--api", API_FALSA, "--token-local", "--n", "2", *extra])

    def test_api_fora_sai_com_2(self):
        with patch.object(coleta_real.requests, "get", side_effect=requests.ConnectionError("recusada")):
            assert self._main() == 2

    def test_health_sem_json_sai_com_2(self):
        html = MagicMock(status_code=200, text="<html>proxy</html>")
        html.json.side_effect = requests.JSONDecodeError("Expecting value", "<html>", 0)
        with patch.object(coleta_real.requests, "get", return_value=html):
            assert self._main() == 2

    @pytest.mark.parametrize("erro", [httpx.ConnectError("sem rota"), APIError(dict(ERRO_SEM_POSTGRES))],
                             ids=["transporte", "postgrest-sem-postgres"])
    def test_banco_fora_sai_com_2(self, erro):
        saude = MagicMock(status_code=200)
        saude.json.return_value = {"status": "ok"}
        with patch.object(coleta_real.requests, "get", return_value=saude), \
             patch.object(coleta_real.repo, "get_client", side_effect=erro):
            assert self._main() == 2

    def test_login_recusado_sai_com_2(self, monkeypatch, capsys):
        saude = MagicMock(status_code=200)
        saude.json.return_value = {"status": "ok"}
        recusa = MagicMock(status_code=401, text='{"detail":"Usuario ou senha invalidos."}')
        monkeypatch.setenv("SAFEFIELD_SENHA", "errada")
        with patch.object(coleta_real.requests, "get", return_value=saude), \
             patch.object(coleta_real.requests, "post", return_value=recusa) as post, \
             patch.object(coleta_real.repo, "get_client", side_effect=AssertionError("passou do login")):
            assert coleta_real.main(["--api", API_FALSA, "--usuario", "analista"]) == 2
        post.assert_called_once()
        assert post.call_args.args[0] == f"{API_FALSA}/auth/token"
        assert "login de analista recusado (401)" in capsys.readouterr().err

    def test_log_api_inexistente_sai_com_2(self, tmp_path, capsys):
        with patch.object(coleta_real.requests, "get", side_effect=AssertionError("nao conferiu o log antes")):
            assert self._main("--log-api", str(tmp_path / "nao-existe.log")) == 2
        assert "nao-existe.log nao existe" in capsys.readouterr().err


class _ConsultaFalsa:
    """O pedaco do query builder do supabase-py que coleta_real usa."""

    def __init__(self, linhas: list[dict]):
        self.linhas = list(linhas)

    def select(self, *_colunas, **_kw):
        return self

    def order(self, *_a, **_kw):
        return self

    def limit(self, n: int):
        self.linhas = self.linhas[:n]
        return self

    def in_(self, coluna: str, valores):
        valores = set(valores)
        self.linhas = [x for x in self.linhas if x.get(coluna) in valores]
        return self

    def execute(self):
        return SimpleNamespace(data=deepcopy(self.linhas))


@pytest.mark.usefixtures("random_intacto")
class TestColetaRealDePontaAPonta:
    """
    coleta_real.main() inteiro, offline: login, /health, envio com retry e
    descarte, leitura do 'banco' (o repositorio falso atras de um query
    builder falso), arquivo de log escrito pelo handler de producao, e o JSON.
    """

    SEMENTE = [{"avaliacao_id": i, "equipamento_id": eq, "operador_id": op, "leitura_id": None}
               for i, (eq, op) in enumerate([("EQ-0001", "OP-0001"), ("EQ-0002", "OP-0002"),
                                             ("EQ-0004", "OP-0015")], start=1)]

    def _supabase(self, banco: RepositorioFalso):
        tabelas = {
            "avaliacoes": lambda: self.SEMENTE + list(banco.avaliacoes.values()),
            "equipamentos": lambda: list(CADASTRO.values()),
            "predicoes": lambda: banco.predicoes,
            "auditoria": lambda: banco.auditoria,
        }
        return SimpleNamespace(table=lambda nome: _ConsultaFalsa(tabelas[nome]()))

    def _rotas(self, open_meteo):
        def get(url, params=None, timeout=None):
            if url.startswith(config.OPENMETEO_BASE_URL):
                return open_meteo(url, params=params, timeout=timeout)
            assert url == f"{API_FALSA}/health", f"requisicao inesperada para {url}"
            return client.get("/health")

        return get, _post_pela_api

    def test_coleta_integra_sai_com_0_e_o_json_nao_leva_posicao(self, ambiente, log_da_api, tmp_path,
                                                               monkeypatch, capsys):
        arquivo_de_log = (tmp_path / "api.log").open("w", encoding="utf-8")
        logging.getLogger("safefield").handlers[0].setStream(arquivo_de_log)
        saida = tmp_path / "coleta.json"
        monkeypatch.setenv("SAFEFIELD_SENHA", SENHAS[USUARIO])
        get, post = self._rotas(ambiente.open_meteo)
        with patch.object(coleta_real, "repo", SimpleNamespace(get_client=lambda: self._supabase(ambiente.banco))), \
             patch.object(coleta_real.requests, "get", get), \
             patch.object(coleta_real.requests, "post", post), \
             patch.object(simulador, "_OPERADORES", []):
            codigo = coleta_real.main(["--api", API_FALSA, "--n", "8", "--k", "4", "--seed", "3",
                                       "--usuario", USUARIO, "--log-api", str(tmp_path / "api.log"),
                                       "--saida", str(saida)])
        arquivo_de_log.close()
        impresso = capsys.readouterr().out
        assert codigo == 0, impresso

        texto = saida.read_text(encoding="utf-8")
        relatorio = json.loads(texto)
        assert relatorio["ok"] and relatorio["autenticacao"] == {"modo": "login", "usuario": USUARIO,
                                                                 "como": "POST /auth/token"}
        assert len(ambiente.banco.avaliacoes) == 8 and relatorio["resumo"]["respostas_descartadas"] == 2
        assert {c["nome"] for c in relatorio["checagens"]} >= {"entrada_gravada_confere",
                                                             "log_correlacionado_por_request_id"}
        # LGPD: nem a chave nem o valor da posicao saem no JSON.
        assert "latitude" not in texto and "longitude" not in texto
        for a in ambiente.banco.avaliacoes.values():
            assert str(a["latitude"]) not in texto and str(a["longitude"]) not in texto
        # A trilha impressa e a do arquivo de log, nao uma linha montada.
        log = (tmp_path / "api.log").read_text(encoding="utf-8").splitlines()
        linhas = [t["linha_de_log"] for tr in relatorio["trilhas"] for t in tr["tentativas"]
                  if t["status"] in (200, 201)]
        assert linhas and all(li in log for li in linhas)
        assert all(f"linha de log: {li}" in impresso for li in linhas)


def _resposta_de_login(perfil: str, operador_id=None, token="tok"):
    r = MagicMock(status_code=200)
    r.json.return_value = {"access_token": f"{token}-{perfil}", "perfil": perfil, "operador_id": operador_id}
    return r


class TestAutenticacaoDosScripts:
    """F(2)/G(3): login e o padrao; o token local so com --token-local, e o relatorio diz qual foi."""

    def test_coleta_real_faz_login_por_padrao(self, monkeypatch):
        monkeypatch.setenv("SAFEFIELD_SENHA", "s3nha")
        with patch.object(coleta_real.requests, "post", return_value=_resposta_de_login("analista")) as post, \
             patch.object(coleta_real, "criar_token", side_effect=AssertionError("token local sem --token-local")):
            token, usuario, modo = coleta_real.autenticar(API_FALSA, "maria", token_local=False)
        assert (token, usuario, modo["modo"], modo["usuario"]) == ("tok-analista", "maria", "login", "maria")
        assert post.call_args.kwargs["json"] == {"usuario": "maria", "senha": "s3nha"}

    def test_coleta_real_recusa_login_de_outro_perfil(self, monkeypatch):
        monkeypatch.setenv("SAFEFIELD_SENHA", "s3nha")
        with patch.object(coleta_real.requests, "post", return_value=_resposta_de_login("gestor")), \
             pytest.raises(coleta_real.Interrompido, match="perfil 'gestor'"):
            coleta_real.autenticar(API_FALSA, "maria", token_local=False)

    def test_coleta_real_token_local_so_quando_pedido(self):
        with patch.object(coleta_real.requests, "post", side_effect=AssertionError("login com --token-local")):
            token, usuario, modo = coleta_real.autenticar(API_FALSA, "maria", token_local=True)
        assert usuario == "analista" and modo["modo"] == "token-local"
        assert token and "sem login" in modo["como"]

    def test_casos_de_uso_fazem_login_por_perfil(self, monkeypatch):
        for perfil in casos_de_uso.PERFIS:
            monkeypatch.setenv(f"SAFEFIELD_SENHA_{perfil.upper()}", f"senha-{perfil}")
        monkeypatch.setenv("SAFEFIELD_USUARIO_OPERADOR", "joao")

        def login(url, json=None, timeout=None):
            perfil = "operador" if json["usuario"] == "joao" else json["usuario"]
            assert json["senha"] == f"senha-{perfil}"
            return _resposta_de_login(perfil, "OP-0003" if perfil == "operador" else None)

        with patch.object(casos_de_uso.requests, "post", side_effect=login) as post, \
             patch.object(casos_de_uso, "criar_token", side_effect=AssertionError("token local sem --token-local")):
            tokens, usuarios, operador_id, modo = casos_de_uso.autenticar(API_FALSA, False, "OP-0015")
        assert post.call_count == len(casos_de_uso.PERFIS)
        assert usuarios == {"operador": "joao", "gestor": "gestor", "tecnico": "tecnico", "analista": "analista"}
        assert tokens["operador"] == "tok-operador"
        # O operador_id vem do login, nao do --operador.
        assert operador_id == "OP-0003" and modo["modo"] == "login"

    def test_casos_de_uso_recusam_perfil_trocado(self, monkeypatch):
        for perfil in casos_de_uso.PERFIS:
            monkeypatch.setenv(f"SAFEFIELD_SENHA_{perfil.upper()}", "x")
        with patch.object(casos_de_uso.requests, "post", return_value=_resposta_de_login("analista")), \
             pytest.raises(casos_de_uso.Interrompido, match="esperado 'operador'"):
            casos_de_uso.autenticar(API_FALSA, False, "OP-0015")

    def test_casos_de_uso_token_local_so_quando_pedido(self):
        with patch.object(casos_de_uso.requests, "post", side_effect=AssertionError("login com --token-local")):
            tokens, usuarios, operador_id, modo = casos_de_uso.autenticar(API_FALSA, True, "OP-0015")
        assert set(tokens) == set(casos_de_uso.PERFIS) and operador_id == "OP-0015"
        assert modo["modo"] == "token-local"


# --- O checador dos casos de uso ---------------------------------------------

def _item(eq: str, operador_id, latitude=-12.5, total=3) -> dict:
    return {"equipamento_id": eq, "operador_id": operador_id, "latitude": latitude,
            "longitude": None if latitude is None else -55.7, "total_avaliacoes": total}


def _detalhe(operador_id=None, latitude=None, valor_shap=None) -> dict:
    return {
        "ultima_avaliacao": {"avaliacao_id": 7, "operador_id": operador_id, "latitude": latitude,
                             "longitude": latitude},
        "predicao": {"top_fatores_shap": [
            {"feature": "latitude", "valor": valor_shap, "shap_value": 1.2, "grupo": "geografico"},
            {"feature": "horas_operacao", "valor": 6.0, "shap_value": 0.8, "grupo": "operacional"},
        ]},
    }


class TestChecadorDosCasosDeUso:
    """scripts/evidencias/casos_de_uso: LGPD, alertas e recusas nao passam por vacuidade."""

    def test_lgpd_mascarado_na_lista_e_no_detalhe_passa(self):
        itens = [_item("EQ-1", "OP-0015"), _item("EQ-2", None, latitude=None)]
        passo = casos_de_uso.conferir_lgpd(itens, {"EQ-2": _detalhe()}, "OP-0015")
        assert passo["ok"], passo
        assert "fatores de posicao no top SHAP: 1" in passo["visto"]

    def test_lgpd_sem_caso_mascaravel_e_nao_demonstrado(self):
        itens = [_item("EQ-1", "OP-0015"), _item("EQ-3", None, latitude=None, total=0)]
        passo = casos_de_uso.conferir_lgpd(itens, {}, "OP-0015")
        assert not passo["ok"] and "nao demonstrado" in passo["visto"]

    def test_lgpd_sem_detalhe_conferido_nao_passa(self):
        passo = casos_de_uso.conferir_lgpd([_item("EQ-2", None, latitude=None)], {}, "OP-0015")
        assert not passo["ok"] and "nao demonstrado" in passo["visto"]

    @pytest.mark.parametrize("itens,detalhe,vazou", [
        ([_item("EQ-2", "OP-0003", latitude=None)], _detalhe(), "lista EQ-2: operador_id"),
        ([_item("EQ-2", None)], _detalhe(), "lista EQ-2: latitude"),
        ([_item("EQ-2", None, latitude=None)], _detalhe(operador_id="OP-0003"), "detalhe EQ-2: operador_id"),
        ([_item("EQ-2", None, latitude=None)], _detalhe(latitude=-12.5), "detalhe EQ-2: longitude"),
        ([_item("EQ-2", None, latitude=None)], _detalhe(valor_shap=-12.5), "detalhe EQ-2: shap:latitude"),
        ([_item("EQ-2", None, latitude=None)], {"ultima_avaliacao": None}, "ultima_avaliacao ausente"),
    ], ids=["lista-operador", "lista-posicao", "detalhe-operador", "detalhe-posicao", "detalhe-shap",
            "detalhe-vazio"])
    def test_lgpd_vazamento_reprova(self, itens, detalhe, vazou):
        passo = casos_de_uso.conferir_lgpd(itens, {"EQ-2": detalhe}, "OP-0015")
        assert not passo["ok"] and vazou in passo["visto"], passo

    def test_alertas_vazio_e_nao_demonstrado(self):
        passo = casos_de_uso.conferir_alertas({"ok": True}, {"total": 0, "itens": []}, {"EQ-1"})
        assert not passo["ok"] and "nao demonstrado" in passo["visto"]

    def test_alertas_fora_do_recorte_reprova_e_dentro_passa(self):
        alertas = {"itens": [{"equipamento_id": "EQ-1"}, {"equipamento_id": "EQ-9"}]}
        assert not casos_de_uso.conferir_alertas({"ok": True}, alertas, {"EQ-1"})["ok"]
        assert casos_de_uso.conferir_alertas({"ok": True}, {"itens": alertas["itens"][:1]}, {"EQ-1"})["ok"]

    USUARIOS = {"operador": "joao", "gestor": "gestor", "tecnico": "tecnico", "analista": "analista"}
    SUCESSO = [{"status": "sucesso", "usuario": "joao", "perfil": "operador", "modelo_versao": "v"}]

    def _recusa(self, perfil):
        return {"status": "erro", "usuario": perfil, "perfil": perfil,
                "detalhe": f"Perfil '{perfil}' nao envia leituras."}

    def test_auditoria_uma_recusa_por_perfil_passa(self):
        recusas = [self._recusa("gestor"), self._recusa("tecnico")]
        ok, visto = casos_de_uso.conferir_auditoria(self.SUCESSO, recusas, self.USUARIOS, 7)
        assert ok, visto

    @pytest.mark.parametrize("recusas", [
        [],
        ["gestor"],
        ["gestor", "tecnico", "tecnico"],
    ], ids=["nenhuma", "falta-tecnico", "tecnico-duplicado"])
    def test_auditoria_sem_exatamente_uma_por_perfil_reprova(self, recusas):
        ok, _ = casos_de_uso.conferir_auditoria(
            self.SUCESSO, [self._recusa(p) for p in recusas], self.USUARIOS, 7)
        assert not ok

    def test_auditoria_sem_o_sucesso_do_operador_reprova(self):
        recusas = [self._recusa("gestor"), self._recusa("tecnico")]
        assert not casos_de_uso.conferir_auditoria([], recusas, self.USUARIOS, 7)[0]
        assert not casos_de_uso.conferir_auditoria(self.SUCESSO, recusas, self.USUARIOS, None)[0]

    def test_instante_do_servidor_vem_do_header_date(self):
        r = SimpleNamespace(headers={"Date": "Mon, 28 Sep 2026 20:31:07 GMT"})
        assert casos_de_uso.instante_do_servidor(r) == datetime(2026, 9, 28, 20, 31, 7, tzinfo=timezone.utc)
        assert casos_de_uso.instante_do_servidor(SimpleNamespace(headers={})) is None
