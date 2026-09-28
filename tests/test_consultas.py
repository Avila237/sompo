"""
Faixa de risco com uma unica fonte (S4-16).

A faixa e derivada do score cru no momento da predicao e gravada junto com ele,
ja arredondado a duas casas. Um score cru de 33.004 vira risco_score=33.0 com
faixa_risco='medio'. Recalcular a faixa a partir do 33.0 gravado daria 'baixo':
as rotas de leitura tem de devolver a faixa gravada, nao recalcular.
"""

import os
import sys
from unittest.mock import patch

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.services import consultas  # noqa: E402

EQUIPAMENTO = {
    "equipamento_id": "EQ-0001",
    "modelo_equipamento": "John Deere 7J195",
    "tipo_equipamento": "trator",
    "idade_equipamento": 5,
    "historico_sinistros": 1,
    "tem_iot": True,
}

# Na fronteira: gravado como 33.0, mas a faixa gravada (do score cru) e 'medio'.
AVALIACAO_NA_FRONTEIRA = {
    "avaliacao_id": 1,
    "equipamento_id": "EQ-0001",
    "operador_id": "OP-0001",
    "risco_score": 33.0,
    "faixa_risco": "medio",
    "timestamp": "2026-01-01T10:00:00+00:00",
    "latitude": -24.0,
    "longitude": -51.0,
    "tipo_operacao": "colheita",
}


@pytest.fixture
def fronteira():
    with patch.object(consultas.repo, "listar_equipamentos", return_value=[EQUIPAMENTO]), \
         patch.object(consultas.repo, "listar_avaliacoes_resumo", return_value=[AVALIACAO_NA_FRONTEIRA]):
        yield


class TestFaixaGravadaPrevalece:
    def test_equipamentos_devolve_a_faixa_gravada(self, fronteira):
        (item,) = consultas.listar_equipamentos()
        assert item["faixa_risco"] == "medio"

    def test_kpis_contam_pela_faixa_gravada(self, fronteira):
        assert consultas.kpis()["avaliacoes_por_faixa"] == {"baixo": 0, "medio": 1, "alto": 0}

    def test_alertas_usam_a_faixa_gravada(self, fronteira):
        # faixa_minima=medio: a avaliacao entra porque a faixa gravada e 'medio'
        (alerta,) = consultas.alertas(limite=5, faixa_minima="medio")
        assert alerta["faixa_risco"] == "medio"

    def test_por_operacao_conta_alto_pela_faixa_gravada(self):
        alto_gravado = {**AVALIACAO_NA_FRONTEIRA, "risco_score": 66.0, "faixa_risco": "alto"}
        with patch.object(consultas.repo, "listar_avaliacoes_resumo", return_value=[alto_gravado]):
            (op,) = consultas.agregado_por_operacao()
        assert op["avaliacoes_risco_alto"] == 1


class TestRecomendacoesNoDetalhe:
    def test_detalhe_usa_leitura_e_cadastro(self):
        """historico_sinistros vem do cadastro; horas_operacao, da avaliacao."""
        equipamento = {**EQUIPAMENTO, "historico_sinistros": 5}
        ultima = {**AVALIACAO_NA_FRONTEIRA, "faixa_risco": "alto", "horas_operacao": 10.0}
        with patch.object(consultas.repo, "buscar_equipamento", return_value=equipamento), \
             patch.object(consultas.repo, "ultima_avaliacao", return_value=ultima), \
             patch.object(consultas.repo, "predicao_de", return_value=None), \
             patch.object(consultas.repo, "listar_avaliacoes_resumo", return_value=[ultima]):
            detalhe = consultas.detalhe_equipamento("EQ-0001")
        assert "historico_e_jornada_longa" in [r["id"] for r in detalhe["recomendacoes"]]

    def test_sem_avaliacao_nao_ha_recomendacao(self):
        with patch.object(consultas.repo, "buscar_equipamento", return_value=EQUIPAMENTO), \
             patch.object(consultas.repo, "ultima_avaliacao", return_value=None), \
             patch.object(consultas.repo, "listar_avaliacoes_resumo", return_value=[]):
            detalhe = consultas.detalhe_equipamento("EQ-0001")
        assert detalhe["recomendacoes"] == []


class TestSemAvaliacao:
    def test_equipamento_sem_avaliacao_mantem_o_contrato(self):
        with patch.object(consultas.repo, "listar_equipamentos", return_value=[EQUIPAMENTO]), \
             patch.object(consultas.repo, "listar_avaliacoes_resumo", return_value=[]):
            (item,) = consultas.listar_equipamentos()
        assert item["total_avaliacoes"] == 0
        assert item["risco_score"] == 0.0
        assert item["faixa_risco"] == "baixo"


# ---------------------------------------------------------------------------
# Manutenção da última avaliação em GET /equipamentos (S4-36 · BRA-469)
# ---------------------------------------------------------------------------

def _aval_manut(aid, ts, atrasada, pct, dias):
    return {
        **AVALIACAO_NA_FRONTEIRA, "avaliacao_id": aid, "timestamp": ts,
        "manutencao_atrasada": atrasada, "atraso_manutencao_pct": pct, "ultima_manutencao_dias": dias,
    }


class TestManutencaoNaLista:
    """A tela do técnico ordena a frota pelo atraso de manutenção da última avaliação."""

    def test_campos_vem_da_avaliacao_mais_recente(self):
        antiga = _aval_manut(1, "2026-01-01T10:00:00+00:00", False, 0.4, 60)
        recente = _aval_manut(2, "2026-03-01T10:00:00+00:00", True, 1.38, 208)
        with patch.object(consultas.repo, "listar_equipamentos", return_value=[EQUIPAMENTO]), \
             patch.object(consultas.repo, "listar_avaliacoes_resumo", return_value=[antiga, recente]):
            (item,) = consultas.listar_equipamentos()
        assert item["manutencao_atrasada"] is True
        assert item["atraso_manutencao_pct"] == 1.38
        assert item["ultima_manutencao_dias"] == 208

    def test_sem_avaliacao_os_tres_campos_sao_nulos(self):
        with patch.object(consultas.repo, "listar_equipamentos", return_value=[EQUIPAMENTO]), \
             patch.object(consultas.repo, "listar_avaliacoes_resumo", return_value=[]):
            (item,) = consultas.listar_equipamentos()
        assert item["manutencao_atrasada"] is None
        assert item["atraso_manutencao_pct"] is None
        assert item["ultima_manutencao_dias"] is None

    def test_avaliacao_sem_os_campos_nao_quebra(self):
        """Linha antiga sem as colunas (ou valor nulo no banco): campo nulo, sem KeyError."""
        with patch.object(consultas.repo, "listar_equipamentos", return_value=[EQUIPAMENTO]), \
             patch.object(consultas.repo, "listar_avaliacoes_resumo", return_value=[AVALIACAO_NA_FRONTEIRA]):
            (item,) = consultas.listar_equipamentos()
        assert item["manutencao_atrasada"] is None
        assert item["atraso_manutencao_pct"] is None
        assert item["ultima_manutencao_dias"] is None

    def test_resumo_seleciona_as_colunas_de_manutencao(self):
        from backend.db import repository
        capturado = {}

        def falso_paginado(tabela, colunas, ordem):
            capturado["colunas"] = colunas
            return []

        repository._cache.pop("avaliacoes", None)
        try:
            with patch.object(repository, "_paginado", side_effect=falso_paginado):
                repository.listar_avaliacoes_resumo()
        finally:
            repository._cache.pop("avaliacoes", None)
        for coluna in ("manutencao_atrasada", "atraso_manutencao_pct", "ultima_manutencao_dias"):
            assert coluna in capturado["colunas"]


class TestCamposInternosForaDoDetalhe:
    """leitura_id e payload_hash sao da idempotencia (S4-12), nao de quem le."""

    def test_detalhe_nao_devolve_leitura_id_nem_payload_hash(self):
        ultima = {
            **AVALIACAO_NA_FRONTEIRA,
            "leitura_id": "11111111-1111-1111-1111-111111111111",
            "payload_hash": "a" * 64,
        }
        with patch.object(consultas.repo, "buscar_equipamento", return_value=EQUIPAMENTO), \
             patch.object(consultas.repo, "ultima_avaliacao", return_value=ultima), \
             patch.object(consultas.repo, "predicao_de", return_value=None), \
             patch.object(consultas.repo, "listar_avaliacoes_resumo", return_value=[ultima]):
            detalhe = consultas.detalhe_equipamento("EQ-0001")
        assert "leitura_id" not in detalhe["ultima_avaliacao"]
        assert "payload_hash" not in detalhe["ultima_avaliacao"]
        # O resto da linha segue completo.
        assert detalhe["ultima_avaliacao"] == AVALIACAO_NA_FRONTEIRA
        assert all(set(h) == {"timestamp", "risco_score"} for h in detalhe["historico"])
