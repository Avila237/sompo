import json
import os
import sys

import joblib
import pandas as pd
import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.ml.mlflow_tracking import EXPERIMENT_NAME, TRACKING_URI, log_training_run
from backend.ml.train import derive_faixa, preprocess_features

MODELS_DIR = os.path.join(PROJECT_ROOT, "models")
DATA_PATH = os.path.join(PROJECT_ROOT, "data", "dataset_safefield.parquet")
DATA_DIR = os.path.join(PROJECT_ROOT, "data")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tracking_run_id():
    """Executa um run de tracking e retorna o run_id."""
    model = joblib.load(os.path.join(MODELS_DIR, "xgboost_model.joblib"))
    encoder = joblib.load(os.path.join(MODELS_DIR, "encoder.joblib"))
    with open(os.path.join(MODELS_DIR, "features.json")) as f:
        features = json.load(f)
    with open(os.path.join(MODELS_DIR, "metrics.json")) as f:
        metrics = json.load(f)

    df = pd.read_parquet(DATA_PATH)
    X = preprocess_features(df[features].copy(), encoder)
    y_pred = model.predict(X[:200])
    y_test_faixa = [derive_faixa(float(s)) for s in df["risco_score"][:200]]
    y_pred_faixa = [derive_faixa(float(s)) for s in y_pred]

    return log_training_run(
        model=model,
        metrics=metrics,
        feature_cols=features,
        y_test_faixa=y_test_faixa,
        y_pred_faixa=y_pred_faixa,
        models_dir=MODELS_DIR,
        data_dir=DATA_DIR,
    )


@pytest.fixture(scope="module")
def mlflow_client(tracking_run_id):
    """Retorna MlflowClient apontando para o tracking URI local."""
    import mlflow
    mlflow.set_tracking_uri(TRACKING_URI)
    return mlflow.tracking.MlflowClient(tracking_uri=TRACKING_URI)


@pytest.fixture(scope="module")
def experiment(mlflow_client):
    return mlflow_client.get_experiment_by_name(EXPERIMENT_NAME)


@pytest.fixture(scope="module")
def finished_run(mlflow_client, experiment):
    runs = mlflow_client.search_runs(experiment_ids=[experiment.experiment_id])
    finished = [r for r in runs if r.info.status == "FINISHED"]
    assert len(finished) > 0, "Nenhuma run com status FINISHED encontrada"
    return finished[0]


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------

class TestRegistro:
    def test_mlruns_dir_criado(self):
        assert os.path.isdir(os.path.join(PROJECT_ROOT, "mlruns"))

    def test_run_id_retornado(self, tracking_run_id):
        assert tracking_run_id is not None
        assert isinstance(tracking_run_id, str)
        assert len(tracking_run_id) > 0


# ---------------------------------------------------------------------------
# Experimento
# ---------------------------------------------------------------------------

class TestExperimento:
    def test_experimento_existe(self, experiment):
        assert experiment is not None

    def test_experimento_nome_correto(self, experiment):
        assert experiment.name == EXPERIMENT_NAME


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

class TestRun:
    def test_run_com_status_finished(self, finished_run):
        assert finished_run.info.status == "FINISHED"

    def test_run_metricas_nao_vazias(self, finished_run):
        assert len(finished_run.data.metrics) > 0


# ---------------------------------------------------------------------------
# Parametros
# ---------------------------------------------------------------------------

class TestParametros:
    def test_param_n_estimators(self, finished_run):
        assert "n_estimators" in finished_run.data.params

    def test_param_max_depth(self, finished_run):
        assert "max_depth" in finished_run.data.params

    def test_param_learning_rate(self, finished_run):
        assert "learning_rate" in finished_run.data.params

    def test_param_subsample(self, finished_run):
        assert "subsample" in finished_run.data.params

    def test_param_colsample_bytree(self, finished_run):
        assert "colsample_bytree" in finished_run.data.params

    def test_param_n_features(self, finished_run):
        assert "n_features" in finished_run.data.params

    def test_param_dataset_version(self, finished_run):
        assert "dataset_version" in finished_run.data.params


# ---------------------------------------------------------------------------
# Metricas
# ---------------------------------------------------------------------------

class TestMetricas:
    def test_metrica_mae(self, finished_run):
        assert "mae" in finished_run.data.metrics
        assert isinstance(finished_run.data.metrics["mae"], float)
        assert finished_run.data.metrics["mae"] > 0

    def test_metrica_rmse(self, finished_run):
        assert "rmse" in finished_run.data.metrics
        assert finished_run.data.metrics["rmse"] > 0

    def test_metrica_r2(self, finished_run):
        assert "r2" in finished_run.data.metrics
        assert finished_run.data.metrics["r2"] > 0

    def test_metrica_accuracy_faixas(self, finished_run):
        assert "accuracy_faixas" in finished_run.data.metrics

    def test_metrica_f1_baixo(self, finished_run):
        assert "f1_baixo" in finished_run.data.metrics

    def test_metrica_f1_medio(self, finished_run):
        assert "f1_medio" in finished_run.data.metrics

    def test_metrica_f1_alto(self, finished_run):
        assert "f1_alto" in finished_run.data.metrics


# ---------------------------------------------------------------------------
# Artefatos
# ---------------------------------------------------------------------------

class TestArtefatos:
    def test_run_tem_artefatos(self, mlflow_client, finished_run):
        artifacts = mlflow_client.list_artifacts(finished_run.info.run_id)
        assert len(artifacts) > 0

    def test_pasta_model_existe(self, mlflow_client, finished_run):
        artifacts = mlflow_client.list_artifacts(finished_run.info.run_id, "model")
        assert len(artifacts) > 0

    def test_pasta_shap_plots_existe(self, mlflow_client, finished_run):
        artifacts = mlflow_client.list_artifacts(finished_run.info.run_id, "shap_plots")
        assert len(artifacts) > 0


# ---------------------------------------------------------------------------
# Graceful Fallback
# ---------------------------------------------------------------------------

class TestGracefulFallback:
    def test_fallback_retorna_none_quando_erro(self):
        result = log_training_run(
            model=None,
            metrics={"mae": 1.0, "rmse": 1.5, "r2": 0.9, "accuracy_faixas": 0.9},
            feature_cols=["f1"],
            y_test_faixa=["baixo"],
            y_pred_faixa=["baixo"],
        )
        assert result is None

    def test_nao_propaga_excecao(self):
        raised = False
        try:
            log_training_run(
                model=None,
                metrics={"mae": 1.0, "rmse": 1.5, "r2": 0.9, "accuracy_faixas": 0.9},
                feature_cols=["f1"],
                y_test_faixa=["baixo"],
                y_pred_faixa=["baixo"],
            )
        except Exception:
            raised = True
        assert not raised, "log_training_run propagou excecao inesperada"