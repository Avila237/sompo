import json
import os
import sys

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OrdinalEncoder

DATA_PATH = "data/dataset_safefield.parquet"
MODELS_DIR = "models"

# Este modulo tambem roda como script (python backend/ml/train.py), caso em que a
# raiz do projeto nao esta no sys.path e o import absoluto abaixo falharia.
_PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJ_ROOT not in sys.path:
    sys.path.insert(0, _PROJ_ROOT)

# Constantes e pre-processamento vivem em preprocess.py, compartilhados com a API.
# Reexportados aqui porque tests/ e scripts/ importam de backend.ml.train.
from backend.ml.preprocess import (  # noqa: E402,F401
    BOOL_COLS,
    CAT_COLS,
    EXCLUDE_COLS,
    TARGET,
    derive_faixa,
    preprocess_features,
)


def main():
    os.makedirs(MODELS_DIR, exist_ok=True)

    df = pd.read_parquet(DATA_PATH)

    feature_cols = [c for c in df.columns if c not in EXCLUDE_COLS]
    assert len(feature_cols) == 30, f"Expected 30 features, got {len(feature_cols)}"

    X = df[feature_cols].copy()
    y = df[TARGET].copy()

    for col in BOOL_COLS:
        X[col] = X[col].astype(int)

    encoder = OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1)
    X[CAT_COLS] = encoder.fit_transform(X[CAT_COLS])

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42
    )

    model = xgb.XGBRegressor(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
        tree_method="hist",
    )
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

    y_pred = model.predict(X_test)
    mae = float(mean_absolute_error(y_test, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    r2 = float(r2_score(y_test, y_pred))

    SEP = "=" * 50
    print()
    print(SEP)
    print("METRICAS DE REGRESSAO")
    print(SEP)
    print(f"MAE:  {mae:.4f}")
    print(f"RMSE: {rmse:.4f}")
    print(f"R2:   {r2:.4f}")

    y_test_faixa = [derive_faixa(s) for s in y_test]
    y_pred_faixa = [derive_faixa(s) for s in y_pred]
    acc = float(accuracy_score(y_test_faixa, y_pred_faixa))
    labels = ["baixo", "medio", "alto"]

    print()
    print(SEP)
    print("METRICAS DE CLASSIFICACAO (faixas derivadas)")
    print(SEP)
    print(f"Acuracia das faixas: {acc:.4f} ({acc * 100:.1f}%)")
    print()
    print("Matriz de Confusao:")
    cm = confusion_matrix(y_test_faixa, y_pred_faixa, labels=labels)
    print(pd.DataFrame(cm, index=labels, columns=labels).to_string())
    print()
    print("Classification Report:")
    print(classification_report(y_test_faixa, y_pred_faixa, labels=labels))

    print()
    print(SEP)
    print("CRITERIOS DE ACEITACAO")
    print(SEP)
    ok_r2 = r2 > 0.80
    ok_mae = mae < 10
    ok_acc = acc > 0.85
    print(f"R2 > 0.80:       {'OK' if ok_r2 else 'FALHOU'} ({r2:.4f})")
    print(f"MAE < 10:        {'OK' if ok_mae else 'FALHOU'} ({mae:.4f})")
    print(f"Acuracia > 85%:  {'OK' if ok_acc else 'FALHOU'} ({acc * 100:.1f}%)")

    if not (ok_r2 and ok_mae and ok_acc):
        print()
        print("[ATENCAO] Modelo nao atingiu todos os criterios. Investigar antes de prosseguir.")
        sys.exit(1)

    print()
    print("[OK] Todos os criterios de aceitacao atingidos.")

    metrics = {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "r2": round(r2, 4),
        "accuracy_faixas": round(acc, 4),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "n_features": int(len(feature_cols)),
    }

    joblib.dump(model, os.path.join(MODELS_DIR, "xgboost_model.joblib"))
    joblib.dump(encoder, os.path.join(MODELS_DIR, "encoder.joblib"))

    with open(os.path.join(MODELS_DIR, "features.json"), "w") as f:
        json.dump(feature_cols, f, indent=2)

    with open(os.path.join(MODELS_DIR, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    print()
    print(f"Artefatos salvos em '{MODELS_DIR}/':")
    for fname in ["xgboost_model.joblib", "encoder.joblib", "features.json", "metrics.json"]:
        fpath = os.path.join(MODELS_DIR, fname)
        size_kb = os.path.getsize(fpath) / 1024
        print(f"  - {fname} ({size_kb:.1f} KB)")

    try:
        from backend.ml.mlflow_tracking import log_training_run
        log_training_run(
            model=model,
            metrics=metrics,
            feature_cols=feature_cols,
            y_test_faixa=y_test_faixa,
            y_pred_faixa=y_pred_faixa,
        )
    except Exception as e:
        print(f"\n[MLflow] Tracking indisponivel: {e}")


if __name__ == "__main__":
    main()