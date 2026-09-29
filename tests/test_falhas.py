"""
Falhas previsiveis (S4-21): dependencia fora do ar responde tratado, com
request_id correlacionavel e registro na auditoria, nunca com stack trace.

Supabase, Open-Meteo e o modelo sao mockados.
"""

import os
import sys
from unittest.mock import patch

import json

import httpx
import pytest
from fastapi.testclient import TestClient
from postgrest import SyncPostgrestClient
from postgrest.exceptions import APIError

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.api.main import app  # noqa: E402
from backend.core.exceptions import (  # noqa: E402
    BancoIndisponivel,
    LeituraReutilizada,
    ModeloIndisponivel,
)
from backend.core.security import criar_token  # noqa: E402
from backend.db import repository  # noqa: E402
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


URL_POSTGREST = "http://postgrest.invalid"


def _postgrest_respondendo(status: int, corpo: str) -> SyncPostgrestClient:
    """
    Cliente PostgREST real (o postgrest-py instalado), com o servidor trocado
    por um que responde sempre `status` e `corpo`. O APIError que chega a API
    e o que a biblioteca monta, nao um construido a mao.
    """
    def responder(_requisicao):
        return httpx.Response(status, content=corpo.encode(),
                              headers={"content-type": "application/json"})

    return SyncPostgrestClient(
        URL_POSTGREST,
        http_client=httpx.Client(transport=httpx.MockTransport(responder), base_url=URL_POSTGREST),
    )


def _erro_postgrest(codigo: str, mensagem: str = "erro") -> str:
    return json.dumps({"code": codigo, "message": mensagem, "details": None, "hint": None})


# (status HTTP, corpo) da resposta do PostgREST ou do gateway na frente dele
SEM_BANCO = [
    pytest.param(503, _erro_postgrest("PGRST000", "Database connection error."), id="PGRST000"),
    pytest.param(503, _erro_postgrest("PGRST001", "Database client error."), id="PGRST001"),
    pytest.param(503, _erro_postgrest("PGRST002", "Could not query the database for the schema cache."),
                 id="PGRST002"),
    pytest.param(504, _erro_postgrest("PGRST003", "Timed out acquiring connection from pool."),
                 id="PGRST003"),
    pytest.param(503, _erro_postgrest("08006", "connection failure"), id="sqlstate-08006"),
    pytest.param(503, _erro_postgrest("57P01", "terminating connection due to administrator command"),
                 id="sqlstate-57P01"),
    # Corpo que nao e o JSON de erro do PostgREST: o postgrest-py poe o status HTTP em `code`.
    pytest.param(502, "<html>Bad Gateway</html>", id="gateway-502-html"),
    pytest.param(503, json.dumps({"message": "An invalid response was received from the upstream server"}),
                 id="gateway-503-json-sem-code"),
]
ERRO_DE_DADO = [
    pytest.param(409, _erro_postgrest("23505", "duplicate key value violates unique constraint"),
                 id="23505"),
    pytest.param(400, _erro_postgrest("23514", "violates check constraint"), id="23514-check"),
    pytest.param(400, _erro_postgrest("22P02", "invalid input syntax for type uuid"), id="22P02"),
    pytest.param(406, _erro_postgrest("PGRST116", "JSON object requested, multiple rows returned"),
                 id="PGRST116"),
    pytest.param(400, _erro_postgrest("PT409", "leitura_id reutilizado"), id="PT409"),
    pytest.param(404, "<html>Not Found</html>", id="gateway-404-html"),
]


@pytest.fixture
def postgrest_real():
    """Troca o get_client do repositorio; sem o cache, a leitura vai ao 'servidor'."""
    repository.invalidar_cache()
    # GET com 503 e repetido pelo proprio postgrest-py (ate 3 vezes, com espera).
    with patch("postgrest._sync.request_builder.get_retry_delay", return_value=0):
        yield
    repository.invalidar_cache()


class TestPostgrestSemPostgres:
    """
    PostgREST de pe com o Postgres fora: nao ha erro de transporte (o httpx
    fala com o PostgREST), e sim um APIError. Falta de banco vira o mesmo 503
    da conexao recusada; erro de dado continua como estava (500 generico, ou
    409 do PT409 na gravacao).
    """

    @pytest.mark.parametrize("status,corpo", SEM_BANCO)
    def test_sem_banco_responde_503(self, auth, postgrest_real, status, corpo):
        with patch.object(repository, "get_client", return_value=_postgrest_respondendo(status, corpo)):
            r = client.get("/equipamentos", headers=auth)
        assert r.status_code == 503, r.text
        assert r.json()["detail"] == BancoIndisponivel.mensagem
        assert r.headers.get("X-Request-ID")

    @pytest.mark.parametrize("status,corpo", ERRO_DE_DADO)
    def test_erro_de_dado_nao_vira_503(self, auth, postgrest_real, status, corpo):
        with patch.object(repository, "get_client", return_value=_postgrest_respondendo(status, corpo)):
            r = client.get("/equipamentos", headers=auth)
        assert r.status_code == 500, r.text
        assert r.json()["request_id"] == r.headers.get("X-Request-ID")

    def test_gravacao_com_postgres_fora_responde_503_e_audita(self, auth):
        erro = APIError({"code": "PGRST001", "message": "Database client error.",
                         "details": None, "hint": None})
        with patch("backend.services.scoring.repo") as repo_mock, \
             patch("backend.services.clima.buscar", return_value=CLIMA_FALSO), \
             patch("backend.services.auditoria.registrar") as auditoria:
            repo_mock.buscar_equipamento.return_value = EQUIPAMENTO_FALSO
            repo_mock.operador_existe.return_value = True
            repo_mock.registrar_avaliacao.side_effect = erro
            r = client.post("/avaliacoes", json=LEITURA_VALIDA, headers=auth)
        assert r.status_code == 503, r.text
        assert r.json()["detail"] == BancoIndisponivel.mensagem
        repo_mock.registrar_avaliacao.assert_called_once()
        assert _status_das_auditorias(auditoria) == ["erro"]

    def test_pt409_na_gravacao_continua_409(self, auth):
        """O PT409 e tratado no repositorio (LeituraReutilizada) antes de chegar ao handler."""
        cliente = _postgrest_respondendo(400, _erro_postgrest("PT409", "leitura_id reutilizado"))
        with patch.object(repository, "get_client", return_value=cliente), \
             pytest.raises(LeituraReutilizada):
            repository.registrar_avaliacao({"leitura_id": "x"}, {})


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
