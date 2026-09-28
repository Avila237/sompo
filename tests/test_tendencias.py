"""
Testes de GET /tendencias (BRA-459 · S4-26): serie de score por grupo nos tres
eixos (equipamento, regiao, operacao).

O repositorio e mockado: nem Supabase nem rede sao chamados.
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


def _aval(dia, score, eq="EQ-0001", op="colheita", lat=-12.0, lon=-54.0, hora="10:00:00"):
    return {
        "avaliacao_id": hash((dia, score, eq, op, hora)) & 0xFFFF,
        "equipamento_id": eq,
        "operador_id": "OP-0001",
        "risco_score": score,
        "faixa_risco": "medio",
        "timestamp": f"{dia}T{hora}+00:00",
        "latitude": lat,
        "longitude": lon,
        "tipo_operacao": op,
    }


def _tendencias(avals, **kw):
    with patch("backend.services.consultas.repo.listar_avaliacoes_resumo", return_value=avals):
        return consultas.tendencias(**kw)


# ---------------------------------------------------------------------------
# Janela: dias COM dados, na base inteira
# ---------------------------------------------------------------------------

class TestJanela:
    def test_janela_sao_os_ultimos_dias_com_dados_da_base(self):
        avals = [_aval(d, 50) for d in ("2025-01-01", "2025-01-05", "2025-03-10", "2026-08-24")]
        r = _tendencias(avals, eixo="operacao", dias=3)
        assert r["janela"] == {"inicio": "2025-01-05", "fim": "2026-08-24", "dias_com_dados": 3}

    def test_base_menor_que_a_janela_informa_dias_com_dados(self):
        avals = [_aval("2025-01-01", 40), _aval("2025-01-02", 60)]
        r = _tendencias(avals, eixo="operacao", dias=30)
        assert r["dias"] == 30
        assert r["janela"]["dias_com_dados"] == 2

    def test_base_vazia_devolve_series_vazias(self):
        r = _tendencias([], eixo="equipamento", dias=30)
        assert r["series"] == []
        assert r["janela"] == {"inicio": None, "fim": None, "dias_com_dados": 0}

    def test_dado_fora_da_janela_nao_entra_na_media_do_grupo(self):
        avals = [_aval("2025-01-01", 100), _aval("2025-01-02", 20), _aval("2025-01-03", 40)]
        r = _tendencias(avals, eixo="operacao", dias=2)
        serie = r["series"][0]
        assert serie["score_medio"] == 30.0
        assert serie["avaliacoes"] == 2


# ---------------------------------------------------------------------------
# Pontos: lacuna em vez de zero
# ---------------------------------------------------------------------------

class TestPontos:
    def test_grupo_sem_avaliacao_no_dia_nao_ganha_ponto(self):
        avals = [
            _aval("2025-01-01", 50, op="colheita"),
            _aval("2025-01-02", 60, op="colheita"),
            _aval("2025-01-02", 30, op="plantio"),
            _aval("2025-01-03", 70, op="colheita"),
        ]
        r = _tendencias(avals, eixo="operacao", dias=30)
        plantio = next(s for s in r["series"] if s["chave"] == "plantio")
        assert [p["dia"] for p in plantio["pontos"]] == ["2025-01-02"]

    def test_ponto_e_media_do_dia_e_vem_em_ordem_de_dia(self):
        avals = [
            _aval("2025-01-02", 10, hora="09:00:00"),
            _aval("2025-01-01", 50),
            _aval("2025-01-02", 20, hora="15:00:00"),
        ]
        r = _tendencias(avals, eixo="operacao", dias=30)
        pontos = r["series"][0]["pontos"]
        assert pontos == [
            {"dia": "2025-01-01", "score_medio": 50.0, "avaliacoes": 1},
            {"dia": "2025-01-02", "score_medio": 15.0, "avaliacoes": 2},
        ]


# ---------------------------------------------------------------------------
# Agrupamento por eixo
# ---------------------------------------------------------------------------

class TestEixos:
    def test_equipamento_agrupa_por_id(self):
        avals = [_aval("2025-01-01", 50, eq="EQ-0001"), _aval("2025-01-01", 70, eq="EQ-0002")]
        r = _tendencias(avals, eixo="equipamento", dias=30)
        assert {s["chave"] for s in r["series"]} == {"EQ-0001", "EQ-0002"}
        assert all(s["rotulo"] == s["chave"] for s in r["series"])

    def test_operacao_sem_tipo_entra_como_desconhecida(self):
        r = _tendencias([_aval("2025-01-01", 50, op=None)], eixo="operacao", dias=30)
        assert r["series"][0]["chave"] == "desconhecida"

    def test_regiao_usa_a_posicao_da_propria_avaliacao(self):
        """O mesmo equipamento em dois lugares gera pontos em duas regioes."""
        avals = [
            _aval("2025-01-01", 50, eq="EQ-0001", lat=-12.0, lon=-54.0),
            _aval("2025-01-02", 80, eq="EQ-0001", lat=-24.0, lon=-51.0),
        ]
        r = _tendencias(avals, eixo="regiao", dias=30)
        assert {s["rotulo"] for s in r["series"]} == {"12°S 54°O", "24°S 51°O"}

    def test_regiao_descarta_avaliacao_sem_coordenada(self):
        avals = [_aval("2025-01-01", 50, lat=None, lon=None), _aval("2025-01-01", 60)]
        r = _tendencias(avals, eixo="regiao", dias=30)
        assert len(r["series"]) == 1
        assert r["series"][0]["avaliacoes"] == 1

    def test_eixo_invalido_levanta_erro(self):
        with pytest.raises(ValueError):
            _tendencias([_aval("2025-01-01", 50)], eixo="cliente", dias=30)


# ---------------------------------------------------------------------------
# Selecao de grupos: limite, ordem e chave
# ---------------------------------------------------------------------------

class TestSelecao:
    AVALS = [
        _aval("2025-01-01", 20, eq="EQ-0001"),
        _aval("2025-01-01", 90, eq="EQ-0002"),
        _aval("2025-01-01", 60, eq="EQ-0003"),
        _aval("2025-01-01", 60, eq="EQ-0004"),
        _aval("2025-01-02", 60, eq="EQ-0004"),
    ]

    def test_limite_e_ordem_por_score_medio_desc(self):
        r = _tendencias(self.AVALS, eixo="equipamento", dias=30, limite=2)
        assert [s["chave"] for s in r["series"]] == ["EQ-0002", "EQ-0004"]

    def test_empate_de_score_desempata_por_mais_avaliacoes(self):
        r = _tendencias(self.AVALS, eixo="equipamento", dias=30, limite=4)
        assert [s["chave"] for s in r["series"]][1:3] == ["EQ-0004", "EQ-0003"]

    def test_chave_restringe_a_um_grupo_e_ignora_limite(self):
        r = _tendencias(self.AVALS, eixo="equipamento", dias=30, limite=1, chave="EQ-0001")
        assert [s["chave"] for s in r["series"]] == ["EQ-0001"]

    def test_chave_inexistente_devolve_series_vazias(self):
        r = _tendencias(self.AVALS, eixo="equipamento", dias=30, chave="EQ-9999")
        assert r["series"] == []


# ---------------------------------------------------------------------------
# Rota HTTP
# ---------------------------------------------------------------------------

@pytest.fixture
def auth() -> dict:
    t, _ = criar_token("analista", "analista")
    return {"Authorization": f"Bearer {t}"}


class TestRota:
    def test_sem_token_recebe_401(self):
        assert client.get("/tendencias?eixo=operacao").status_code == 401

    @pytest.mark.parametrize(
        "query",
        [
            "",                               # eixo obrigatorio
            "eixo=cliente",                   # fora do enum
            "eixo=operacao&dias=0",
            "eixo=operacao&dias=366",
            "eixo=operacao&limite=0",
            "eixo=operacao&limite=21",
        ],
    )
    def test_parametro_invalido_recebe_422(self, auth, query):
        with patch("backend.services.consultas.repo.listar_avaliacoes_resumo", return_value=[]):
            r = client.get(f"/tendencias?{query}", headers=auth)
        assert r.status_code == 422, query

    def test_resposta_tem_o_shape_do_contrato(self, auth):
        avals = [_aval("2025-01-01", 40), _aval("2025-01-02", 60)]
        with patch("backend.services.consultas.repo.listar_avaliacoes_resumo", return_value=avals):
            r = client.get("/tendencias?eixo=operacao&dias=30&limite=5", headers=auth)
        assert r.status_code == 200, r.text
        corpo = r.json()
        assert set(corpo) == {"eixo", "dias", "janela", "series"}
        assert corpo["eixo"] == "operacao"
        serie = corpo["series"][0]
        assert set(serie) == {"chave", "rotulo", "score_medio", "avaliacoes", "pontos"}
        assert set(serie["pontos"][0]) == {"dia", "score_medio", "avaliacoes"}
