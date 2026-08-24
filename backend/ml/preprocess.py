"""
Pre-processamento compartilhado entre treino e inferencia.

Extraido de train.py para que a API possa preparar features sem importar o
script de treinamento. train.py reexporta estes nomes para nao quebrar os
imports existentes em tests/ e scripts/.
"""

import pandas as pd
from sklearn.preprocessing import OrdinalEncoder

# Colunas que nunca entram como feature: identificadores, timestamp,
# metadados de RAG e os proprios targets.
EXCLUDE_COLS = {
    "equipamento_id",
    "timestamp",
    "operador_id",
    "modelo_equipamento",
    "categoria_manual",
    "risco_score",
    "faixa_risco",
}
TARGET = "risco_score"
CAT_COLS = ["tipo_equipamento", "tipo_operacao", "tipo_solo", "condicao_clima"]
BOOL_COLS = ["tem_iot", "manutencao_atrasada"]


def derive_faixa(score: float) -> str:
    """Deriva a faixa de risco a partir do score. Nunca gerar independentemente."""
    if score <= 33:
        return "baixo"
    elif score <= 66:
        return "medio"
    return "alto"


def preprocess_features(df: pd.DataFrame, encoder: OrdinalEncoder) -> pd.DataFrame:
    """
    Aplica o mesmo pre-processamento do treino: booleanos para int, categoricas
    pelo encoder ajustado no treino, e object -> numerico (None vira NaN, que o
    XGBoost trata nativamente).
    """
    X = df.copy()
    for col in BOOL_COLS:
        X[col] = X[col].astype(int)
    X[CAT_COLS] = encoder.transform(X[CAT_COLS])
    for col in X.select_dtypes(include="object").columns:
        X[col] = pd.to_numeric(X[col], errors="coerce")
    return X


# Agrupamento das 30 features para decomposicao SHAP por grupo. Vive aqui, e nao
# em shap_explainer, porque a API precisa dele sem carregar matplotlib.
FEATURE_GROUPS: dict[str, list[str]] = {
    "ambiental":   ["temperatura_ar", "precipitacao_mm", "umidade_solo", "velocidade_vento", "condicao_clima"],
    "geografico":  ["latitude", "longitude", "tipo_solo", "distancia_agua_m", "declividade"],
    "operacional": ["tipo_operacao", "velocidade_kmh", "vibracao_g", "temperatura_motor", "horas_operacao", "horario_operacao"],
    "equipamento": ["tipo_equipamento", "idade_equipamento", "historico_sinistros", "tem_iot"],
    "operador":    ["pct_velocidade_acima_recomendada", "freq_eventos_bruscos", "pct_operacoes_noturnas", "score_operador_historico"],
    "manutencao":  ["ultima_manutencao_dias", "ultima_manutencao_horas_op", "intervalo_manut_recomendado_dias", "intervalo_manut_recomendado_horas", "manutencao_atrasada", "atraso_manutencao_pct"],
}

FEATURE_TO_GROUP: dict[str, str] = {
    feat: grp for grp, feats in FEATURE_GROUPS.items() for feat in feats
}
