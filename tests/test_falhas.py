"""
Falhas previsiveis (S4-21): dependencia fora do ar responde tratado, com
request_id correlacionavel e registro na auditoria, nunca com stack trace.

Supabase, Open-Meteo e o modelo sao mockados.
"""

import os
import sys
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.api.main import app  # noqa: E402
from backend.core.exceptions import BancoIndisponivel, ModeloIndisponivel  # noqa: E402
from backend.core.security import criar_token  # noqa: E402
from tests.test_api import CLIMA_FALSO, EQUIPAMENTO_FALSO, LEITURA_VALIDA  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def auth():
    token, _ = criar_token("analista", "analista")
    return {"Authorization": f"Bearer {token}"}


def _status_das_auditorias(auditoria_mock) -> list[str]:
    return [c.args[3] for c in auditoria_mock.call_args_list]


class TestModeloIndisponivel:
    def test_responde_503_sem_persistir_e_audita(self, auth):
        with patch("backend.services.scoring.repo") as repo_mock, \
             patch("backend.services.clima.buscar", return_value=CLIMA_FALSO), \
             patch("backend.services.scoring.get_predictor",
                   side_effect=FileNotFoundError("models/xgboost_model.joblib")), \
             patch("backend.services.auditoria.registrar") as auditoria:
            repo_mock.buscar_equipamento.return_value = EQUIPAMENTO_FALSO
            repo_mock.operador_existe.return_value = True
            r = client.post("/avaliacoes", json=LEITURA_VALIDA, headers=auth)
        assert r.status_code == 503
        assert r.json()["detail"] == ModeloIndisponivel.mensagem
        assert r.headers.get("X-Request-ID")
        repo_mock.registrar_avaliacao.assert_not_called()
        assert _status_das_auditorias(auditoria) == ["erro"]


class TestBancoIndisponivel:
    def test_supabase_inacessivel_responde_503(self, auth):
        with patch("backend.services.scoring.repo") as repo_mock, \
             patch("backend.services.auditoria.registrar"):
            repo_mock.buscar_equipamento.side_effect = httpx.ConnectError("sem rota")
            r = client.post("/avaliacoes", json=LEITURA_VALIDA, headers=auth)
        assert r.status_code == 503
        assert r.json()["detail"] == BancoIndisponivel.mensagem
        assert r.headers.get("X-Request-ID")

    def test_leitura_com_banco_fora_tambem_responde_503(self, auth):
        with patch("backend.services.consultas.repo") as repo_mock:
            repo_mock.listar_equipamentos.side_effect = httpx.ReadTimeout("lento")
            r = client.get("/equipamentos", headers=auth)
        assert r.status_code == 503


class TestErroInesperado:
    def test_500_traz_request_id_no_corpo_e_no_header(self, auth):
        with patch("backend.services.scoring.repo") as repo_mock:
            repo_mock.buscar_equipamento.side_effect = RuntimeError("bug")
            r = client.post("/avaliacoes", json=LEITURA_VALIDA, headers=auth)
        assert r.status_code == 500
        assert "bug" not in r.text, "detalhe interno vazou para o cliente"
        rid = r.json()["request_id"]
        assert rid and r.headers.get("X-Request-ID") == rid


class TestClimaIndisponivel:
    def test_502_registra_auditoria_de_erro(self, auth):
        with patch("backend.services.scoring.repo") as repo_mock, \
             patch("backend.services.clima.buscar", return_value=None), \
             patch("backend.services.auditoria.registrar") as auditoria:
            repo_mock.buscar_equipamento.return_value = EQUIPAMENTO_FALSO
            repo_mock.operador_existe.return_value = True
            r = client.post("/avaliacoes", json=LEITURA_VALIDA, headers=auth)
        assert r.status_code == 502
        assert _status_das_auditorias(auditoria) == ["erro"]


class TestHealth:
    def test_degradado_nao_expoe_o_erro_interno(self):
        with patch("backend.services.scoring.get_predictor",
                   side_effect=FileNotFoundError(r"C:\\caminho\\interno\\modelo.joblib")):
            r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "degradado"
        assert "caminho" not in r.text

    def test_ok_quando_o_modelo_carrega(self):
        r = client.get("/health")
        assert r.json()["status"] == "ok"
        assert r.json()["modelo"]["n_features"] == 30
