"""
scripts/evidencias/casos_de_uso.py de ponta a ponta (S4-28), offline: login
por perfil, a API real em memoria e um banco falso que responde as leituras e
a consulta de auditoria. Prova a orquestracao que os testes das funcoes puras
nao alcancam: saida 0, uma so avaliacao gravada, modo login no relatorio,
filtro da auditoria pelo instante do servidor e nenhuma posicao no JSON.
"""

import json
import random
import uuid
from copy import deepcopy
from datetime import datetime
from email.utils import formatdate
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.core.security import criar_token
from backend.db import repository
from scripts import simulate_telemetry as simulador
from scripts.evidencias import casos_de_uso
from tests.conftest import SENHAS
from tests.test_confiabilidade_coleta import (
    CADASTRO, Injetor, OpenMeteoFalsa, RepositorioFalso, client,
)

API = "http://api.teste"


class BancoComLeitura(RepositorioFalso):
    """O falso da coleta, mais as leituras que as personas fazem."""

    def operador_existe(self, operador_id):
        return operador_id in ("OP-0001", "OP-0002", "OP-0003", "OP-0015")

    def listar_equipamentos(self):
        return [deepcopy(e) for e in CADASTRO.values()]

    def listar_avaliacoes_resumo(self):
        return [deepcopy(a) for a in self.avaliacoes.values()]

    def ultima_avaliacao(self, eq):
        dele = [a for a in self.avaliacoes.values() if a["equipamento_id"] == eq]
        return deepcopy(max(dele, key=lambda a: a["timestamp"])) if dele else None


class Consulta:
    def __init__(self, linhas):
        self.linhas = list(linhas)
        self.filtros = []

    def select(self, *_a, **_k):
        return self

    def eq(self, c, v):
        self.filtros.append(("eq", c, v))
        self.linhas = [x for x in self.linhas if x.get(c) == v]
        return self

    def in_(self, c, vs):
        self.filtros.append(("in", c, list(vs)))
        self.linhas = [x for x in self.linhas if x.get(c) in set(vs)]
        return self

    def gte(self, c, v):
        self.filtros.append(("gte", c, v))
        limite = datetime.fromisoformat(v.replace("Z", "+00:00"))
        self.linhas = [x for x in self.linhas if x[c] >= limite]
        return self

    def execute(self):
        return SimpleNamespace(data=deepcopy(self.linhas))


def _com_date(r):
    r.headers["Date"] = formatdate(usegmt=True)
    return r


def _seed(banco):
    """Leituras gravadas pela propria API, como analista."""
    token, _ = criar_token("analista", "analista")
    h = {"Authorization": f"Bearer {token}"}
    rng = random.Random(5)
    plano = [("EQ-0001", "OP-0015", "normal"), ("EQ-0002", "OP-0015", "critico"),
             ("EQ-0001", "OP-0003", "critico"), ("EQ-0004", "OP-0002", "critico"),
             ("EQ-0002", "OP-0015", "critico")]
    with patch.object(simulador, "random", rng), patch.object(simulador, "_OPERADORES", ["x"]):
        for eq, op, cen in plano:
            leitura, _ = simulador.gerar_leitura([CADASTRO[eq]], cen)
            leitura["operador_id"] = op
            leitura["leitura_id"] = str(uuid.UUID(int=rng.getrandbits(128), version=4))
            r = client.post("/avaliacoes", json=leitura, headers=h)
            assert r.status_code == 201, r.text


@pytest.fixture
def mundo(monkeypatch):
    inj = Injetor()
    banco = BancoComLeitura(inj)
    om = OpenMeteoFalsa(inj)
    consultas_feitas = []

    def get_client():
        def table(nome):
            assert nome == "auditoria", nome
            q = Consulta(banco.auditoria)
            consultas_feitas.append(q)
            return q
        return SimpleNamespace(table=table)

    with patch.multiple(
        repository,
        get_client=get_client,
        buscar_equipamento=banco.buscar_equipamento,
        operador_existe=banco.operador_existe,
        buscar_por_leitura=banco.buscar_por_leitura,
        registrar_avaliacao=banco.registrar_avaliacao,
        buscar_avaliacao=banco.buscar_avaliacao,
        predicao_de=banco.predicao_de,
        inserir_auditoria=banco.inserir_auditoria,
        invalidar_cache=banco.invalidar_cache,
        listar_equipamentos=banco.listar_equipamentos,
        listar_avaliacoes_resumo=banco.listar_avaliacoes_resumo,
        ultima_avaliacao=banco.ultima_avaliacao,
    ), patch("backend.services.clima.requests.get", om):
        _seed(banco)
        for p in casos_de_uso.PERFIS:
            monkeypatch.setenv(f"SAFEFIELD_SENHA_{p.upper()}", SENHAS[p])
        yield banco, consultas_feitas, om


def _rotas(om):
    def get(url, timeout=None, **kw):
        if url.startswith('https://api.open-meteo.com'):
            return om(url, timeout=timeout, **kw)
        assert url.startswith(API)
        return _com_date(client.get(url[len(API):], **kw))

    def post(url, json=None, headers=None, timeout=None):
        assert url.startswith(API)
        return _com_date(client.post(url[len(API):], json=json, headers=headers))

    def request(metodo, url, timeout=None, headers=None, json=None):
        assert url.startswith(API)
        return _com_date(client.request(metodo, url[len(API):], headers=headers, json=json))

    return get, post, request


def test_casos_de_uso_de_ponta_a_ponta(mundo, tmp_path):
    banco, consultas, om = mundo
    get, post, request = _rotas(om)
    saida = tmp_path / "casos.json"
    antes = len(banco.avaliacoes)
    with patch.object(casos_de_uso.requests, "get", get), \
         patch.object(casos_de_uso.requests, "post", post), \
         patch.object(casos_de_uso.requests, "request", request), \
         patch.object(casos_de_uso, "criar_token", side_effect=AssertionError("token local")):
        codigo = casos_de_uso.main(["--api", API, "--seed", "1", "--saida", str(saida)])
    rel = json.loads(saida.read_text())
    falhos = [(c["perfil"], p["chamada"], p.get("visto"), p.get("detalhe"))
              for c in rel["personas"] for p in c["passos"] if not p["ok"]]
    assert codigo == 0, falhos
    assert len(banco.avaliacoes) == antes + 1
    assert rel["autenticacao"]["modo"] == "login"
    # A query da auditoria filtrou por equipamento, status, usuarios e instante.
    recusas = [q for q in consultas if any(f[0] == "gte" for f in q.filtros)]
    assert len(recusas) == 1
    filtros = {(f[0], f[1]) for f in recusas[0].filtros}
    assert {("eq", "equipamento_id"), ("gte", "timestamp")} <= filtros, recusas[0].filtros
    texto = saida.read_text()
    assert "latitude\": -" not in texto
