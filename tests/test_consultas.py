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


class TestSemAvaliacao:
    def test_equipamento_sem_avaliacao_mantem_o_contrato(self):
        with patch.object(consultas.repo, "listar_equipamentos", return_value=[EQUIPAMENTO]), \
             patch.object(consultas.repo, "listar_avaliacoes_resumo", return_value=[]):
            (item,) = consultas.listar_equipamentos()
        assert item["total_avaliacoes"] == 0
        assert item["risco_score"] == 0.0
        assert item["faixa_risco"] == "baixo"
