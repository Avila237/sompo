"""
Recomendacoes preventivas (S4-25): regra deterministica, versionada no codigo,
com o criterio que a disparou. Nunca texto gerado.
"""

import os
import sys

import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.services.recomendacoes import PUBLICOS, REGRAS, recomendar  # noqa: E402

# Leitura neutra: nenhuma regra de interacao dispara.
NEUTRA = {
    "precipitacao_mm": 5.0,
    "tipo_solo": "arenoso",
    "velocidade_kmh": 6.0,
    "declividade": 3.0,
    "distancia_agua_m": 2000.0,
    "horario_operacao": 11,
    "idade_equipamento": 4,
    "vibracao_g": 1.0,
    "tipo_operacao": "colheita",
    "horas_operacao": 4.0,
    "historico_sinistros": 1,
    "pct_velocidade_acima_recomendada": 10.0,
    "atraso_manutencao_pct": 0.5,
    "manutencao_atrasada": False,
    "pct_operacoes_noturnas": 10.0,
}


def _ids(recs):
    return [r["id"] for r in recs]


class TestFormato:
    def test_cada_recomendacao_tem_publico_acao_e_criterio(self):
        leitura = {**NEUTRA, "precipitacao_mm": 42.0, "tipo_solo": "argiloso"}
        (rec,) = recomendar(leitura, "alto", [])
        assert set(rec) == {"id", "publico", "acao", "criterio"}
        assert rec["publico"] in PUBLICOS
        assert rec["acao"] and rec["criterio"]

    def test_criterio_traz_os_valores_da_leitura(self):
        leitura = {**NEUTRA, "precipitacao_mm": 42.0, "tipo_solo": "argiloso"}
        (rec,) = recomendar(leitura, "alto", [])
        assert "42" in rec["criterio"] and "argiloso" in rec["criterio"]

    def test_ids_das_regras_sao_unicos(self):
        assert len({r.id for r in REGRAS}) == len(REGRAS)


class TestRegras:
    @pytest.mark.parametrize(
        "ajuste,regra",
        [
            ({"precipitacao_mm": 31.0, "tipo_solo": "argiloso"}, "solo_encharcado"),
            ({"velocidade_kmh": 21.0, "declividade": 16.0}, "tombamento"),
            ({"distancia_agua_m": 150.0, "precipitacao_mm": 26.0}, "margem_alagavel"),
            ({"horario_operacao": 22, "velocidade_kmh": 16.0}, "velocidade_noturna"),
            ({"idade_equipamento": 11, "vibracao_g": 2.1}, "vibracao_equipamento_antigo"),
            ({"tipo_operacao": "transporte", "velocidade_kmh": 26.0, "declividade": 11.0},
             "transporte_em_declive"),
            ({"horas_operacao": 9.0, "horario_operacao": 2}, "fadiga_noturna"),
            ({"historico_sinistros": 4, "horas_operacao": 9.0}, "historico_e_jornada_longa"),
            ({"pct_velocidade_acima_recomendada": 31.0, "precipitacao_mm": 21.0},
             "conducao_agressiva_na_chuva"),
            ({"atraso_manutencao_pct": 1.3, "horas_operacao": 9.0}, "manutencao_vencida_e_uso_intenso"),
            ({"pct_operacoes_noturnas": 51.0, "horario_operacao": 23}, "escala_noturna_habitual"),
            ({"manutencao_atrasada": True, "atraso_manutencao_pct": 1.1}, "manutencao_atrasada"),
        ],
    )
    def test_regra_dispara_na_condicao(self, ajuste, regra):
        assert regra in _ids(recomendar({**NEUTRA, **ajuste}, "medio", []))

    @pytest.mark.parametrize(
        "ajuste",
        [
            {"precipitacao_mm": 30.0, "tipo_solo": "argiloso"},     # limiar estrito: > 30
            {"velocidade_kmh": 20.0, "declividade": 16.0},
            {"horario_operacao": 6, "velocidade_kmh": 16.0},        # 6h ja nao e noturno
            {"historico_sinistros": 3, "horas_operacao": 12.0},     # historico precisa ser >= 4
        ],
    )
    def test_regra_nao_dispara_no_limiar(self, ajuste):
        assert recomendar({**NEUTRA, **ajuste}, "baixo", []) == []

    def test_campo_ausente_nao_quebra_nem_dispara(self):
        leitura = {**NEUTRA, "vibracao_g": None, "idade_equipamento": 20}
        assert "vibracao_equipamento_antigo" not in _ids(recomendar(leitura, "alto", []))


class TestGarantiaParaMedioEAlto:
    def test_sem_regra_usa_o_fator_que_mais_empurrou_o_risco(self):
        fatores = [
            {"feature": "distancia_agua_m", "shap_value": -3.0, "grupo": "geografico"},
            {"feature": "historico_sinistros", "shap_value": 18.6, "grupo": "equipamento"},
        ]
        (rec,) = recomendar({**NEUTRA, "historico_sinistros": 7}, "alto", fatores)
        assert rec["id"] == "fator_dominante"
        assert "historico_sinistros" in rec["criterio"] and "7" in rec["criterio"]
        assert "+18.6" in rec["criterio"]

    def test_sem_regra_e_sem_fator_positivo_ainda_recomenda(self):
        fatores = [{"feature": "declividade", "shap_value": -1.0, "grupo": "geografico"}]
        (rec,) = recomendar(NEUTRA, "medio", fatores)
        assert rec["id"] == "monitorar"
        assert "medio" in rec["criterio"]

    def test_baixo_sem_regra_nao_recomenda(self):
        assert recomendar(NEUTRA, "baixo", [{"feature": "x", "shap_value": 5.0, "grupo": "operador"}]) == []

    def test_regra_disparada_dispensa_o_fallback(self):
        fatores = [{"feature": "historico_sinistros", "shap_value": 18.6, "grupo": "equipamento"}]
        recs = recomendar({**NEUTRA, "precipitacao_mm": 42.0, "tipo_solo": "argiloso"}, "alto", fatores)
        assert "fator_dominante" not in _ids(recs)


@pytest.mark.skipif(
    not os.path.isfile(os.path.join(PROJECT_ROOT, "models", "xgboost_model.joblib")),
    reason="modelo nao treinado",
)
def test_toda_avaliacao_media_ou_alta_do_dataset_recebe_recomendacao():
    """A garantia contra o modelo real, numa amostra do dataset simulado."""
    from backend.ml.predictor import Predictor

    predictor = Predictor(os.path.join(PROJECT_ROOT, "models"))
    df = pd.read_parquet(os.path.join(PROJECT_ROOT, "data", "dataset_safefield.parquet"))
    # 60 linhas: cada predicao com SHAP custa ~0,3 s; a amostra so precisa
    # exercitar as duas faixas.
    amostra = df.sample(60, random_state=7).to_dict("records")
    medio_ou_alto = 0
    for registro in amostra:
        explicacao = predictor.prever(registro)
        if explicacao.faixa_risco == "baixo":
            continue
        medio_ou_alto += 1
        recs = recomendar(registro, explicacao.faixa_risco, explicacao.top_fatores)
        assert recs, f"{registro['equipamento_id']} ({explicacao.faixa_risco}) sem recomendacao"
    assert medio_ou_alto > 0, "amostra sem nenhuma avaliacao media ou alta: teste vazio"
