"""
Hardening da API (S4-19): autenticacao que nao quebra com entrada inesperada,
limite de tentativas de login, CORS sem credenciais e log sem localizacao
precisa (dado pessoal sob a LGPD).
"""

import logging
import os
import sys
from unittest.mock import patch

import pytest
import requests
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.api.main import app  # noqa: E402
from backend.api.routers import auth as rota_auth  # noqa: E402
from backend.core import config  # noqa: E402
from backend.services import clima  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def sem_historico_de_tentativas():
    rota_auth.limpar_tentativas()
    yield
    rota_auth.limpar_tentativas()


def _credencial_valida():
    usuario, dados = next(iter(config.DEMO_USERS.items()))
    return usuario, dados["senha"]


class TestSenhaComCaractereNaoAscii:
    @pytest.mark.parametrize("senha", ["çãõ", "senha-com-emoji-🔒", "ÿ" * 40])
    def test_recusa_com_401_e_nao_quebra_com_500(self, senha):
        usuario, _ = _credencial_valida()
        r = client.post("/auth/token", json={"usuario": usuario, "senha": senha})
        assert r.status_code == 401

    def test_senha_com_acento_cadastrada_autentica(self):
        with patch.dict(config.DEMO_USERS, {"joão": {"senha": "coração-1", "perfil": "gestor"}}):
            r = client.post("/auth/token", json={"usuario": "joão", "senha": "coração-1"})
        assert r.status_code == 200
        assert r.json()["perfil"] == "gestor"


class TestLimiteDeTentativas:
    def test_bloqueia_depois_do_limite_de_falhas(self):
        usuario, senha = _credencial_valida()
        for _ in range(rota_auth.MAX_FALHAS):
            assert client.post("/auth/token", json={"usuario": usuario, "senha": senha + "-errada"}).status_code == 401
        r = client.post("/auth/token", json={"usuario": usuario, "senha": senha})
        assert r.status_code == 429, "credencial certa depois do limite tambem espera a janela"
        assert int(r.headers["Retry-After"]) > 0

    def test_abaixo_do_limite_a_credencial_certa_entra(self):
        usuario, senha = _credencial_valida()
        for _ in range(rota_auth.MAX_FALHAS - 1):
            client.post("/auth/token", json={"usuario": usuario, "senha": senha + "-errada"})
        assert client.post("/auth/token", json={"usuario": usuario, "senha": senha}).status_code == 200

    def test_falhas_expiram_depois_da_janela(self):
        usuario, senha = _credencial_valida()
        agora = [1000.0]
        with patch.object(rota_auth, "_relogio", lambda: agora[0]):
            for _ in range(rota_auth.MAX_FALHAS):
                client.post("/auth/token", json={"usuario": usuario, "senha": senha + "-errada"})
            assert client.post("/auth/token", json={"usuario": usuario, "senha": senha}).status_code == 429
            agora[0] += rota_auth.JANELA_S + 1
            assert client.post("/auth/token", json={"usuario": usuario, "senha": senha}).status_code == 200


class TestCors:
    def test_preflight_nao_libera_credenciais(self):
        origem = config.API_CORS_ORIGINS[0]
        r = client.options(
            "/equipamentos",
            headers={"Origin": origem, "Access-Control-Request-Method": "GET"},
        )
        assert r.headers.get("access-control-allow-origin") == origem
        assert "access-control-allow-credentials" not in r.headers


class TestLogSemLocalizacaoPrecisa:
    def test_falha_da_open_meteo_nao_loga_a_coordenada_exata(self, caplog):
        with patch.object(clima.requests, "get", side_effect=requests.ConnectionError("rede fora")), \
             caplog.at_level(logging.WARNING, logger="safefield"):
            assert clima.buscar(-12.54531, -55.71149, "argiloso") is None
        texto = caplog.text
        assert "Open-Meteo" in texto
        assert "-12.5453" not in texto and "-55.7115" not in texto
        assert "-12.5" in texto


# ---------------------------------------------------------------------------
# CORS: o navegador precisa ler a resposta e o X-Request-ID, inclusive em erro
# ---------------------------------------------------------------------------

class TestCorsEmErro:
    """
    O dashboard roda em outra origem. Sem Access-Control-Allow-Origin o fetch
    rejeita a resposta inteira ("Não foi possível falar com a API"); sem
    Access-Control-Expose-Headers ele não lê o X-Request-ID, e um 503 (que não
    traz request_id no corpo) chega à tela sem o código para suporte.
    """

    ORIGEM = config.API_CORS_ORIGINS[0]

    @pytest.fixture
    def auth_origem(self):
        from backend.core.security import criar_token
        token, _ = criar_token("analista", "analista")
        return {"Authorization": f"Bearer {token}", "Origin": self.ORIGEM}

    def _checa_cors(self, r):
        assert r.headers.get("access-control-allow-origin") == self.ORIGEM
        assert "x-request-id" in r.headers.get("access-control-expose-headers", "").lower()
        assert r.headers.get("x-request-id")

    def test_resposta_normal_expoe_x_request_id(self):
        r = client.get("/health", headers={"Origin": self.ORIGEM})
        assert r.status_code == 200
        self._checa_cors(r)

    def test_503_chega_ao_navegador_com_o_codigo(self, auth_origem):
        from backend.core.exceptions import BancoIndisponivel
        from backend.services import consultas
        with patch.object(consultas, "kpis", side_effect=BancoIndisponivel()):
            r = client.get("/kpis", headers=auth_origem)
        assert r.status_code == 503
        self._checa_cors(r)

    def test_500_nao_tratado_chega_ao_navegador_com_o_codigo(self, auth_origem):
        """O 500 é montado no middleware de correlação: o CORS tem de envolvê-lo."""
        from backend.services import consultas
        with patch.object(consultas, "kpis", side_effect=RuntimeError("falha inesperada")):
            r = client.get("/kpis", headers=auth_origem)
        assert r.status_code == 500
        self._checa_cors(r)
        assert r.json()["request_id"] == r.headers["x-request-id"]
