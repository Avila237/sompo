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
