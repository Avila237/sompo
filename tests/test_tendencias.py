"""
GET /tendencias: series de score por grupo, nos tres eixos que o enunciado da
Sprint 4 pede (equipamento, regiao, tipo de operacao).

O repositorio e mockado: a agregacao e toda em memoria sobre
listar_avaliacoes_resumo(), entao o dado de entrada e montado aqui.
"""

import os
import sys
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.api.main import app  # noqa: E402
from backend.core.security import criar_token  # noqa: E402
from backend.services import consultas  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


def _aval(dia, eq, score, op="colheita", lat=-24.1, lon=-51.2):
    return {
        "avaliacao_id": hash((dia, eq, score)) & 0xFFFF,
        "equipamento_id": eq,
        "operador_id": "OP-0001",
        "risco_score": score,
        "faixa_risco": consultas._faixa(score),
        "timestamp": f"{dia}T10:00:00+00:00",
        "latitude": lat,
        "longitude": lon,
        "tipo_operacao": op,
    }


# Quatro dias com dados. EQ-0001 aparece nos dias 1, 2 e 4 (lacuna no dia 3).
BASE = [
    _aval("2026-01-01", "EQ-0001", 80.0),
    _aval("2026-01-02", "EQ-0001", 70.0),
    _aval("2026-01-04", "EQ-0001", 60.0),
    _aval("2026-01-01", "EQ-0002", 20.0, op="transporte"),
    _aval("2026-01-03", "EQ-0002", 30.0, op="transporte"),
    _aval("2026-01-03", "EQ-0003", 50.0, op="plantio", lat=-12.0, lon=-55.0),
]


@pytest.fixture
def base():
    with patch.object(consultas.repo, "listar_avaliacoes_resumo", return_value=BASE):
        yield


def _serie(resp, chave):
    return next(s for s in resp["series"] if s["chave"] == chave)


class TestJanela:
    def test_janela_e_dos_ultimos_dias_com_dados_da_base_inteira(self, base):
        r = consultas.tendencias("equipamento", dias=2, limite=10)
        assert r["janela"] == {"inicio": "2026-01-03", "fim": "2026-01-04", "dias_com_dados": 2}
        # EQ-0001 so tem o dia 4 dentro da janela
        assert [p["dia"] for p in _serie(r, "EQ-0001")["pontos"]] == ["2026-01-04"]

    def test_dias_maior_que_a_base_devolve_o_que_existe(self, base):
        r = consultas.tendencias("equipamento", dias=30, limite=10)
        assert r["janela"]["dias_com_dados"] == 4
        assert r["dias"] == 30

    def test_score_do_grupo_e_calculado_so_na_janela(self, base):
        r = consultas.tendencias("equipamento", dias=2, limite=10)
        s = _serie(r, "EQ-0001")
        assert s["score_medio"] == 60.0
        assert s["avaliacoes"] == 1


class TestPontos:
    def test_dia_sem_avaliacao_do_grupo_vira_lacuna_nao_zero(self, base):
        r = consultas.tendencias("equipamento", dias=30, limite=10)
        pontos = _serie(r, "EQ-0001")["pontos"]
        assert [p["dia"] for p in pontos] == ["2026-01-01", "2026-01-02", "2026-01-04"]
        assert all(p["score_medio"] > 0 for p in pontos)

    def test_pontos_em_ordem_crescente_de_dia(self, base):
        r = consultas.tendencias("operacao", dias=30, limite=10)
        for s in r["series"]:
            dias = [p["dia"] for p in s["pontos"]]
            assert dias == sorted(dias)


class TestEixos:
    def test_eixo_operacao_agrupa_por_tipo(self, base):
        r = consultas.tendencias("operacao", dias=30, limite=10)
        assert {s["chave"] for s in r["series"]} == {"colheita", "transporte", "plantio"}
        assert _serie(r, "transporte")["avaliacoes"] == 2

    def test_operacao_ausente_entra_como_desconhecida(self):
        base = [*BASE, {**_aval("2026-01-04", "EQ-0009", 40.0), "tipo_operacao": None}]
        with patch.object(consultas.repo, "listar_avaliacoes_resumo", return_value=base):
            r = consultas.tendencias("operacao", dias=30, limite=10)
        assert "desconhecida" in {s["chave"] for s in r["series"]}

    def test_eixo_regiao_usa_a_posicao_da_propria_avaliacao(self, base):
        r = consultas.tendencias("regiao", dias=30, limite=10)
        chaves = {s["chave"] for s in r["series"]}
        # -24.1,-51.2 cai na celula 24°S 51°O; -12,-55 na celula 12°S 54°O
        assert chaves == {"24°S 51°O", "12°S 54°O"}
        s = _serie(r, "24°S 51°O")
        assert s["rotulo"] == s["chave"]

    def test_regiao_ignora_avaliacao_sem_coordenada(self):
        base = [*BASE, {**_aval("2026-01-04", "EQ-0009", 40.0), "latitude": None}]
        with patch.object(consultas.repo, "listar_avaliacoes_resumo", return_value=base):
            r = consultas.tendencias("regiao", dias=30, limite=10)
        assert sum(s["avaliacoes"] for s in r["series"]) == len(BASE)


class TestSelecao:
    def test_limite_mantem_os_grupos_de_maior_score(self, base):
        r = consultas.tendencias("equipamento", dias=30, limite=2)
        assert [s["chave"] for s in r["series"]] == ["EQ-0001", "EQ-0003"]

    def test_series_em_ordem_decrescente_de_score(self, base):
        r = consultas.tendencias("equipamento", dias=30, limite=10)
        scores = [s["score_medio"] for s in r["series"]]
        assert scores == sorted(scores, reverse=True)

    def test_chave_filtra_um_grupo_e_ignora_limite(self, base):
        r = consultas.tendencias("equipamento", dias=30, limite=1, chave="EQ-0002")
        assert [s["chave"] for s in r["series"]] == ["EQ-0002"]

    def test_chave_inexistente_devolve_series_vazia(self, base):
        r = consultas.tendencias("equipamento", dias=30, limite=5, chave="EQ-9999")
        assert r["series"] == []

    def test_base_vazia_devolve_series_vazia(self):
        with patch.object(consultas.repo, "listar_avaliacoes_resumo", return_value=[]):
            r = consultas.tendencias("equipamento", dias=30, limite=5)
        assert r["series"] == []
        assert r["janela"]["dias_com_dados"] == 0


class TestRota:
    @pytest.fixture
    def auth(self):
        token, _ = criar_token("analista", "analista")
        return {"Authorization": f"Bearer {token}"}

    def test_sem_token_recebe_401(self):
        assert client.get("/tendencias?eixo=operacao").status_code == 401

    @pytest.mark.parametrize(
        "query",
        ["", "eixo=cor", "eixo=operacao&dias=0", "eixo=operacao&dias=366",
         "eixo=operacao&limite=0", "eixo=operacao&limite=21"],
    )
    def test_parametro_invalido_recebe_422(self, auth, query):
        assert client.get(f"/tendencias?{query}", headers=auth).status_code == 422

    def test_resposta_tem_o_shape_do_contrato(self, auth, base):
        r = client.get("/tendencias?eixo=operacao&dias=30&limite=5", headers=auth)
        assert r.status_code == 200
        corpo = r.json()
        assert set(corpo) == {"eixo", "dias", "janela", "series"}
        assert corpo["eixo"] == "operacao"
        serie = corpo["series"][0]
        assert set(serie) == {"chave", "rotulo", "score_medio", "avaliacoes", "pontos"}
        assert set(serie["pontos"][0]) == {"dia", "score_medio", "avaliacoes"}


class TestCelulaCompartilhada:
    def test_por_regiao_e_tendencias_nomeiam_a_regiao_igual(self, base):
        """As duas rotas usam a mesma celula de 3 graus: o rotulo nao pode divergir."""
        equipamento = {"latitude": -24.1, "longitude": -51.2, "risco_score": 70.0}
        with patch.object(consultas, "listar_equipamentos", return_value=[equipamento]):
            (regiao,) = consultas.agregado_por_regiao()
        chaves = {s["chave"] for s in consultas.tendencias("regiao", dias=30, limite=10)["series"]}
        assert regiao["nome"] == "24°S 51°O"
        assert regiao["nome"] in chaves
