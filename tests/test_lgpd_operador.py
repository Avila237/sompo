"""
Minimizacao de dados nas rotas de leitura (LGPD).

O operador ve os equipamentos que ja operou (S4-18), mas a avaliacao de um
deles pode ser de outro operador. Dessa, ele nao recebe quem operou nem onde:
operador_id, latitude e longitude saem null. As proprias chegam intactas, e
analista, gestor e tecnico veem tudo.

A posicao e feature do modelo, entao tambem apareceria no 'valor' do fator
SHAP e no criterio da recomendacao do fator dominante: os testes procuram o
dado na resposta inteira, nao so no campo.

leitura_id e payload_hash sao internos da idempotencia (S4-12) e nao saem em
nenhuma resposta de leitura, para nenhum perfil.

O repositorio e mockado; rota, recorte e servico sao os reais.
"""

import copy
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

PROPRIO = "OP-0015"
OUTRO = "OP-0099"

# Coordenadas distintas o bastante para a busca no texto da resposta nao casar por acaso.
POS_PROPRIA = (-12.345678, -55.123456)
POS_OUTRO = (-23.456789, -44.987654)

# EQ-0042: o operador ja operou, mas a ultima avaliacao e de outro operador.
# EQ-0043: a ultima avaliacao e do proprio operador.
# EQ-0099: so outro operador operou; fora do recorte.
MISTO, PROPRIO_EQ, ALHEIO = "EQ-0042", "EQ-0043", "EQ-0099"

LEITURA_ID = "11111111-2222-3333-4444-555555555555"
PAYLOAD_HASH = "f" * 64


def _auth(perfil: str, operador_id: str | None = None) -> dict:
    token, _ = criar_token(perfil, perfil, operador_id)
    return {"Authorization": f"Bearer {token}"}


AUTH = {
    "analista": _auth("analista"),
    "gestor": _auth("gestor"),
    "tecnico": _auth("tecnico"),
    "operador": _auth("operador", PROPRIO),
}
FROTA = ("analista", "gestor", "tecnico")


def _equipamento(equipamento_id: str) -> dict:
    return {
        "equipamento_id": equipamento_id,
        "tipo_equipamento": "trator",
        "modelo_equipamento": "John Deere 7J195",
        "categoria_manual": "trator_operacao",
        "idade_equipamento": 5,
        "historico_sinistros": 1,
        "tem_iot": True,
        "intervalo_manut_recomendado_dias": 180,
        "intervalo_manut_recomendado_horas": 500,
    }


def _resumo(avaliacao_id, equipamento_id, operador_id, dia, pos, score=80.0):
    return {
        "avaliacao_id": avaliacao_id,
        "equipamento_id": equipamento_id,
        "operador_id": operador_id,
        "risco_score": score,
        "faixa_risco": "alto" if score > 66 else "medio",
        "timestamp": f"2026-09-{dia:02d}T10:00:00+00:00",
        "latitude": pos[0],
        "longitude": pos[1],
        "tipo_operacao": "colheita",
        # Como na linha real: se o servico passar a espalhar a linha, a
        # idempotencia vaza e test_idempotencia_nao_sai_nas_listas falha.
        "leitura_id": f"00000000-0000-0000-0000-{avaliacao_id:012d}",
        "payload_hash": "a" * 64,
    }


RESUMO = [
    _resumo(1, MISTO, PROPRIO, 1, POS_PROPRIA, score=50.0),
    _resumo(2, MISTO, OUTRO, 2, POS_OUTRO),
    _resumo(3, PROPRIO_EQ, PROPRIO, 3, POS_PROPRIA),
    _resumo(4, ALHEIO, OUTRO, 4, POS_OUTRO),
]


def _linha_completa(resumo: dict) -> dict:
    """Linha de avaliacoes como o select('*') devolve, com as colunas internas."""
    return {
        **resumo,
        # Sem campo que dispare regra: a recomendacao sai do fator dominante.
        "velocidade_kmh": 5.0,
        "score_operador_historico": 61.0,
        "fonte": "telemetria",
        "clima_origem": "open-meteo",
        "leitura_id": LEITURA_ID,
        "payload_hash": PAYLOAD_HASH,
    }


def _ultima(equipamento_id: str) -> dict | None:
    do_eq = [a for a in RESUMO if a["equipamento_id"] == equipamento_id]
    return _linha_completa(max(do_eq, key=lambda a: a["timestamp"])) if do_eq else None


def _predicao(avaliacao_id: int) -> dict:
    # A posicao e o fator que mais empurra o risco: vira o criterio do fator dominante.
    lat = next(a["latitude"] for a in RESUMO if a["avaliacao_id"] == avaliacao_id)
    return {
        "avaliacao_id": avaliacao_id,
        "risco_score_predito": 80.0,
        "faixa_predita": "alto",
        "top_fatores_shap": [
            {"feature": "latitude", "valor": lat, "shap_value": 9.5, "grupo": "geografico"},
            {"feature": "velocidade_kmh", "valor": 5.0, "shap_value": 2.0, "grupo": "operacional"},
        ],
        "contribuicoes_por_grupo": {"geografico": 9.5, "operacional": 2.0},
        "modelo_versao": "xgboost-v1-baseline",
    }


@pytest.fixture
def base():
    repo = consultas.repo
    equipamentos = [_equipamento(e) for e in (MISTO, PROPRIO_EQ, ALHEIO)]
    with patch.object(repo, "listar_equipamentos", return_value=equipamentos), \
         patch.object(repo, "listar_avaliacoes_resumo", return_value=RESUMO), \
         patch.object(repo, "buscar_equipamento", side_effect=_equipamento), \
         patch.object(repo, "ultima_avaliacao", side_effect=_ultima), \
         patch.object(repo, "predicao_de", side_effect=_predicao):
        yield


def _item(resp, equipamento_id: str) -> dict:
    return next(e for e in resp.json()["itens"] if e["equipamento_id"] == equipamento_id)


def _na_resposta(resp, *valores) -> list:
    """Valores que aparecem em algum lugar da resposta; vazio quando nenhum aparece."""
    return [v for v in valores if str(v) in resp.text]


class TestEquipamentos:
    def test_operador_ve_os_proprios_campos(self, base):
        r = client.get("/equipamentos", headers=AUTH["operador"])
        assert r.status_code == 200
        item = _item(r, PROPRIO_EQ)
        assert (item["operador_id"], item["latitude"], item["longitude"]) == (PROPRIO, *POS_PROPRIA)

    def test_operador_recebe_mascarada_a_avaliacao_de_outro(self, base):
        r = client.get("/equipamentos", headers=AUTH["operador"])
        item = _item(r, MISTO)
        assert (item["operador_id"], item["latitude"], item["longitude"]) == (None, None, None)
        # So os tres campos: o resto da linha segue igual ao da frota.
        assert item["risco_score"] == 80.0
        assert item["ultima_avaliacao"] == "2026-09-02T10:00:00+00:00"
        assert _na_resposta(r, OUTRO, *POS_OUTRO) == []

    @pytest.mark.parametrize("perfil", FROTA)
    def test_frota_ve_tudo(self, base, perfil):
        r = client.get("/equipamentos", headers=AUTH[perfil])
        item = _item(r, MISTO)
        assert (item["operador_id"], item["latitude"], item["longitude"]) == (OUTRO, *POS_OUTRO)
        assert {e["equipamento_id"] for e in r.json()["itens"]} == {MISTO, PROPRIO_EQ, ALHEIO}


class TestAlertas:
    def test_operador_ve_o_proprio_e_mascarado_o_de_outro(self, base):
        r = client.get("/alertas?faixa_minima=baixo&limite=100", headers=AUTH["operador"])
        assert r.status_code == 200
        por_id = {a["avaliacao_id"]: a for a in r.json()["itens"]}
        assert set(por_id) == {1, 2, 3}, "recorte: o alerta do equipamento alheio nao entra"
        assert por_id[1]["operador_id"] == PROPRIO
        assert por_id[3]["operador_id"] == PROPRIO
        assert por_id[2]["operador_id"] is None
        assert _na_resposta(r, OUTRO) == []

    def test_mascarar_nao_acrescenta_campo_ao_alerta(self, base):
        """O alerta nao traz posicao; mascarar nao pode criar latitude/longitude nele."""
        frota = client.get("/alertas?faixa_minima=baixo", headers=AUTH["analista"]).json()
        operador = client.get("/alertas?faixa_minima=baixo", headers=AUTH["operador"]).json()
        assert {frozenset(a) for a in operador["itens"]} == {frozenset(frota["itens"][0])}

    @pytest.mark.parametrize("perfil", FROTA)
    def test_frota_ve_tudo(self, base, perfil):
        r = client.get("/alertas?faixa_minima=baixo&limite=100", headers=AUTH[perfil])
        por_id = {a["avaliacao_id"]: a for a in r.json()["itens"]}
        assert por_id[2]["operador_id"] == OUTRO
        assert por_id[4]["operador_id"] == OUTRO


class TestDetalhe:
    def test_operador_ve_a_propria_avaliacao_intacta(self, base):
        r = client.get(f"/equipamentos/{PROPRIO_EQ}", headers=AUTH["operador"])
        assert r.status_code == 200
        corpo = r.json()
        ultima = corpo["ultima_avaliacao"]
        assert (ultima["operador_id"], ultima["latitude"], ultima["longitude"]) == (PROPRIO, *POS_PROPRIA)
        assert corpo["predicao"]["top_fatores_shap"][0]["valor"] == POS_PROPRIA[0]
        (rec,) = corpo["recomendacoes"]
        assert rec["criterio"] == f"maior contribuição para o risco: latitude={POS_PROPRIA[0]:g} (+9.5 pontos)"

    def test_operador_recebe_mascarada_a_avaliacao_de_outro(self, base):
        r = client.get(f"/equipamentos/{MISTO}", headers=AUTH["operador"])
        assert r.status_code == 200
        corpo = r.json()
        ultima = corpo["ultima_avaliacao"]
        assert (ultima["operador_id"], ultima["latitude"], ultima["longitude"]) == (None, None, None)
        # O resto da avaliacao segue: e o recorte do operador.
        assert ultima["score_operador_historico"] == 61.0
        assert ultima["risco_score"] == 80.0

    def test_posicao_nao_vaza_pelo_shap_nem_pela_recomendacao(self, base):
        corpo = client.get(f"/equipamentos/{MISTO}", headers=AUTH["operador"]).json()
        latitude, velocidade = corpo["predicao"]["top_fatores_shap"]
        assert latitude == {"feature": "latitude", "valor": None, "shap_value": 9.5, "grupo": "geografico"}
        assert velocidade["valor"] == 5.0, "so a posicao e mascarada"
        (rec,) = corpo["recomendacoes"]
        assert rec["id"] == "fator_dominante"
        assert rec["criterio"] == "maior contribuição para o risco: latitude (+9.5 pontos)"

    def test_nada_do_outro_operador_na_resposta_inteira(self, base):
        r = client.get(f"/equipamentos/{MISTO}", headers=AUTH["operador"])
        assert _na_resposta(r, OUTRO, *POS_OUTRO, f"{POS_OUTRO[0]:g}") == []

    @pytest.mark.parametrize("perfil", FROTA)
    def test_frota_ve_tudo(self, base, perfil):
        r = client.get(f"/equipamentos/{MISTO}", headers=AUTH[perfil])
        assert r.status_code == 200
        corpo = r.json()
        ultima = corpo["ultima_avaliacao"]
        assert (ultima["operador_id"], ultima["latitude"], ultima["longitude"]) == (OUTRO, *POS_OUTRO)
        assert corpo["predicao"]["top_fatores_shap"][0]["valor"] == POS_OUTRO[0]
        (rec,) = corpo["recomendacoes"]
        assert f"latitude={POS_OUTRO[0]:g}" in rec["criterio"]

    def test_historico_nao_traz_operador_nem_posicao(self, base):
        corpo = client.get(f"/equipamentos/{MISTO}", headers=AUTH["operador"]).json()
        assert [set(h) for h in corpo["historico"]] == [{"timestamp", "risco_score"}] * 2


class TestCamposInternos:
    @pytest.mark.parametrize("perfil", [*FROTA, "operador"])
    @pytest.mark.parametrize("equipamento_id", [MISTO, PROPRIO_EQ])
    def test_idempotencia_nao_sai_no_detalhe(self, base, perfil, equipamento_id):
        r = client.get(f"/equipamentos/{equipamento_id}", headers=AUTH[perfil])
        assert r.status_code == 200
        assert "leitura_id" not in r.json()["ultima_avaliacao"]
        assert "payload_hash" not in r.json()["ultima_avaliacao"]
        assert _na_resposta(r, "leitura_id", "payload_hash", LEITURA_ID, PAYLOAD_HASH) == []

    @pytest.mark.parametrize("perfil", [*FROTA, "operador"])
    @pytest.mark.parametrize("rota", ["/equipamentos", "/alertas?faixa_minima=baixo&limite=100"])
    def test_idempotencia_nao_sai_nas_listas(self, base, perfil, rota):
        r = client.get(rota, headers=AUTH[perfil])
        assert r.status_code == 200
        assert _na_resposta(r, "leitura_id", "payload_hash") == []


class TestMinimizarNoServico:
    def test_nao_altera_a_resposta_recebida(self):
        """Mascara em copia: quem chamou continua com o dado original."""
        itens = [
            {"equipamento_id": MISTO, "operador_id": OUTRO, "latitude": -1.0, "longitude": -2.0},
            {"equipamento_id": PROPRIO_EQ, "operador_id": PROPRIO, "latitude": -3.0, "longitude": -4.0},
        ]
        resposta = {"total": 2, "itens": itens}
        antes = copy.deepcopy(resposta)
        saida = consultas.minimizar_para_operador(resposta, PROPRIO)
        assert resposta == antes
        assert saida["itens"][0]["operador_id"] is None
        assert saida["itens"][1] == itens[1]

    def test_equipamento_sem_avaliacao_segue_com_os_nulls_do_contrato(self):
        item = {"equipamento_id": MISTO, "operador_id": None, "latitude": None, "longitude": None}
        saida = consultas.minimizar_para_operador({"total": 1, "itens": [item]}, PROPRIO)
        assert saida["itens"] == [item]

    def test_detalhe_sem_avaliacao_passa_intacto(self):
        detalhe = {
            "equipamento": _equipamento(MISTO),
            "ultima_avaliacao": None,
            "predicao": None,
            "recomendacoes": [],
            "historico": [],
        }
        assert consultas.minimizar_para_operador(detalhe, PROPRIO) == detalhe

    def test_detalhe_sem_predicao(self):
        detalhe = {
            "equipamento": _equipamento(MISTO),
            "ultima_avaliacao": _linha_completa(RESUMO[1]),
            "predicao": None,
            "recomendacoes": [],
            "historico": [],
        }
        saida = consultas.minimizar_para_operador(detalhe, PROPRIO)
        assert saida["ultima_avaliacao"]["latitude"] is None
        assert saida["predicao"] is None
