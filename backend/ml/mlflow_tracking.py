"""
Rastreabilidade de experimentos com MLflow para o modelo SafeField.

Uso:
    from backend.ml.mlflow_tracking import log_training_run
    run_id = log_training_run(model, metrics, feature_cols, ...)

Visualizar experimentos:
    mlflow ui --backend-store-uri file:./mlruns
"""

import os
from typing import Optional

# O MLflow 3.x recusa o backend de arquivos (file:./mlruns) por padrao — ele entrou
# em modo de manutencao e exige opt-in explicito. Sem isto, log_training_run() cai no
# fallback e o treino roda sem rastreabilidade. Definido antes de qualquer import de
# mlflow (que acontece dentro da funcao, mais abaixo).
os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")

EXPERIMENT_NAME = "safefield-xgboost"
TRACKING_URI = "file:./mlruns"
DATASET_VERSION = "v2"

SHAP_PLOTS = [
    "shap_summary_beeswarm.png",
    "shap_summary_bar.png",
    "shap_group_contributions.png",
    "shap_waterfall_baixo.png",
    "shap_waterfall_medio.png",
    "shap_waterfall_alto.png",
]

MODEL_ARTIFACTS = [
    "xgboost_model.joblib",
    "encoder.joblib",
    "features.json",
    "metrics.json",
]


def log_training_run(
    model,
    metrics: dict,
    feature_cols: list,
    y_test_faixa: list,
    y_pred_faixa: list,
    models_dir: str = "models",
    data_dir: str = "data",
    dataset_version: str = DATASET_VERSION,
) -> Optional[str]:
    """
    Registra um run de treinamento no MLflow.
    Retorna o run_id ou None se o MLflow nao estiver disponivel ou ocorrer erro.
    """
    try:
        import mlflow
        from sklearn.metrics import f1_score
    except ImportError:
        print("[MLflow] mlflow nao instalado — tracking pulado.")
        return None

    try:
        mlflow.set_tracking_uri(TRACKING_URI)
        mlflow.set_experiment(EXPERIMENT_NAME)

        with mlflow.start_run() as run:
            # Hiperparametros do XGBoost
            params = model.get_params()
            mlflow.log_param("n_estimators", params.get("n_estimators"))
            mlflow.log_param("max_depth", params.get("max_depth"))
            mlflow.log_param("learning_rate", params.get("learning_rate"))
            mlflow.log_param("subsample", params.get("subsample"))
            mlflow.log_param("colsample_bytree", params.get("colsample_bytree"))

            # Parametros do experimento
            mlflow.log_param("n_features", metrics.get("n_features", len(feature_cols)))
            mlflow.log_param("n_train", metrics.get("n_train"))
            mlflow.log_param("n_test", metrics.get("n_test"))
            mlflow.log_param("dataset_version", dataset_version)

            # Metricas de regressao
            mlflow.log_metric("mae", metrics["mae"])
            mlflow.log_metric("rmse", metrics["rmse"])
            mlflow.log_metric("r2", metrics["r2"])
            mlflow.log_metric("accuracy_faixas", metrics["accuracy_faixas"])

            # F1 por faixa de risco
            labels = ["baixo", "medio", "alto"]
            f1_scores = f1_score(
                y_test_faixa, y_pred_faixa,
                labels=labels, average=None, zero_division=0,
            )
            for label, f1 in zip(labels, f1_scores):
                mlflow.log_metric(f"f1_{label}", round(float(f1), 4))

            # Artefatos do modelo
            for fname in MODEL_ARTIFACTS:
                fpath = os.path.join(models_dir, fname)
                if os.path.isfile(fpath):
                    mlflow.log_artifact(fpath, artifact_path="model")

            # Graficos SHAP
            for fname in SHAP_PLOTS:
                fpath = os.path.join(data_dir, fname)
                if os.path.isfile(fpath):
                    mlflow.log_artifact(fpath, artifact_path="shap_plots")

            run_id = run.info.run_id

        print(f"\n[MLflow] Run registrada: {run_id}")
        print(f"[MLflow] Experimento: {EXPERIMENT_NAME}")
        print(f"[MLflow] Tracking URI: {TRACKING_URI}")
        print("[MLflow] Para visualizar: mlflow ui --backend-store-uri file:./mlruns")
        return run_id

    except Exception as e:
        print(f"\n[MLflow] Erro no tracking (graceful fallback): {e}")
        return None