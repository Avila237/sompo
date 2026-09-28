"""
Autenticacao por tabela e autorizacao por perfil (S4-18).

Matriz perfil x rota (aprovada em 28/09/2026, docs/contrato-api.md):
analista, gestor e tecnico leem a frota inteira; o operador so os equipamentos
que ja operou e nao ve as agregacoes. Envia leitura: o analista por qualquer
operador, o operador so em nome proprio.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.api.main import app  # noqa: E402
from backend.api.routers import auth as rota_auth  # noqa: E402
from backend.api.schemas import LeituraTelemetria  # noqa: E402
from backend.core.security import criar_token, gerar_hash, senha_confere  # noqa: E402
from backend.services import autenticacao  # noqa: E402
from backend.services.scoring import hash_do_payload  # noqa: E402
from tests.conftest import SENHAS, USUARIOS  # noqa: E402
from tests.test_api import CLIMA_FALSO, EQUIPAMENTO_FALSO, LEITURA_VALIDA  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)

DO_OPERADOR = "EQ-0042"
ALHEIO = "EQ-0099"
OPERADOR_ID = "OP-0015"


@pytest.fixture(autouse=True)
def sem_historico_de_tentativas():
    rota_auth.limpar_tentativas()
    yield
    rota_auth.limpar_tentativas()


def _auth(perfil: str, operador_id: str | None = None) -> dict:
    token, _ = criar_token(perfil, perfil, operador_id)
    return {"Authorization": f"Bearer {token}"}


AUTH = {
    "analista": _auth("analista"),
    "gestor": _auth("gestor"),
    "tecnico": _auth("tecnico"),
    "operador": _auth("operador", OPERADOR_ID),
}


@pytest.fixture
def servico():
    """Camada de consultas falsa: a regra testada aqui e a da rota."""
    falso = MagicMock()
    falso.listar_equipamentos.return_value = [
        {"equipamento_id": DO_OPERADOR, "faixa_risco": "alto", "modelo_equipamento": "A"},
        {"equipamento_id": ALHEIO, "faixa_risco": "alto", "modelo_equipamento": "B"},
    ]
    falso.equipamentos_do_operador.return_value = {DO_OPERADOR}
    falso.detalhe_equipamento.return_value = {"equipamento": {}}
    falso.alertas.return_value = []
    falso.kpis.return_value = {}
    falso.agregado_por_operacao.return_value = []
    falso.agregado_por_regiao.return_value = []
    falso.tendencia.return_value = []
    falso.tendencias.return_value = {}
    with patch("backend.api.routers.consultas.consultas", falso):
        yield falso


# ---------------------------------------------------------------------------
# Leitura: perfil x rota
# ---------------------------------------------------------------------------

class TestLeituraPorPerfil:
    @pytest.mark.parametrize("perfil", ["analista", "gestor", "tecnico"])
    def test_frota_ve_todos_os_equipamentos(self, servico, perfil):
        r = client.get("/equipamentos", headers=AUTH[perfil])
        assert r.status_code == 200
        assert {e["equipamento_id"] for e in r.json()["itens"]} == {DO_OPERADOR, ALHEIO}

    def test_operador_ve_so_os_que_operou(self, servico):
        r = client.get("/equipamentos", headers=AUTH["operador"])
        assert r.status_code == 200
        assert [e["equipamento_id"] for e in r.json()["itens"]] == [DO_OPERADOR]
        servico.equipamentos_do_operador.assert_called_once_with(OPERADOR_ID)

    @pytest.mark.parametrize("perfil", ["analista", "gestor", "tecnico", "operador"])
    def test_detalhe_do_proprio_recorte(self, servico, perfil):
        assert client.get(f"/equipamentos/{DO_OPERADOR}", headers=AUTH[perfil]).status_code == 200

    def test_operador_recebe_403_no_detalhe_alheio_sem_consultar(self, servico):
        r = client.get(f"/equipamentos/{ALHEIO}", headers=AUTH["operador"])
        assert r.status_code == 403
        servico.detalhe_equipamento.assert_not_called()

    def test_operador_nao_descobre_se_equipamento_alheio_existe(self, servico):
        servico.detalhe_equipamento.return_value = None
        assert client.get("/equipamentos/EQ-9999", headers=AUTH["operador"]).status_code == 403
        assert client.get("/equipamentos/EQ-9999", headers=AUTH["analista"]).status_code == 404

    @pytest.mark.parametrize("perfil", ["analista", "gestor", "tecnico"])
    def test_alertas_da_frota_sem_recorte(self, servico, perfil):
        assert client.get("/alertas", headers=AUTH[perfil]).status_code == 200
        assert servico.alertas.call_args.kwargs["equipamentos"] is None

    def test_alertas_do_operador_recortados(self, servico):
        assert client.get("/alertas", headers=AUTH["operador"]).status_code == 200
        assert servico.alertas.call_args.kwargs["equipamentos"] == {DO_OPERADOR}

    @pytest.mark.parametrize("rota", ["/kpis", "/tendencias?eixo=equipamento"])
    @pytest.mark.parametrize("perfil", ["analista", "gestor", "tecnico"])
    def test_agregacoes_liberadas_para_a_frota(self, servico, rota, perfil):
        assert client.get(rota, headers=AUTH[perfil]).status_code == 200

    @pytest.mark.parametrize("rota", ["/kpis", "/tendencias?eixo=equipamento"])
    def test_agregacoes_negadas_ao_operador(self, servico, rota):
        r = client.get(rota, headers=AUTH["operador"])
        assert r.status_code == 403
        assert "operador" in r.json()["detail"]


class TestRecorteNoServico:
    def test_equipamentos_do_operador(self):
        from backend.services import consultas

        avals = [
            {"equipamento_id": "EQ-0001", "operador_id": "OP-0015"},
            {"equipamento_id": "EQ-0002", "operador_id": "OP-0099"},
            {"equipamento_id": "EQ-0001", "operador_id": "OP-0015"},
        ]
        with patch.object(consultas.repo, "listar_avaliacoes_resumo", return_value=avals):
            assert consultas.equipamentos_do_operador("OP-0015") == {"EQ-0001"}
            assert consultas.equipamentos_do_operador("OP-7777") == set()

    def test_alertas_filtra_antes_do_limite(self):
        """O recorte vem antes do limite: senao o operador receberia menos alertas que existem."""
        from backend.services import consultas

        base = {"operador_id": "OP-0001", "risco_score": 80, "faixa_risco": "alto"}
        avals = [
            {**base, "avaliacao_id": 1, "equipamento_id": "EQ-0002", "timestamp": "2026-09-03"},
            {**base, "avaliacao_id": 2, "equipamento_id": "EQ-0002", "timestamp": "2026-09-02"},
            {**base, "avaliacao_id": 3, "equipamento_id": "EQ-0001", "timestamp": "2026-09-01"},
        ]
        with patch.object(consultas.repo, "listar_avaliacoes_resumo", return_value=avals):
            (alerta,) = consultas.alertas(limite=1, equipamentos={"EQ-0001"})
        assert alerta["avaliacao_id"] == 3


# ---------------------------------------------------------------------------
# Envio: POST /avaliacoes
# ---------------------------------------------------------------------------

def _enviar(auth, leitura, recorte=None, anterior=None):
    recorte = {LEITURA_VALIDA["equipamento_id"]} if recorte is None else recorte
    with patch("backend.services.scoring.repo") as repo_mock, \
         patch("backend.services.consultas.equipamentos_do_operador", return_value=recorte), \
         patch("backend.services.clima.buscar", return_value=CLIMA_FALSO), \
         patch("backend.services.auditoria.registrar") as auditoria:
        repo_mock.buscar_equipamento.return_value = EQUIPAMENTO_FALSO
        repo_mock.operador_existe.return_value = True
        repo_mock.buscar_por_leitura.return_value = anterior
        repo_mock.registrar_avaliacao.return_value = (1, False)
        r = client.post("/avaliacoes", json=leitura, headers=auth)
    return r, repo_mock, auditoria


class TestEnvioPorPerfil:
    def test_analista_envia_por_qualquer_operador(self):
        r, _, _ = _enviar(AUTH["analista"], LEITURA_VALIDA)
        assert r.status_code == 201, r.text

    def test_operador_envia_em_nome_proprio(self):
        auth = _auth("operador", LEITURA_VALIDA["operador_id"])
        r, _, _ = _enviar(auth, LEITURA_VALIDA)
        assert r.status_code == 201, r.text

    def test_operador_nao_envia_em_nome_de_outro_e_fica_auditado(self):
        auth = _auth("operador", "OP-7777")
        r, repo_mock, auditoria = _enviar(auth, LEITURA_VALIDA)
        assert r.status_code == 403
        assert "OP-7777" in r.json()["detail"]
        repo_mock.registrar_avaliacao.assert_not_called()
        assert [c.args[3] for c in auditoria.call_args_list] == ["erro"]

    def test_operador_nao_amplia_o_recorte_enviando_para_equipamento_alheio(self):
        """Sem isto, uma leitura em nome proprio num equipamento alheio o poria no recorte."""
        auth = _auth("operador", LEITURA_VALIDA["operador_id"])
        assert LEITURA_VALIDA["equipamento_id"] != "EQ-0777"
        r, repo_mock, auditoria = _enviar(auth, LEITURA_VALIDA, recorte={"EQ-0777"})
        assert r.status_code == 403
        repo_mock.buscar_equipamento.assert_not_called()
        repo_mock.registrar_avaliacao.assert_not_called()
        assert [c.args[3] for c in auditoria.call_args_list] == ["erro"]

    def test_operador_nao_descobre_equipamento_inexistente_pelo_envio(self):
        auth = _auth("operador", LEITURA_VALIDA["operador_id"])
        leitura = {**LEITURA_VALIDA, "equipamento_id": "EQ-9999"}
        r, _, _ = _enviar(auth, leitura)
        assert r.status_code == 403, "inexistente e alheio respondem igual"

    @pytest.mark.parametrize("perfil", ["gestor", "tecnico"])
    def test_perfis_de_leitura_nao_enviam(self, perfil):
        r, repo_mock, auditoria = _enviar(AUTH[perfil], LEITURA_VALIDA)
        assert r.status_code == 403
        repo_mock.buscar_equipamento.assert_not_called()
        assert [c.args[3] for c in auditoria.call_args_list] == ["erro"]


class TestAutorizacaoAntesDoReenvio:
    """
    Reenvio de leitura_id ja gravada (S4-12) nao pode pular a matriz (S4-18):
    na ordem inversa, gestor e tecnico receberiam 200 com o resultado gravado
    e um operador leria a avaliacao de outro.
    """

    LEITURA_ID = "11111111-1111-1111-1111-111111111111"

    def _ja_gravada(self):
        leitura = LeituraTelemetria(**LEITURA_VALIDA, leitura_id=self.LEITURA_ID)
        # Mesmo hash do payload original: na ordem errada, isto viraria 200.
        anterior = {"avaliacao_id": 77, "payload_hash": hash_do_payload(leitura.model_dump(mode="json"))}
        return {**LEITURA_VALIDA, "leitura_id": self.LEITURA_ID}, anterior

    @pytest.mark.parametrize("perfil", ["gestor", "tecnico"])
    def test_perfil_de_leitura_nao_recebe_o_resultado_gravado(self, perfil):
        leitura, anterior = self._ja_gravada()
        r, repo_mock, auditoria = _enviar(AUTH[perfil], leitura, anterior=anterior)
        assert r.status_code == 403, r.text
        repo_mock.buscar_por_leitura.assert_not_called()
        assert [c.args[3] for c in auditoria.call_args_list] == ["erro"]

    def test_operador_nao_le_o_reenvio_de_outro_operador(self):
        leitura, anterior = self._ja_gravada()
        r, repo_mock, auditoria = _enviar(_auth("operador", "OP-7777"), leitura, anterior=anterior)
        assert r.status_code == 403, r.text
        repo_mock.buscar_por_leitura.assert_not_called()
        assert [c.args[3] for c in auditoria.call_args_list] == ["erro"]


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------

class TestConteudoDoToken:
    def test_perfil_fora_da_lista_e_token_invalido(self):
        r = client.get("/equipamentos", headers=_auth("administrador"))
        assert r.status_code == 401

    def test_operador_sem_vinculo_e_token_invalido(self):
        r = client.get("/equipamentos", headers=_auth("operador", None))
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# Login contra a tabela
# ---------------------------------------------------------------------------

class TestLogin:
    def test_operador_recebe_o_proprio_operador_id(self):
        r = client.post("/auth/token", json={"usuario": "operador", "senha": SENHAS["operador"]})
        assert r.status_code == 200
        assert r.json()["perfil"] == "operador"
        assert r.json()["operador_id"] == "OP-0015"

    @pytest.mark.parametrize("perfil", ["analista", "gestor", "tecnico"])
    def test_perfis_de_frota_sem_operador_id(self, perfil):
        r = client.post("/auth/token", json={"usuario": perfil, "senha": SENHAS[perfil]})
        assert r.status_code == 200
        assert r.json()["operador_id"] is None

    def test_usuario_desativado_nao_entra(self):
        r = client.post("/auth/token", json={"usuario": "desligado", "senha": SENHAS["desligado"]})
        assert r.status_code == 401

    def test_usuario_inexistente_tambem_calcula_hash(self):
        """Mesmo custo de tempo que uma senha errada: nao revela quem existe."""
        with patch.object(autenticacao, "senha_confere", wraps=senha_confere) as conferir:
            r = client.post("/auth/token", json={"usuario": "ninguem", "senha": "qualquer"})
        assert r.status_code == 401
        conferir.assert_called_once()

    @pytest.mark.parametrize("armazenado", [
        "lixo",
        "scrypt$99999999999999999999999$8$5$AA==$AA==",
        "scrypt$-2$8$5$AA==$AA==",
    ])
    def test_hash_malformado_no_banco_recusa_sem_500(self, armazenado):
        with patch.dict(USUARIOS, {"quebrado": {**USUARIOS["analista"], "senha_hash": armazenado}}), \
             patch.object(autenticacao, "senha_confere", wraps=senha_confere) as conferir:
            r = client.post("/auth/token", json={"usuario": "quebrado", "senha": "x"})
        assert r.status_code == 401
        # Prova que o hash quebrado foi mesmo conferido, e nao que o usuario sumiu.
        conferir.assert_called_once_with("x", armazenado)

    def test_falhas_em_paralelo_nao_furam_o_limite(self):
        """A tentativa conta antes do hash: requisicoes simultaneas nao passam todas pela checagem."""
        from concurrent.futures import ThreadPoolExecutor

        def tentar(_):
            corpo = {"usuario": "analista", "senha": "errada"}
            return client.post("/auth/token", json=corpo).status_code

        with ThreadPoolExecutor(max_workers=12) as pool:
            codigos = list(pool.map(tentar, range(12)))
        assert codigos.count(401) <= rota_auth.MAX_FALHAS
        assert codigos.count(429) >= 12 - rota_auth.MAX_FALHAS

    def test_sucesso_nao_consome_tentativa(self):
        for _ in range(rota_auth.MAX_FALHAS + 1):
            r = client.post("/auth/token", json={"usuario": "analista", "senha": SENHAS["analista"]})
            assert r.status_code == 200

    @pytest.mark.parametrize("corpo", [
        {"usuario": "", "senha": "x"},
        {"usuario": "analista", "senha": ""},
        {"usuario": "a" * 61, "senha": "x"},
        {"usuario": "analista", "senha": "x" * 257},
        {"usuario": "ana\u0000lista", "senha": "x"},
        {"usuario": "ana\nlista", "senha": "x"},
    ])
    def test_entrada_fora_do_limite_e_422(self, corpo):
        assert client.post("/auth/token", json=corpo).status_code == 422


class TestHash:
    def test_sal_diferente_a_cada_hash(self):
        assert gerar_hash("mesma-senha") != gerar_hash("mesma-senha")

    def test_confere_so_a_senha_certa(self):
        h = gerar_hash("coração-1")
        assert senha_confere("coração-1", h)
        assert not senha_confere("coracao-1", h)

    def test_parametros_ficam_no_hash(self):
        algoritmo, n, r, p, _, _ = gerar_hash("x").split("$")
        assert (algoritmo, n, r, p) == ("scrypt", str(2**14), "8", "5")

    @pytest.mark.parametrize("armazenado", ["", "lixo", "bcrypt$a$b$c$d$e", "scrypt$x$8$5$AA==$AA=="])
    def test_hash_desconhecido_ou_malformado_nao_confere(self, armazenado):
        assert not senha_confere("qualquer", armazenado)
