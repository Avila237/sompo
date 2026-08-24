"""
Explicabilidade SHAP para o modelo de risco SafeField.

Uso principal:
    from backend.ml.shap_explainer import run_full_analysis
    results = run_full_analysis()
"""

import json
import os

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

MODELS_DIR = "models"
DATA_DIR = "data"
DATA_PATH = "data/dataset_safefield.parquet"

# Definidos em preprocess.py para que a API os use sem carregar matplotlib.
# Reexportados aqui porque tests/ e o restante do modulo importam daqui.
from backend.ml.preprocess import FEATURE_GROUPS, FEATURE_TO_GROUP  # noqa: E402

_FEATURE_TO_GROUP = FEATURE_TO_GROUP


def load_artifacts(models_dir: str = MODELS_DIR):
    """Carrega modelo, encoder e lista de features do disco."""
    model = joblib.load(os.path.join(models_dir, "xgboost_model.joblib"))
    encoder = joblib.load(os.path.join(models_dir, "encoder.joblib"))
    with open(os.path.join(models_dir, "features.json")) as f:
        features = json.load(f)
    return model, encoder, features


def compute_shap_values(model, X: pd.DataFrame) -> np.ndarray:
    """Calcula SHAP values via TreeExplainer. Retorna array (n_amostras, n_features)."""
    explainer = shap.TreeExplainer(model)
    return explainer.shap_values(X)


def top_features_global(shap_values: np.ndarray, features: list, top_n: int = 10) -> list:
    """Retorna as top N features por importancia media absoluta de SHAP."""
    mean_abs = np.abs(shap_values).mean(axis=0)
    indices = np.argsort(mean_abs)[::-1][:top_n]
    return [(features[i], float(mean_abs[i])) for i in indices]


def group_contributions(shap_values: np.ndarray, features: list) -> pd.DataFrame:
    """
    Para cada registro, soma os |SHAP values| de cada grupo de features.
    Retorna DataFrame com colunas: ambiental, geografico, operacional, equipamento, operador, manutencao.
    """
    shap_df = pd.DataFrame(shap_values, columns=features)
    result = {}
    for group, cols in FEATURE_GROUPS.items():
        present = [c for c in cols if c in shap_df.columns]
        result[group] = shap_df[present].abs().sum(axis=1).values
    return pd.DataFrame(result)


def explain_record(shap_values: np.ndarray, features: list, idx: int, top_n: int = 5) -> list:
    """
    Retorna os top N fatores para um registro especifico.
    Cada fator: {"feature": str, "shap_value": float, "group": str}
    """
    row = shap_values[idx]
    indices = np.argsort(np.abs(row))[::-1][:top_n]
    return [
        {
            "feature": features[i],
            "shap_value": float(row[i]),
            "group": _FEATURE_TO_GROUP.get(features[i], "unknown"),
        }
        for i in indices
    ]


def save_shap_values(shap_values: np.ndarray, models_dir: str = MODELS_DIR) -> str:
    """Salva os SHAP values em disco para reutilizacao."""
    path = os.path.join(models_dir, "shap_values.npy")
    np.save(path, shap_values)
    return path


def save_plots(
    model,
    shap_values: np.ndarray,
    X: pd.DataFrame,
    y_pred: np.ndarray,
    features: list,
    data_dir: str = DATA_DIR,
) -> list:
    """
    Gera e salva graficos SHAP como PNG.
    Retorna lista com caminhos dos arquivos salvos.
    """
    os.makedirs(data_dir, exist_ok=True)
    saved = []

    # 1. Summary beeswarm
    path = os.path.join(data_dir, "shap_summary_beeswarm.png")
    shap.summary_plot(shap_values, X, show=False)
    plt.savefig(path, dpi=120, bbox_inches="tight")
    plt.close("all")
    saved.append(path)

    # 2. Summary bar
    path = os.path.join(data_dir, "shap_summary_bar.png")
    shap.summary_plot(shap_values, X, plot_type="bar", show=False)
    plt.savefig(path, dpi=120, bbox_inches="tight")
    plt.close("all")
    saved.append(path)

    # 3. Contribuicao por grupo (barras)
    group_df = group_contributions(shap_values, features)
    group_means = group_df.mean().sort_values(ascending=False)
    path = os.path.join(data_dir, "shap_group_contributions.png")
    fig, ax = plt.subplots(figsize=(8, 5))
    group_means.plot(kind="bar", ax=ax)
    ax.set_title("Contribuicao Media por Grupo de Features (SHAP)")
    ax.set_ylabel("Soma media de |SHAP values|")
    ax.set_xlabel("Grupo")
    plt.tight_layout()
    plt.savefig(path, dpi=120, bbox_inches="tight")
    plt.close("all")
    saved.append(path)

    # 4-6. Waterfall plots (um por faixa de risco)
    explainer = shap.TreeExplainer(model)
    explanation = explainer(X)

    bands = []
    for p in y_pred:
        score = float(p)
        if score <= 33:
            bands.append("baixo")
        elif score <= 66:
            bands.append("medio")
        else:
            bands.append("alto")

    for faixa in ("baixo", "medio", "alto"):
        try:
            idx = bands.index(faixa)
        except ValueError:
            continue
        path = os.path.join(data_dir, f"shap_waterfall_{faixa}.png")
        shap.plots.waterfall(explanation[idx], show=False)
        plt.savefig(path, dpi=120, bbox_inches="tight")
        plt.close("all")
        saved.append(path)

    return saved


def run_full_analysis(
    models_dir: str = MODELS_DIR,
    data_path: str = DATA_PATH,
    data_dir: str = DATA_DIR,
    sample_size: int = 500,
) -> dict:
    """
    Executa analise SHAP completa:
    carrega artefatos, pre-processa amostra, calcula SHAP values,
    salva artefatos e graficos, retorna dict com metricas e exemplos.
    """
    from backend.ml.train import derive_faixa, preprocess_features

    model, encoder, features = load_artifacts(models_dir)
    df = pd.read_parquet(data_path)

    sample = df.sample(min(sample_size, len(df)), random_state=42).reset_index(drop=True)
    X = preprocess_features(sample[features].copy(), encoder)
    y_pred = model.predict(X)

    shap_values = compute_shap_values(model, X)
    save_shap_values(shap_values, models_dir)
    saved_plots = save_plots(model, shap_values, X, y_pred, features, data_dir)

    top_feats = top_features_global(shap_values, features, top_n=10)

    group_df = group_contributions(shap_values, features)
    examples = {}
    for faixa in ("baixo", "medio", "alto"):
        mask = [derive_faixa(float(p)) == faixa for p in y_pred]
        if any(mask):
            idx = next(i for i, m in enumerate(mask) if m)
            score = float(y_pred[idx])
            contrib = group_df.iloc[idx].to_dict()
            top_factors = explain_record(shap_values, features, idx, top_n=5)
            examples[faixa] = {
                "score": round(score, 2),
                "group_contributions": {k: round(v, 3) for k, v in contrib.items()},
                "top_factors": top_factors,
            }

    return {
        "shap_values_shape": shap_values.shape,
        "top_features": top_feats,
        "examples_by_faixa": examples,
        "saved_plots": saved_plots,
    }


if __name__ == "__main__":
    results = run_full_analysis()
    SEP = "=" * 50
    print()
    print(SEP)
    print("SHAP ANALYSIS - SAFEFIELD")
    print(SEP)
    print(f"\nSHAP values shape: {results['shap_values_shape']}")
    print("\nTop 10 features (global):")
    for feat, imp in results["top_features"]:
        print(f"  {feat:<45} {imp:.4f}")
    print("\nDecomposicao por grupo (por faixa de risco):")
    for faixa, ex in results["examples_by_faixa"].items():
        print(f"\n  [{faixa.upper()}] score={ex['score']:.1f}")
        for grp, val in sorted(ex["group_contributions"].items(), key=lambda x: -x[1]):
            print(f"    {grp:<15} {val:.3f}")
    print("\nGraficos salvos:")
    for p in results["saved_plots"]:
        print(f"  {p}")