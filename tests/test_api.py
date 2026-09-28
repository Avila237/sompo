"""
Testes da integracao (RF-11).

Cobrem os tres pontos onde o fluxo pode quebrar em silencio: payload invalido
sendo persistido, rota de dado sem autenticacao, e scoring devolvendo score sem
a decomposicao que a interface precisa.

Dependencias externas sao mockadas: nem Supabase nem Open-Meteo sao chamados.
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
from backend.core import config  # noqa: E402
from backend.core.security import criar_token  # noqa: E402

# raise_server_exceptions=False: queremos observar o 500 que o handler produz,
# nao a excecao crua propagada pelo TestClient.
client = TestClient(app, raise_server_exceptions=False)

EQUIPAMENTO_FALSO = {
    "equipamento_id": "EQ-0001",
    "tipo_equipamento": "trator",
    "modelo_equipamento": "John Deere 7J195",
    "categoria_manual": "trator_operacao",
    "idade_equipamento": 5,
    "historico_sinistros": 2,
    "tem_iot": True,
    "intervalo_manut_recomendado_dias": 180,
    "intervalo_manut_recomendado_horas": 500,
}

CLIMA_FALSO = {
    "temperatura_ar": 28.0,
    "precipitacao_mm": 10.0,
    "umidade_solo": 40.0,
    "velocidade_vento": 12.0,
    "condicao_clima": "nublado",
}

LEITURA_VALIDA = {
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


@pytest.fixture
def token() -> str:
    t, _ = criar_token("analista", "analista")
    return t


@pytest.fixture
def auth(token) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. Autenticacao
# ---------------------------------------------------------------------------

class TestAutenticacao:
    ROTAS_PROTEGIDAS = [
        ("get", "/equipamentos"),
        ("get", "/equipamentos/EQ-0001"),
        ("get", "/alertas"),
        ("get", "/kpis"),
        ("post", "/avaliacoes"),
    ]

    @pytest.mark.parametrize("metodo,rota", ROTAS_PROTEGIDAS)
    def test_sem_token_recebe_401(self, metodo, rota):
        r = getattr(client, metodo)(rota)
        assert r.status_code == 401

    @pytest.mark.parametrize("metodo,rota", ROTAS_PROTEGIDAS)
    def test_token_invalido_recebe_401(self, metodo, rota):
        r = getattr(client, metodo)(rota, headers={"Authorization": "Bearer nao.e.token"})
        assert r.status_code == 401

    def test_health_e_aberto(self):
        assert client.get("/health").status_code == 200

    def test_credencial_errada_recebe_401(self):
        r = client.post("/auth/token", json={"usuario": "analista", "senha": "errada"})
        assert r.status_code == 401

    def test_usuario_inexistente_recebe_401(self):
        r = client.post("/auth/token", json={"usuario": "ninguem", "senha": "x"})
        assert r.status_code == 401

    def test_credencial_correta_devolve_token(self):
        usuario, dados = next(iter(config.DEMO_USERS.items()))
        r = client.post("/auth/token", json={"usuario": usuario, "senha": dados["senha"]})
        assert r.status_code == 200
        corpo = r.json()
        assert corpo["token_type"] == "bearer"
        assert corpo["perfil"] == dados["perfil"]
        assert corpo["access_token"]


# ---------------------------------------------------------------------------
# 2. Validacao: payload invalido nao pode persistir
# ---------------------------------------------------------------------------

class TestValidacao:
    @pytest.mark.parametrize(
        "campo,valor",
        [
            ("equipamento_id", "EQ-42"),        # fora do padrao EQ-0000
            ("operador_id", "12345"),           # fora do padrao OP-0000
            ("velocidade_kmh", 99.0),           # acima do dominio
            ("horario_operacao", 25),           # hora inexistente
            ("tipo_operacao", "voando"),        # fora do enum
            ("tipo_solo", "lunar"),             # fora do enum
            ("declividade", -3.0),              # negativo
            ("latitude", 10.0),                 # fora do Brasil
            ("atraso_manutencao_pct", 0.5),     # derivado: nao aceito do cliente
        ],
    )
    def test_payload_invalido_rejeitado_sem_persistir(self, auth, campo, valor):
        with patch("backend.db.repository.inserir_avaliacao") as inserir:
            r = client.post("/avaliacoes", json={**LEITURA_VALIDA, campo: valor}, headers=auth)
        assert r.status_code == 422, f"{campo}={valor} deveria ser rejeitado"
        inserir.assert_not_called()

    def test_campo_derivado_e_recusado(self, auth):
        """faixa_risco e atraso_manutencao_pct sao derivados: o cliente nao os define."""
        for campo, valor in (("faixa_risco", "baixo"), ("atraso_manutencao_pct", 0.1)):
            with patch("backend.db.repository.inserir_avaliacao") as inserir:
                r = client.post(
                    "/avaliacoes", json={**LEITURA_VALIDA, campo: valor}, headers=auth
                )
            assert r.status_code == 422, f"{campo} deveria ser recusado"
            inserir.assert_not_called()

    def test_equipamento_inexistente_recebe_404(self, auth):
        with patch("backend.services.scoring.repo") as repo_mock, \
             patch("backend.services.auditoria.registrar"):
            repo_mock.buscar_equipamento.return_value = None
            r = client.post("/avaliacoes", json=LEITURA_VALIDA, headers=auth)
        assert r.status_code == 404
        assert "nao encontrado" in r.json()["detail"]


# ---------------------------------------------------------------------------
# 2b. Consistencia entre campos (docs/data schema.md, secao 3)
# ---------------------------------------------------------------------------

def _post_com_cadastro(auth, leitura, equipamento=EQUIPAMENTO_FALSO):
    """POST com o cadastro mockado; devolve (resposta, mock do repositorio)."""
    with patch("backend.services.scoring.repo") as repo_mock,          patch("backend.services.clima.buscar", return_value=CLIMA_FALSO),          patch("backend.services.auditoria.registrar"):
        repo_mock.buscar_equipamento.return_value = equipamento
        repo_mock.operador_existe.return_value = True
        repo_mock.inserir_avaliacao.return_value = 1
        r = client.post("/avaliacoes", json=leitura, headers=auth)
    return r, repo_mock


class TestConsistenciaCruzada:
    def test_parado_com_velocidade_e_recusado(self, auth):
        """Regra 4: operacao parada tem velocidade zero."""
        leitura = {**LEITURA_VALIDA, "tipo_operacao": "parado", "velocidade_kmh": 12.0}
        r, repo_mock = _post_com_cadastro(auth, leitura)
        assert r.status_code == 422
        assert "parado" in r.text
        repo_mock.inserir_avaliacao.assert_not_called()

    def test_parado_com_velocidade_zero_e_aceito(self, auth):
        leitura = {**LEITURA_VALIDA, "tipo_operacao": "parado", "velocidade_kmh": 0.0}
        r, _ = _post_com_cadastro(auth, leitura)
        assert r.status_code == 201, r.text

    @pytest.mark.parametrize(
        "precipitacao,condicao",
        [
            (0.0, "tempestade"),    # tempestade sem chuva
            (0.0, "chuvoso"),
            (2.1, "ensolarado"),    # logo acima do teto de 2 mm
            (35.0, "nublado"),      # 20-50 mm so admite chuvoso
            (35.0, "tempestade"),
            (80.0, "ensolarado"),
        ],
    )
    def test_clima_incompativel_com_a_chuva_e_recusado(self, auth, precipitacao, condicao):
        """Regra 5: condicao_clima acompanha a precipitacao acumulada."""
        leitura = {
            **LEITURA_VALIDA, **CLIMA_FALSO,
            "precipitacao_mm": precipitacao, "condicao_clima": condicao,
        }
        r, repo_mock = _post_com_cadastro(auth, leitura)
        assert r.status_code == 422, f"{precipitacao} mm + {condicao} deveria ser recusado"
        assert "condicao_clima" in r.text
        repo_mock.inserir_avaliacao.assert_not_called()

    @pytest.mark.parametrize(
        "precipitacao,condicao",
        [
            (0.0, "ensolarado"), (2.0, "nublado"),        # teto inclusivo de cada faixa
            (2.1, "nublado"), (20.0, "chuvoso"),
            (20.1, "chuvoso"), (50.0, "chuvoso"),
            (50.1, "tempestade"), (120.0, "chuvoso"),
        ],
    )
    def test_clima_compativel_com_a_chuva_e_aceito(self, auth, precipitacao, condicao):
        leitura = {
            **LEITURA_VALIDA, **CLIMA_FALSO,
            "precipitacao_mm": precipitacao, "condicao_clima": condicao,
        }
        r, _ = _post_com_cadastro(auth, leitura)
        assert r.status_code == 201, r.text

    def test_so_um_dos_dois_campos_de_clima_nao_e_checado(self, auth):
        """Sem o par completo nao ha o que cruzar: a Open-Meteo completa o resto."""
        leitura = {**LEITURA_VALIDA, "condicao_clima": "tempestade"}
        r, _ = _post_com_cadastro(auth, leitura)
        assert r.status_code == 201, r.text

    @pytest.mark.parametrize(
        "cadastro",
        [
            {**EQUIPAMENTO_FALSO, "tem_iot": False},
            {**EQUIPAMENTO_FALSO, "tipo_equipamento": "implemento"},
        ],
        ids=["sem_iot", "implemento"],
    )
    def test_temperatura_motor_sem_sensor_e_recusada(self, auth, cadastro):
        """Regras 1 e 10: so equipamento com IoT e motor proprio mede temperatura."""
        r, repo_mock = _post_com_cadastro(auth, LEITURA_VALIDA, equipamento=cadastro)
        assert r.status_code == 422
        assert "temperatura_motor" in r.json()["detail"]
        repo_mock.inserir_avaliacao.assert_not_called()

    def test_equipamento_sem_iot_sem_temperatura_motor_e_aceito(self, auth):
        leitura = {k: v for k, v in LEITURA_VALIDA.items() if k != "temperatura_motor"}
        r, _ = _post_com_cadastro(auth, leitura, equipamento={**EQUIPAMENTO_FALSO, "tem_iot": False})
        assert r.status_code == 201, r.text


# ---------------------------------------------------------------------------
# 3. Scoring end-to-end (dependencias externas mockadas)
# ---------------------------------------------------------------------------

class TestScoring:
    @pytest.fixture
    def resposta(self, auth):
        with patch("backend.services.scoring.repo") as repo_mock, \
             patch("backend.services.clima.buscar", return_value=CLIMA_FALSO), \
             patch("backend.services.auditoria.registrar"):
            repo_mock.buscar_equipamento.return_value = EQUIPAMENTO_FALSO
            repo_mock.operador_existe.return_value = True
            repo_mock.inserir_avaliacao.return_value = 4242
            r = client.post("/avaliacoes", json=LEITURA_VALIDA, headers=auth)
        assert r.status_code == 201, r.text
        return r.json()

    def test_devolve_score_no_dominio(self, resposta):
        assert 0.0 <= resposta["risco_score"] <= 100.0

    def test_score_nunca_vem_sozinho(self, resposta):
        """RF-10: score sempre acompanhado de faixa e decomposicao."""
        for chave in ("faixa_risco", "contribuicoes_por_grupo", "top_fatores"):
            assert chave in resposta, f"resposta sem '{chave}'"

    def test_decomposicao_cobre_os_seis_grupos(self, resposta):
        esperados = {
            "ambiental", "geografico", "operacional",
            "equipamento", "operador", "manutencao",
        }
        assert set(resposta["contribuicoes_por_grupo"]) == esperados

    def test_recomendacoes_vem_com_criterio(self, resposta):
        """S4-25: acao preventiva com o criterio que a disparou."""
        assert isinstance(resposta["recomendacoes"], list)
        for rec in resposta["recomendacoes"]:
            assert set(rec) == {"id", "publico", "acao", "criterio"}
        if resposta["faixa_risco"] != "baixo":
            assert resposta["recomendacoes"], "faixa media/alta sem recomendacao"

    def test_top_fatores_tem_shape_do_contrato(self, resposta):
        assert len(resposta["top_fatores"]) == 5
        for fator in resposta["top_fatores"]:
            assert set(fator) == {"feature", "valor", "shap_value", "grupo"}

    def test_persiste_avaliacao_e_predicao_ligadas(self, auth):
        with patch("backend.services.scoring.repo") as repo_mock, \
             patch("backend.services.clima.buscar", return_value=CLIMA_FALSO), \
             patch("backend.services.auditoria.registrar"):
            repo_mock.buscar_equipamento.return_value = EQUIPAMENTO_FALSO
            repo_mock.operador_existe.return_value = True
            repo_mock.inserir_avaliacao.return_value = 4242
            client.post("/avaliacoes", json=LEITURA_VALIDA, headers=auth)

            repo_mock.inserir_avaliacao.assert_called_once()
            repo_mock.inserir_predicao.assert_called_once()
            predicao = repo_mock.inserir_predicao.call_args[0][0]
            assert predicao["avaliacao_id"] == 4242
            assert predicao["modelo_versao"]
            assert len(predicao["top_fatores_shap"]) == 5

    def test_grava_procedencia_do_dado(self, auth):
        with patch("backend.services.scoring.repo") as repo_mock, \
             patch("backend.services.clima.buscar", return_value=CLIMA_FALSO), \
             patch("backend.services.auditoria.registrar"):
            repo_mock.buscar_equipamento.return_value = EQUIPAMENTO_FALSO
            repo_mock.operador_existe.return_value = True
            repo_mock.inserir_avaliacao.return_value = 1
            client.post("/avaliacoes", json=LEITURA_VALIDA, headers=auth)
            linha = repo_mock.inserir_avaliacao.call_args[0][0]
        assert linha["fonte"] == "telemetria"
        assert linha["clima_origem"] == "open-meteo"

    def test_atraso_manutencao_e_derivado_no_servidor(self, auth):
        """Regra 14: 120/180 = 0.667 e 300/500 = 0.6 -> vence 0.667, nao atrasada."""
        with patch("backend.services.scoring.repo") as repo_mock, \
             patch("backend.services.clima.buscar", return_value=CLIMA_FALSO), \
             patch("backend.services.auditoria.registrar"):
            repo_mock.buscar_equipamento.return_value = EQUIPAMENTO_FALSO
            repo_mock.operador_existe.return_value = True
            repo_mock.inserir_avaliacao.return_value = 1
            client.post("/avaliacoes", json=LEITURA_VALIDA, headers=auth)
            linha = repo_mock.inserir_avaliacao.call_args[0][0]
        assert linha["atraso_manutencao_pct"] == pytest.approx(0.667, abs=0.001)
        assert linha["manutencao_atrasada"] is False


# ---------------------------------------------------------------------------
# 4. Resiliencia: falha da API externa nao derruba o fluxo
# ---------------------------------------------------------------------------

class TestResilienciaClima:
    def test_open_meteo_fora_cai_para_o_payload(self, auth):
        with patch("backend.services.scoring.repo") as repo_mock, \
             patch("backend.services.clima.buscar", return_value=None), \
             patch("backend.services.auditoria.registrar"):
            repo_mock.buscar_equipamento.return_value = EQUIPAMENTO_FALSO
            repo_mock.operador_existe.return_value = True
            repo_mock.inserir_avaliacao.return_value = 1
            r = client.post(
                "/avaliacoes",
                json={**LEITURA_VALIDA, **CLIMA_FALSO},
                headers=auth,
            )
        assert r.status_code == 201
        assert r.json()["clima_origem"] == "payload"

    def test_sem_clima_em_lugar_nenhum_recusa_com_502(self, auth):
        """Nao se inventa clima para alimentar o modelo."""
        with patch("backend.services.scoring.repo") as repo_mock, \
             patch("backend.services.clima.buscar", return_value=None), \
             patch("backend.services.auditoria.registrar"):
            repo_mock.buscar_equipamento.return_value = EQUIPAMENTO_FALSO
            repo_mock.operador_existe.return_value = True
            r = client.post("/avaliacoes", json=LEITURA_VALIDA, headers=auth)
        assert r.status_code == 502
        repo_mock.inserir_avaliacao.assert_not_called()

    def test_predicao_falha_reverte_avaliacao(self, auth):
        """RF-03: o registro nao pode ficar orfao, sem predicao."""
        with patch("backend.services.scoring.repo") as repo_mock, \
             patch("backend.services.clima.buscar", return_value=CLIMA_FALSO), \
             patch("backend.services.auditoria.registrar"):
            repo_mock.buscar_equipamento.return_value = EQUIPAMENTO_FALSO
            repo_mock.operador_existe.return_value = True
            repo_mock.inserir_avaliacao.return_value = 999
            repo_mock.inserir_predicao.side_effect = RuntimeError("banco caiu")
            r = client.post("/avaliacoes", json=LEITURA_VALIDA, headers=auth)
        assert r.status_code == 500
        repo_mock.remover_avaliacao.assert_called_once_with(999)
