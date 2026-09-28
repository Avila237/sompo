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
