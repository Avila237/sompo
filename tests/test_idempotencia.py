"""
Idempotencia da ingestao (S4-12) e gravacao atomica (S4-13).

A funcao SQL registrar_avaliacao() foi testada contra um Postgres real (ver o
PR); aqui o repositorio e mockado e o que se testa e o contrato da API em volta
dela: chave do cliente, hash do payload, reenvio e conflito.
"""

import os
import sys
import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from postgrest.exceptions import APIError

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.api.main import app  # noqa: E402
from backend.api.schemas import LeituraTelemetria  # noqa: E402
from backend.core.exceptions import LeituraReutilizada  # noqa: E402
from backend.core.security import criar_token  # noqa: E402
from backend.db import repository  # noqa: E402
from backend.services.scoring import hash_do_payload  # noqa: E402
from tests.test_api import CLIMA_FALSO, EQUIPAMENTO_FALSO, LEITURA_VALIDA  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)
LEITURA_ID = str(uuid.UUID("11111111-1111-1111-1111-111111111111"))


@pytest.fixture
def auth():
    token, _ = criar_token("analista", "analista")
    return {"Authorization": f"Bearer {token}"}


def _post(auth, leitura, registrar, anterior=None):
    with patch("backend.services.scoring.repo") as repo_mock, \
         patch("backend.services.clima.buscar", return_value=CLIMA_FALSO), \
         patch("backend.services.auditoria.registrar") as auditoria:
        repo_mock.buscar_equipamento.return_value = EQUIPAMENTO_FALSO
        repo_mock.operador_existe.return_value = True
        repo_mock.buscar_por_leitura.return_value = anterior
        if isinstance(registrar, Exception):
            repo_mock.registrar_avaliacao.side_effect = registrar
        else:
            repo_mock.registrar_avaliacao.return_value = registrar
        repo_mock.buscar_avaliacao.return_value = {
            "avaliacao_id": 77, "risco_score": 61.5, "faixa_risco": "medio",
            "clima_origem": "open-meteo", "timestamp": "2026-09-28T10:00:00+00:00",
            **{k: v for k, v in LEITURA_VALIDA.items()},
        }
        repo_mock.predicao_de.return_value = {
            "avaliacao_id": 77, "risco_score_predito": 61.5, "faixa_predita": "medio",
            "modelo_versao": "xgboost-v1-baseline",
            "top_fatores_shap": [{"feature": "horas_operacao", "valor": 6.0, "shap_value": 4.2,
                                  "grupo": "operacional"}],
            "contribuicoes_por_grupo": {"operacional": 4.2},
        }
        r = client.post("/avaliacoes", json=leitura, headers=auth)
    return r, repo_mock, auditoria


class TestChaveDoCliente:
    def test_leitura_id_e_hash_vao_para_a_gravacao(self, auth):
        r, repo_mock, _ = _post(auth, {**LEITURA_VALIDA, "leitura_id": LEITURA_ID}, (1, False))
        assert r.status_code == 201, r.text
        avaliacao, _ = repo_mock.registrar_avaliacao.call_args[0]
        assert avaliacao["leitura_id"] == LEITURA_ID
        assert avaliacao["payload_hash"]

    def test_sem_leitura_id_continua_aceito(self, auth):
        r, repo_mock, _ = _post(auth, LEITURA_VALIDA, (1, False))
        assert r.status_code == 201
        avaliacao, _ = repo_mock.registrar_avaliacao.call_args[0]
        assert avaliacao.get("leitura_id") is None

    def test_leitura_id_invalido_e_recusado(self, auth):
        r, repo_mock, _ = _post(auth, {**LEITURA_VALIDA, "leitura_id": "nao-e-uuid"}, (1, False))
        assert r.status_code == 422
        repo_mock.registrar_avaliacao.assert_not_called()


class TestHash:
    def test_mesmo_payload_mesmo_hash(self):
        assert hash_do_payload(dict(LEITURA_VALIDA)) == hash_do_payload(dict(LEITURA_VALIDA))

    def test_ordem_das_chaves_nao_importa(self):
        invertido = dict(reversed(list(LEITURA_VALIDA.items())))
        assert hash_do_payload(invertido) == hash_do_payload(dict(LEITURA_VALIDA))

    def test_hash_ignora_a_propria_chave(self):
        com_chave = {**LEITURA_VALIDA, "leitura_id": LEITURA_ID}
        assert hash_do_payload(com_chave) == hash_do_payload(dict(LEITURA_VALIDA))

    def test_opcional_ausente_e_opcional_nulo_dao_o_mesmo_hash(self):
        """Campo opcional novo no schema nao muda o hash de um payload antigo."""
        assert hash_do_payload({**LEITURA_VALIDA, "campo_futuro": None}) == hash_do_payload(
            dict(LEITURA_VALIDA)
        )

    def test_payload_diferente_hash_diferente(self):
        outro = {**LEITURA_VALIDA, "velocidade_kmh": LEITURA_VALIDA["velocidade_kmh"] + 1}
        assert hash_do_payload(outro) != hash_do_payload(dict(LEITURA_VALIDA))

    def test_hash_e_do_payload_recebido_nao_do_clima_consultado(self, auth):
        """Um retry nao muda de hash so porque a Open-Meteo respondeu outro valor."""
        leitura = {**LEITURA_VALIDA, "leitura_id": LEITURA_ID}
        _, repo_1, _ = _post(auth, leitura, (1, False))
        with patch("backend.services.clima.buscar", return_value={**CLIMA_FALSO, "temperatura_ar": 11.0}):
            _, repo_2, _ = _post(auth, leitura, (1, True))
        h1 = repo_1.registrar_avaliacao.call_args[0][0]["payload_hash"]
        h2 = repo_2.registrar_avaliacao.call_args[0][0]["payload_hash"]
        assert h1 == h2


class TestReenvio:
    def test_reenvio_devolve_o_resultado_gravado_com_200(self, auth):
        r, _, auditoria = _post(auth, {**LEITURA_VALIDA, "leitura_id": LEITURA_ID}, (77, True))
        assert r.status_code == 200, r.text
        corpo = r.json()
        assert corpo["avaliacao_id"] == 77
        assert corpo["risco_score"] == 61.5 and corpo["faixa_risco"] == "medio"
        assert corpo["contribuicoes_por_grupo"] == {"operacional": 4.2}
        assert corpo["timestamp"] == "2026-09-28T10:00:00+00:00"
        assert "recomendacoes" in corpo
        assert [c.args[3] for c in auditoria.call_args_list] == ["reenvio"]

    def test_conflito_mesma_chave_outro_payload_da_409(self, auth):
        erro = LeituraReutilizada(LEITURA_ID)
        r, _, auditoria = _post(auth, {**LEITURA_VALIDA, "leitura_id": LEITURA_ID}, erro)
        assert r.status_code == 409
        assert LEITURA_ID in r.json()["detail"]
        assert [c.args[3] for c in auditoria.call_args_list] == ["erro"]


class TestReenvioAntesDoTrabalho:
    """
    O retry chega depois de a rede cair: nao pode depender de a Open-Meteo
    ou o modelo estarem de pe de novo para devolver o que ja foi gravado.
    """

    def _hash(self):
        # O mesmo dict que a rota entrega ao servico, ja normalizado pelo Pydantic.
        leitura = LeituraTelemetria(**LEITURA_VALIDA, leitura_id=LEITURA_ID)
        return hash_do_payload(leitura.model_dump(mode="json"))

    def test_reenvio_responde_mesmo_com_a_open_meteo_fora(self, auth):
        anterior = {"avaliacao_id": 77, "payload_hash": self._hash()}
        with patch("backend.services.scoring.resolver_clima", side_effect=AssertionError("clima")), \
             patch("backend.services.scoring.carregar_modelo", side_effect=AssertionError("modelo")):
            r, repo_mock, auditoria = _post(
                auth, {**LEITURA_VALIDA, "leitura_id": LEITURA_ID}, (1, False), anterior
            )
        assert r.status_code == 200, r.text
        assert r.json()["avaliacao_id"] == 77
        repo_mock.registrar_avaliacao.assert_not_called()
        assert [c.args[3] for c in auditoria.call_args_list] == ["reenvio"]

    def test_conflito_detectado_antes_de_consultar_o_clima(self, auth):
        anterior = {"avaliacao_id": 77, "payload_hash": "outro"}
        with patch("backend.services.scoring.resolver_clima", side_effect=AssertionError("clima")):
            r, repo_mock, auditoria = _post(
                auth, {**LEITURA_VALIDA, "leitura_id": LEITURA_ID}, (1, False), anterior
            )
        assert r.status_code == 409
        repo_mock.registrar_avaliacao.assert_not_called()
        assert [c.args[3] for c in auditoria.call_args_list] == ["erro"]


class TestRepositorio:
    def _cliente(self, *efeitos):
        cliente = MagicMock()
        cliente.rpc.return_value.execute.side_effect = list(efeitos)
        return cliente

    def test_devolve_id_e_flag_de_reenvio(self):
        resposta = MagicMock(data=[{"avaliacao_id": 9, "reenvio": False}])
        with patch.object(repository, "get_client", return_value=self._cliente(resposta)):
            assert repository.registrar_avaliacao({"leitura_id": None}, {}) == (9, False)

    def test_erro_pt409_vira_leitura_reutilizada(self):
        erro = APIError({"message": "reutilizado", "code": "PT409", "details": None, "hint": None})
        with patch.object(repository, "get_client", return_value=self._cliente(erro)), \
             pytest.raises(LeituraReutilizada):
            repository.registrar_avaliacao({"leitura_id": LEITURA_ID}, {})

    def test_corrida_na_mesma_chave_tenta_de_novo_e_cai_no_reenvio(self):
        """Dois envios simultaneos: o segundo bate no UNIQUE e, na nova tentativa, e reenvio."""
        corrida = APIError({"message": "duplicate key", "code": "23505", "details": None, "hint": None})
        reenvio = MagicMock(data=[{"avaliacao_id": 9, "reenvio": True}])
        cliente = self._cliente(corrida, reenvio)
        with patch.object(repository, "get_client", return_value=cliente):
            assert repository.registrar_avaliacao({"leitura_id": LEITURA_ID}, {}) == (9, True)
        assert cliente.rpc.return_value.execute.call_count == 2

    def test_violacao_de_unicidade_sem_chave_nao_e_mascarada(self):
        corrida = APIError({"message": "duplicate key", "code": "23505", "details": None, "hint": None})
        with patch.object(repository, "get_client", return_value=self._cliente(corrida)), \
             pytest.raises(APIError):
            repository.registrar_avaliacao({"leitura_id": None}, {})
