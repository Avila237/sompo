"""
Seed do Supabase — popula equipamentos, operadores e avaliacoes.

PREREQUISITO: rode backend/db/schema.sql no SQL Editor do Supabase ANTES deste script.

Uso:
    python scripts/seed_supabase.py          # com confirmacao
    python scripts/seed_supabase.py --force   # sem confirmacao
"""
import argparse
import math
import os
import sys

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.db.supabase_client import get_supabase_client

BATCH_SIZE = 500
DATA_PATH = os.path.join(PROJECT_ROOT, "data", "dataset_safefield.parquet")

EQUIP_STATIC_COLS = [
    "equipamento_id", "tipo_equipamento", "modelo_equipamento",
    "categoria_manual", "idade_equipamento", "historico_sinistros",
    "tem_iot", "intervalo_manut_recomendado_dias",
    "intervalo_manut_recomendado_horas",
]

AVAL_EXCLUDE = set(EQUIP_STATIC_COLS) - {"equipamento_id"}


def sanitize_record(record: dict) -> dict:
    clean = {}
    for key, val in record.items():
        if val is None:
            clean[key] = None
        elif isinstance(val, float) and math.isnan(val):
            clean[key] = None
        elif hasattr(val, "item"):
            clean[key] = val.item()
        elif isinstance(val, pd.Timestamp):
            clean[key] = val.isoformat()
        else:
            clean[key] = val
    return clean


def load_dataset() -> pd.DataFrame:
    return pd.read_parquet(DATA_PATH)


def derive_equipamentos(df: pd.DataFrame) -> list[dict]:
    equip = df.drop_duplicates(subset="equipamento_id")[EQUIP_STATIC_COLS].copy()
    records = equip.to_dict(orient="records")
    return [sanitize_record(r) for r in records]


def derive_operadores(df: pd.DataFrame) -> list[dict]:
    ops = sorted(df["operador_id"].unique())
    return [{"operador_id": str(op)} for op in ops]


def derive_avaliacoes(df: pd.DataFrame) -> list[dict]:
    cols = [c for c in df.columns if c not in AVAL_EXCLUDE]
    aval = df[cols].copy()
    aval["timestamp"] = aval["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    aval["faixa_risco"] = aval["faixa_risco"].astype(str)
    aval["risco_score"] = aval["risco_score"].round(2)
    records = aval.to_dict(orient="records")
    return [sanitize_record(r) for r in records]


def insert_batch(client, table: str, records: list[dict]):
    total = len(records)
    for i in range(0, total, BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        client.table(table).insert(batch).execute()
        inserted = min(i + BATCH_SIZE, total)
        print(f"  {table}: {inserted}/{total}")


def clear_tables(client):
    print("Limpando tabelas existentes...")
    client.table("predicoes").delete().gte("predicao_id", 0).execute()
    client.table("avaliacoes").delete().gte("avaliacao_id", 0).execute()
    client.table("operadores").delete().neq("operador_id", "").execute()
    client.table("equipamentos").delete().neq("equipamento_id", "").execute()


def get_counts(client) -> dict:
    counts = {}
    for table in ["equipamentos", "operadores", "avaliacoes", "predicoes"]:
        result = client.table(table).select("*", count="exact").limit(0).execute()
        counts[table] = result.count
    return counts


def main():
    parser = argparse.ArgumentParser(description="Seed Supabase com dados do SafeField")
    parser.add_argument("--force", action="store_true", help="Pular confirmacao")
    args = parser.parse_args()

    print("=" * 60)
    print("SafeField -- Seed do Supabase")
    print("=" * 60)
    print()
    print("PREREQUISITO: Rode o SQL de backend/db/schema.sql no")
    print("SQL Editor do Supabase ANTES de executar este script.")
    print()

    if not args.force:
        resp = input("Isto vai LIMPAR as tabelas e repopular. Continuar? [s/N] ")
        if resp.lower() not in ("s", "sim", "y", "yes"):
            print("Abortado.")
            sys.exit(0)

    print("Carregando dataset...")
    df = load_dataset()
    print(f"  {len(df)} registros carregados")

    print("\nDerivando tabelas...")
    equipamentos = derive_equipamentos(df)
    operadores = derive_operadores(df)
    avaliacoes = derive_avaliacoes(df)
    print(f"  equipamentos: {len(equipamentos)}")
    print(f"  operadores:   {len(operadores)}")
    print(f"  avaliacoes:   {len(avaliacoes)}")

    client = get_supabase_client()

    clear_tables(client)

    print("\nInserindo equipamentos...")
    insert_batch(client, "equipamentos", equipamentos)

    print("\nInserindo operadores...")
    insert_batch(client, "operadores", operadores)

    print("\nInserindo avaliacoes...")
    insert_batch(client, "avaliacoes", avaliacoes)

    print("\n" + "=" * 60)
    print("Contagens finais:")
    counts = get_counts(client)
    for table, count in counts.items():
        print(f"  {table}: {count}")
    print("=" * 60)
    print("Seed concluido com sucesso!")


if __name__ == "__main__":
    main()