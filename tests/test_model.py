import json
import os
import sys

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import accuracy_score

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.ml.train import BOOL_COLS, CAT_COLS, EXCLUDE_COLS, derive_faixa, preprocess_features

MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
DATA_PATH = os.path.join(PROJECT_ROOT, "data", "dataset_safefield.parquet")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def model():
    return joblib.load(os.path.join(MODELS_DIR, "xgboost_model.joblib"))


@pytest.fixture(scope="module")
def encoder():
    return joblib.load(os.path.join(MODELS_DIR, "encoder.joblib"))


@pytest.fixture(scope="module")
def features():
    with open(os.path.join(MODELS_DIR, "features.json")) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def metrics():
    with open(os.path.join(MODELS_DIR, "metrics.json")) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def dataset():
    return pd.read_parquet(DATA_PATH)


# ---------------------------------------------------------------------------
# Scenario helpers
# ---------------------------------------------------------------------------

LOW_RISK_RAW = {
    "temperatura_ar": 24.0,
    "precipitacao_mm": 0.0,
    "umidade_solo": 12.0,
    "velocidade_vento": 4.0,
    "condicao_clima": "ensolarado",
    "latitude": -15.0,
    "longitude": -47.0,
    "tipo_solo": "arenoso",
    "distancia_agua_m": 4500.0,
    "declividade": 1.0,
    "tipo_operacao": "parado",
    "velocidade_kmh": 0.0,
    "vibracao_g": None,
    "temperatura_motor": None,
    "horas_operacao": 0.5,
    "horario_operacao": 10,
    "tipo_equipamento": "implemento",
    "idade_equipamento": 1,
    "historico_sinistros": 0,
    "tem_iot": False,
    "pct_velocidade_acima_recomendada": 0.0,
    "freq_eventos_bruscos": 0.0,
    "pct_operacoes_noturnas": 5.0,
    "score_operador_historico": 5.0,
    "ultima_manutencao_dias": 20,
    "ultima_manutencao_horas_op": 40.0,
    "intervalo_manut_recomendado_dias": 365,
    "intervalo_manut_recomendado_horas": 1500,
    "manutencao_atrasada": False,
    "atraso_manutencao_pct": 0.08,
}

HIGH_RISK_RAW = {
    "temperatura_ar": 18.0,
    "precipitacao_mm": 90.0,
    "umidade_solo": 85.0,
    "velocidade_vento": 60.0,
    "condicao_clima": "tempestade",
    "latitude": -15.0,
    "longitude": -47.0,
    "tipo_solo": "argiloso",
    "distancia_agua_m": 15.0,
    "declividade": 30.0,
    "tipo_operacao": "transporte",
    "velocidade_kmh": 35.0,
    "vibracao_g": 3.5,
    "temperatura_motor": 110.0,
    "horas_operacao": 18.0,
    "horario_operacao": 23,
    "tipo_equipamento": "colheitadeira",
    "idade_equipamento": 20,
    "historico_sinistros": 9,
    "tem_iot": True,
    "pct_velocidade_acima_recomendada": 85.0,
    "freq_eventos_bruscos": 18.0,
    "pct_operacoes_noturnas": 75.0,
    "score_operador_historico": 90.0,
    "ultima_manutencao_dias": 400,
    "ultima_manutencao_horas_op": 1800.0,
    "intervalo_manut_recomendado_dias": 180,
    "intervalo_manut_recomendado_horas": 500,
    "manutencao_atrasada": True,
    "atraso_manutencao_pct": 2.5,
}


def make_input(raw: dict, features: list, encoder):
    df = pd.DataFrame([raw])[features]
    return preprocess_features(df, encoder)


# ---------------------------------------------------------------------------
# Artefatos
# ---------------------------------------------------------------------------

class TestArtifacts:
    def test_model_file_exists(self):
        assert os.path.isfile(os.path.join(MODELS_DIR, "xgboost_model.joblib"))

    def test_encoder_file_exists(self):
        assert os.path.isfile(os.path.join(MODELS_DIR, "encoder.joblib"))

    def test_features_file_exists(self):
        assert os.path.isfile(os.path.join(MODELS_DIR, "features.json"))

    def test_metrics_file_exists(self):
        assert os.path.isfile(os.path.join(MODELS_DIR, "metrics.json"))

    def test_model_loads(self, model):
        assert model is not None

    def test_encoder_loads(self, encoder):
        assert encoder is not None

    def test_features_loads(self, features):
        assert isinstance(features, list)

    def test_metrics_loads(self, metrics):
        assert isinstance(metrics, dict)

    def test_feature_count_is_30(self, features):
        assert len(features) == 30, f"Expected 30 features, got {len(features)}"

    def test_features_do_not_contain_excluded_columns(self, features):
        feature_set = set(features)
        for col in EXCLUDE_COLS:
            assert col not in feature_set, f"Excluded col {col!r} found in features"


# ---------------------------------------------------------------------------
# Predicoes
# ---------------------------------------------------------------------------

class TestPredicoes:
    def test_predict_returns_floats(self, model, encoder, features, dataset):
        X = preprocess_features(dataset[features].copy(), encoder)
        preds = model.predict(X[:10])
        assert preds.dtype.kind == "f", f"Expected float, got {preds.dtype}"

    def test_predict_correct_shape(self, model, encoder, features, dataset):
        X = preprocess_features(dataset[features].copy(), encoder)
        preds = model.predict(X[:50])
        assert preds.shape == (50,)

    def test_predict_accepts_nulls_without_error(self, model, encoder, features):
        X = make_input(LOW_RISK_RAW, features, encoder)
        preds = model.predict(X)
        assert len(preds) == 1

    def test_predict_is_deterministic(self, model, encoder, features):
        X = make_input(LOW_RISK_RAW, features, encoder)
        assert model.predict(X)[0] == model.predict(X)[0]

    def test_low_risk_scenario_score_below_40(self, model, encoder, features):
        X = make_input(LOW_RISK_RAW, features, encoder)
        score = float(model.predict(X)[0])
        assert score < 40, f"Low-risk scenario returned {score:.2f}, expected < 40"

    def test_high_risk_scenario_score_above_60(self, model, encoder, features):
        X = make_input(HIGH_RISK_RAW, features, encoder)
        score = float(model.predict(X)[0])
        assert score > 60, f"High-risk scenario returned {score:.2f}, expected > 60"


# ---------------------------------------------------------------------------
# Metricas
# ---------------------------------------------------------------------------

class TestMetricas:
    def test_mae_below_10(self, metrics):
        assert metrics["mae"] < 10, f"MAE = {metrics['mae']} (threshold: 10)"

    def test_rmse_below_15(self, metrics):
        assert metrics["rmse"] < 15, f"RMSE = {metrics['rmse']} (threshold: 15)"

    def test_r2_above_080(self, metrics):
        assert metrics["r2"] > 0.80, f"R2 = {metrics['r2']} (threshold: 0.80)"

    def test_accuracy_faixas_above_085(self, metrics):
        assert metrics["accuracy_faixas"] > 0.85, f"Accuracy = {metrics['accuracy_faixas']} (threshold: 0.85)"


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------

class TestEncoding:
    def test_encoder_loads_and_transforms_categoricals(self, encoder, dataset):
        sample = dataset[CAT_COLS].head(5)
        result = encoder.transform(sample)
        assert result.shape == (5, len(CAT_COLS))

    def test_encoder_recognizes_all_dataset_categories(self, encoder, dataset):
        result = encoder.transform(dataset[CAT_COLS])
        assert (result != -1).all(), "Encoder encountered unknown categories from dataset"


# ---------------------------------------------------------------------------
# Faixas derivadas
# ---------------------------------------------------------------------------

class TestFaixasDerivadas:
    def test_derive_faixa_boundary_baixo(self):
        assert derive_faixa(0.0) == "baixo"
        assert derive_faixa(16.5) == "baixo"
        assert derive_faixa(33.0) == "baixo"

    def test_derive_faixa_boundary_medio(self):
        assert derive_faixa(33.1) == "medio"
        assert derive_faixa(50.0) == "medio"
        assert derive_faixa(66.0) == "medio"

    def test_derive_faixa_boundary_alto(self):
        assert derive_faixa(66.1) == "alto"
        assert derive_faixa(83.0) == "alto"
        assert derive_faixa(100.0) == "alto"

    def test_all_three_bands_appear_in_predictions(self, model, encoder, features, dataset):
        X = preprocess_features(dataset[features].copy(), encoder)
        preds = model.predict(X)
        bands = {derive_faixa(float(p)) for p in preds}
        assert bands == {"baixo", "medio", "alto"}, f"Not all bands present. Found: {bands}"