"""
Popular tabela predicoes no Supabase.

Roda o modelo XGBoost sobre as 5000 avaliacoes, calcula SHAP values,
e insere as predicoes com os top 5 fatores explicativos.

Uso:
    python scripts/populate_predictions.py
"""
import os
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.db.supabase_client import get_supabase_client
from backend.ml.shap_explainer import (
    compute_shap_values,
    explain_record,
    load_artifacts,
)
from backend.ml.train import derive_faixa, preprocess_features

BATCH_SIZE = 500
DATA_PATH = os.path.join(PROJECT_ROOT, "data", "dataset_safefield.parquet")
MODELO_VERSAO = "xgboost-v1-baseline"


def fetch_avaliacao_ids(client) -> list[int]:
    all_ids = []
    page_size = 1000
    offset = 0
    while True:
        result = (
            client.table("avaliacoes")
            .select("avaliacao_id")
            .order("avaliacao_id")
            .range(offset, offset + page_size - 1)
            .execute()
        )
        all_ids.extend(r["avaliacao_id"] for r in result.data)
        if len(result.data) < page_size:
            break
        offset += page_size
    return all_ids


def clear_predicoes(client):
    client.table("predicoes").delete().gte("predicao_id", 0).execute()


def insert_batch(client, records: list[dict]):
    total = len(records)
    for i in range(0, total, BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        client.table("predicoes").insert(batch).execute()
        inserted = min(i + BATCH_SIZE, total)
        print(f"  predicoes: {inserted}/{total}")


def main():
    print("=" * 60)
    print("SafeField -- Popular Tabela de Predicoes")
    print("=" * 60)

    print("\nCarregando dataset e artefatos do modelo...")
    df = pd.read_parquet(DATA_PATH)
    model, encoder, features = load_artifacts()
    print(f"  Dataset: {len(df)} registros")
    print(f"  Features: {len(features)}")

    print("\nRodando modelo...")
    X = preprocess_features(df[features].copy(), encoder)
    scores = model.predict(X)
    faixas = [derive_faixa(float(s)) for s in scores]
    print(f"  Predicoes geradas: {len(scores)}")

    print("\nCalculando SHAP values (pode demorar)...")
    shap_values = compute_shap_values(model, X)
    print(f"  SHAP shape: {shap_values.shape}")

    print("\nBuscando avaliacao_ids no Supabase...")
    client = get_supabase_client()
    avaliacao_ids = fetch_avaliacao_ids(client)
    assert len(avaliacao_ids) == len(df), (
        f"Mismatch: {len(avaliacao_ids)} avaliacoes no Supabase vs {len(df)} no dataset"
    )
    print(f"  {len(avaliacao_ids)} avaliacao_ids obtidos")

    print("\nMontando registros de predicoes...")
    records = []
    for i in range(len(df)):
        top_fatores = explain_record(shap_values, features, i, top_n=5)
        records.append({
            "avaliacao_id": avaliacao_ids[i],
            "risco_score_predito": round(float(scores[i]), 2),
            "faixa_predita": faixas[i],
            "top_fatores_shap": top_fatores,
            "modelo_versao": MODELO_VERSAO,
        })

    print("\nLimpando predicoes existentes...")
    clear_predicoes(client)

    print("\nInserindo predicoes...")
    insert_batch(client, records)

    count_result = client.table("predicoes").select("*", count="exact").limit(0).execute()
    total_inserted = count_result.count

    from collections import Counter
    dist = Counter(faixas)

    print("\n" + "=" * 60)
    print(f"Total inserido: {total_inserted}")
    print(f"\nDistribuicao das faixas preditas:")
    for f in ("baixo", "medio", "alto"):
        pct = dist[f] / len(faixas) * 100
        print(f"  {f}: {dist[f]} ({pct:.1f}%)")

    example = records[0]
    print(f"\nExemplo de registro (primeiro):")
    print(f"  avaliacao_id: {example['avaliacao_id']}")
    print(f"  risco_score_predito: {example['risco_score_predito']}")
    print(f"  faixa_predita: {example['faixa_predita']}")
    print(f"  modelo_versao: {example['modelo_versao']}")
    print(f"  top_fatores_shap:")
    for fator in example["top_fatores_shap"]:
        print(f"    {fator['feature']:<40} shap={fator['shap_value']:+.3f}  grupo={fator['group']}")
    print("=" * 60)
    print("Predicoes populadas com sucesso!")


if __name__ == "__main__":
    main()