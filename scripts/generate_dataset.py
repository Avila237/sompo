"""
SafeField - Geracao do Dataset Simulado
Gera ~5.000 registros de avaliações de risco para equipamentos agricolas.

Spec: docs/data_schema.md
Execucao: python scripts/generate_dataset.py (a partir da raiz do projeto)

=== NOTA DE CALIBRACAO DOS PESOS ===
O script usa pesos recalibrados em relacao a spec original (secao 4.2 do data_schema.md)
para atingir a distribuicao alvo de ~40% baixo / ~35% medio / ~25% alto.

Ajustes realizados em relacao aos pesos originais:
  precipitacao_mm:    0.15 -> 0.10
  umidade_solo:       0.10 -> 0.08
  agua_score:         15   -> 12
  declividade:        0.20 -> 0.15
  velocidade_kmh:     0.15 -> 0.12
  horas_operacao:     0.80 -> 1.20  (aumentado: operacoes longas = mais fadiga/risco)
  noturno:            6    -> 5
  historico_sinistros:2.0  -> 6.0   (aumentado: historico e o preditor mais forte)

Adicionado: risco_acumulado = max(0, sinistros-3) * horas * 0.60
  Captura o risco composto: equipamentos acidentados + operacao prolongada.
  Ex: sinistros=8, horas=12 -> bônus de +30 pontos.

Adicionado: horas_operacao correlacionada com tipo_operacao:
  colheita/transporte: gamma(2,5) e gamma(1.5,6) -> media ~10h e ~9h
  plantio: gamma(1.5,3) -> media ~4.5h
  pulverizacao: exponencial(3) -> media ~3h
  parado: exponencial(1.5) -> media ~1.5h

Adicionado: distribuicao estratificada de sinistros em generate_equipamentos:
  Para equipamentos velhos (>10 anos): 35% baixo risco (0-2), 30% medio (2-5), 35% alto (5-10)
  Para equipamentos medios (3-10 anos): 50% baixo (0-1), 30% medio (1-3), 20% alto (3-6)

Distribuicao alvo atingida (seed=42): ~40% baixo / ~36% medio / ~24% alto
"""

import os
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

N_EQUIPAMENTOS = 200
N_REGISTROS = 5000

TIPOS_EQUIPAMENTO = ["trator", "colheitadeira", "implemento"]
TIPOS_OPERACAO = ["colheita", "transporte", "plantio", "pulverizacao", "parado"]
TIPOS_SOLO = ["argiloso", "misto", "arenoso"]
PESO_OPERACAO = [0.30, 0.25, 0.20, 0.15, 0.10]
PESO_EQUIPAMENTO = [0.45, 0.35, 0.20]
PESO_SOLO = [0.40, 0.35, 0.25]


# ---------------------------------------------------------------------------
# 1. Equipamentos
# ---------------------------------------------------------------------------

def generate_equipamentos(n=N_EQUIPAMENTOS):
    """
    Gera a tabela base de equipamentos com distribuicao estratificada de sinistros.
    Regra 1: ~30% com IoT, ~70% sem.
    Regra 8 (estendida): sinistros correlacionados com idade, em 3 tiers de risco.
    Regra 10: distribuicao de tipos.
    """
    ids = [f"EQ-{i:04d}" for i in range(1, n + 1)]
    tipos = np.random.choice(TIPOS_EQUIPAMENTO, size=n, p=PESO_EQUIPAMENTO)
    idades = np.random.randint(0, 26, size=n)

    sinistros = np.zeros(n, dtype=int)
    for i, idade in enumerate(idades):
        tier = np.random.random()
        if idade < 3:
            # Jovem: quase sem sinistros
            sinistros[i] = 2 if np.random.random() < 0.10 else np.random.randint(0, 2)
        elif idade <= 10:
            # Medio: 3 tiers - 50% baixo, 30% medio, 20% alto
            if tier < 0.50:
                sinistros[i] = np.random.randint(0, 2)
            elif tier < 0.80:
                sinistros[i] = np.random.randint(1, 4)
            else:
                sinistros[i] = np.random.randint(3, 7)
        else:
            # Velho: 3 tiers - 35% baixo, 30% medio, 35% alto
            if tier < 0.35:
                sinistros[i] = np.random.randint(0, 3)
            elif tier < 0.65:
                sinistros[i] = np.random.randint(2, 6)
            else:
                sinistros[i] = np.random.randint(5, 11)
    sinistros = np.clip(sinistros, 0, 10)

    # Regra 1: ~30% com IoT
    tem_iot = np.random.random(n) < 0.30

    return pd.DataFrame({
        "equipamento_id": ids,
        "tipo_equipamento": tipos,
        "idade_equipamento": idades,
        "historico_sinistros": sinistros,
        "tem_iot": tem_iot,
    })


# ---------------------------------------------------------------------------
# 2. Dados ambientais
# ---------------------------------------------------------------------------

def generate_ambientais(n=N_REGISTROS):
    """
    Gera temperatura_ar, precipitacao_mm, velocidade_vento, condicao_clima.
    Regra 5: condicao_clima correlacionada com precipitacao_mm.
    umidade_solo nao e gerada aqui - depende de tipo_solo (Regra 3).
    """
    temperatura_ar = np.round(np.random.uniform(-5.0, 45.0, n), 1)
    precipitacao_mm = np.round(np.random.exponential(12, n).clip(0, 120), 1)
    velocidade_vento = np.round(np.random.uniform(0.0, 80.0, n), 1)

    # Regra 5: clima derivado da precipitacao
    condicao_clima = []
    for p in precipitacao_mm:
        if p <= 2:
            condicao_clima.append(np.random.choice(["ensolarado", "nublado"], p=[0.7, 0.3]))
        elif p <= 20:
            condicao_clima.append(np.random.choice(["nublado", "chuvoso"], p=[0.5, 0.5]))
        elif p <= 50:
            condicao_clima.append("chuvoso")
        else:
            condicao_clima.append(np.random.choice(["chuvoso", "tempestade"], p=[0.4, 0.6]))

    return pd.DataFrame({
        "temperatura_ar": temperatura_ar,
        "precipitacao_mm": precipitacao_mm,
        "velocidade_vento": velocidade_vento,
        "condicao_clima": condicao_clima,
    })


# ---------------------------------------------------------------------------
# 3. Dados geograficos
# ---------------------------------------------------------------------------

def generate_geograficos(n=N_REGISTROS):
    """
    Gera latitude, longitude, tipo_solo, distancia_agua_m, declividade.
    Distribuicao de tipo_solo: argiloso 40%, misto 35%, arenoso 25%.
    """
    latitude = np.round(np.random.uniform(-33.75, -2.50, n), 6)
    longitude = np.round(np.random.uniform(-73.99, -34.79, n), 6)
    tipo_solo = np.random.choice(TIPOS_SOLO, size=n, p=PESO_SOLO)
    distancia_agua_m = np.round(np.random.exponential(800, n).clip(10, 5000), 1)
    declividade = np.round(np.random.exponential(5, n).clip(0, 45), 1)

    return pd.DataFrame({
        "latitude": latitude,
        "longitude": longitude,
        "tipo_solo": tipo_solo,
        "distancia_agua_m": distancia_agua_m,
        "declividade": declividade,
    })


# ---------------------------------------------------------------------------
# 4. Dados operacionais
# ---------------------------------------------------------------------------

def _distribuicao_horario():
    """Pesos para cada hora do dia (0-23). Mais atividade entre 6h e 18h."""
    pesos = np.array([
        0.5, 0.3, 0.2, 0.2, 0.3, 0.5,
        1.5, 3.0, 4.0, 4.0, 4.0, 4.0,
        3.5, 4.0, 4.0, 4.0, 3.5, 3.0,
        2.0, 1.5, 1.0, 0.8, 0.7, 0.6,
    ], dtype=float)
    return list(pesos / pesos.sum())


def _gerar_timestamps(n, equip_idx, n_equip):
    """
    Gera timestamps em 2025 com sazonalidade.
    Meses de safra (mar-jun, set-nov) tem mais registros.
    """
    pesos_mes = np.array([
        1.0, 1.0, 2.5, 3.0, 3.0, 2.5,
        1.0, 1.0, 2.5, 3.0, 2.5, 1.5,
    ], dtype=float)
    meses = np.random.choice(range(1, 13), size=n, p=pesos_mes / pesos_mes.sum())
    timestamps = []
    for mes in meses:
        inicio_mes = pd.Timestamp(f"2025-{mes:02d}-01")
        if mes == 12:
            fim_mes = pd.Timestamp("2025-12-31 23:59:59")
        else:
            fim_mes = pd.Timestamp(f"2025-{mes+1:02d}-01") - pd.Timedelta(seconds=1)
        seg = int((fim_mes - inicio_mes).total_seconds())
        offset = np.random.randint(0, seg + 1)
        timestamps.append(inicio_mes + pd.Timedelta(seconds=int(offset)))
    return pd.Series(timestamps)


def generate_operacionais(n, equipamentos, equip_idx):
    """
    Gera tipo_operacao, velocidade_kmh, horas_operacao, horario_operacao, timestamp.
    Regra 4: velocidade correlacionada com tipo_operacao.
    Regra 9: distribuicao de operacoes.
    horas_operacao: correlacionada com tipo_operacao para maior realismo.
      colheita/transporte: operacoes longas (gamma(2,5) e gamma(1.5,6))
      plantio: moderada (gamma(1.5,3))
      pulverizacao/parado: curta (exponencial)
    """
    tipo_operacao = np.random.choice(TIPOS_OPERACAO, size=n, p=PESO_OPERACAO)

    # Regra 4: velocidade por operacao
    velocidade_kmh = np.zeros(n)
    for i, op in enumerate(tipo_operacao):
        if op == "parado":
            velocidade_kmh[i] = 0.0
        elif op in ("colheita", "plantio"):
            velocidade_kmh[i] = np.random.uniform(3.0, 8.0)
        elif op == "pulverizacao":
            velocidade_kmh[i] = np.random.uniform(8.0, 15.0)
        elif op == "transporte":
            velocidade_kmh[i] = np.random.uniform(15.0, 40.0)
    velocidade_kmh = np.round(velocidade_kmh, 1)

    # Horas correlacionadas com tipo de operacao
    horas_operacao = np.zeros(n)
    for i, op in enumerate(tipo_operacao):
        if op == "parado":
            horas_operacao[i] = np.random.exponential(1.5)
        elif op == "pulverizacao":
            horas_operacao[i] = np.random.exponential(3.0)
        elif op == "plantio":
            horas_operacao[i] = np.random.gamma(1.5, 3.0)
        elif op == "colheita":
            horas_operacao[i] = np.random.gamma(2.0, 5.0)
        elif op == "transporte":
            horas_operacao[i] = np.random.gamma(1.5, 6.0)
    horas_operacao = np.round(np.clip(horas_operacao, 0, 24), 1)

    horario_operacao = np.random.choice(range(24), size=n, p=_distribuicao_horario())
    timestamps = _gerar_timestamps(n, equip_idx, len(equipamentos))

    return pd.DataFrame({
        "timestamp": timestamps,
        "tipo_operacao": tipo_operacao,
        "velocidade_kmh": velocidade_kmh,
        "horas_operacao": horas_operacao,
        "horario_operacao": horario_operacao,
    })


# ---------------------------------------------------------------------------
# 5. Regras de consistencia
# ---------------------------------------------------------------------------

def apply_consistency_rules(df):
    """
    Aplica todas as regras que dependem de cruzamento entre colunas.
    """
    df = df.copy()

    # Regra 3: umidade_solo = f(precipitacao_mm, tipo_solo)
    fator_solo = df["tipo_solo"].map({"argiloso": 1.3, "misto": 1.0, "arenoso": 0.7})
    base_umidade = df["precipitacao_mm"] * 0.5 + np.random.uniform(5, 15, len(df))
    df["umidade_solo"] = np.clip(base_umidade * fator_solo, 5, 95).round(1)

    # Regra 6: vibracao_g correlacionada com tipo_operacao e velocidade
    vibracao = np.zeros(len(df))
    ranges_vib = {
        "parado":       (0.1, 0.3),
        "colheita":     (0.8, 2.5),
        "plantio":      (0.5, 1.5),
        "pulverizacao": (0.3, 1.0),
        "transporte":   (0.4, 2.0),
    }
    for op, (v_min, v_max) in ranges_vib.items():
        mask = df["tipo_operacao"] == op
        n_op = mask.sum()
        if n_op == 0:
            continue
        base = np.random.uniform(v_min, v_max, n_op)
        vel_norm = df.loc[mask, "velocidade_kmh"].values / 40.0
        ajuste = vel_norm * (v_max - v_min) * 0.2
        vibracao[mask] = np.clip(base + ajuste, 0.1, 4.0)

    # Regra 1: vibracao_g - sem IoT: 70% tem valor (range 0.1-2.0), 30% null
    vibracao_series = pd.Series(vibracao, index=df.index)
    mask_sem_iot = ~df["tem_iot"]
    indices_sem_iot = df.index[mask_sem_iot].to_numpy()
    null_mask = np.random.random(mask_sem_iot.sum()) < 0.30
    vibracao_series[mask_sem_iot] = vibracao_series[mask_sem_iot].clip(upper=2.0)
    vibracao_series[indices_sem_iot[null_mask]] = np.nan
    df["vibracao_g"] = vibracao_series.round(2)

    # Regra 7: temperatura_motor correlacionada com horas_operacao
    temp_motor = (
        60 + df["horas_operacao"] * 3
        + np.random.uniform(-5, 5, len(df))
    ).clip(50, 120)

    # Regra 1 + Regra 10: temperatura_motor null se sem IoT ou implemento
    temp_series = pd.Series(np.nan, index=df.index)
    mask_tem_motor = df["tem_iot"] & (df["tipo_equipamento"] != "implemento")
    temp_series[mask_tem_motor] = temp_motor[mask_tem_motor].round(1)
    df["temperatura_motor"] = temp_series

    return df


# ---------------------------------------------------------------------------
# 6. Calculo do score de risco
# ---------------------------------------------------------------------------

def calculate_risk_score(df):
    """
    Aplica a formula da secao 4 do data_schema.md com pesos recalibrados.
    Ver docstring do modulo para detalhes dos ajustes.
    """
    df = df.copy()

    noturno = ((df["horario_operacao"] >= 20) | (df["horario_operacao"] <= 5)).astype(int)
    vibracao_valor = df["vibracao_g"].fillna(0)

    # agua_score: transformacao nao-linear da distancia
    agua_score = np.maximum(0, (500 - df["distancia_agua_m"]) / 500)

    # score_base: contribuicoes individuais (pesos recalibrados)
    score_base = (
        df["precipitacao_mm"]       * 0.10
        + df["umidade_solo"]        * 0.08
        + df["velocidade_vento"]    * 0.05
        + agua_score                 * 12
        + df["declividade"]         * 0.15
        + df["velocidade_kmh"]      * 0.12
        + df["horas_operacao"]      * 1.20
        + noturno                    * 5
        + df["idade_equipamento"]   * 0.40
        + df["historico_sinistros"] * 6.00
    )

    # Bonus de interacoes (secao 4.3 - mantidos conforme spec)
    interacoes = pd.Series(0.0, index=df.index)

    # 1. Chuva forte + solo argiloso = terreno perigoso
    interacoes += ((df["precipitacao_mm"] > 30) & (df["tipo_solo"] == "argiloso")) * 12

    # 2. Velocidade alta + declividade = risco de tombamento
    interacoes += ((df["velocidade_kmh"] > 20) & (df["declividade"] > 15)) * 10

    # 3. Proximidade de agua + chuva = risco de alagamento
    interacoes += ((df["distancia_agua_m"] < 200) & (df["precipitacao_mm"] > 25)) * 15

    # 4. Operacao noturna + velocidade alta = visibilidade ruim
    interacoes += ((noturno == 1) & (df["velocidade_kmh"] > 15)) * 8

    # 5. Equipamento velho + vibracao alta = falha mecanica
    interacoes += ((df["idade_equipamento"] > 10) & (vibracao_valor > 2.0)) * 10

    # 6. Transporte rapido em terreno inclinado = cenario grave
    interacoes += (
        (df["tipo_operacao"] == "transporte")
        & (df["velocidade_kmh"] > 25)
        & (df["declividade"] > 10)
    ) * 12

    # 7. Muitas horas + noturno = fadiga extrema
    interacoes += ((df["horas_operacao"] > 8) & (noturno == 1)) * 10

    # Risco acumulado: equipamentos com muitos sinistros sao mais perigosos em operacoes longas
    # Captura o efeito composto: historico ruim + operacao prolongada = risco exponencialmente maior
    risco_acumulado = (
        np.maximum(0, df["historico_sinistros"] - 3)
        * df["horas_operacao"]
        * 0.60
    )

    # Score final com ruido gaussiano
    ruido = np.random.normal(0, 5, len(df))
    score_raw = score_base + interacoes + risco_acumulado + ruido
    df["risco_score"] = np.clip(score_raw, 0, 100).round(1)

    # Faixa derivada (Regra 2)
    df["faixa_risco"] = pd.cut(
        df["risco_score"],
        bins=[-0.1, 33.0, 66.0, 100.0],
        labels=["baixo", "medio", "alto"],
    )

    return df


# ---------------------------------------------------------------------------
# 7. Validacoes
# ---------------------------------------------------------------------------

def validate_dataset(df):
    """Imprime todas as validacoes da secao 5.4 do data_schema.md."""
    print("\n=== Validacoes ===\n")

    # 1. Shape
    print(f"Shape: {df.shape}")

    # 2. Distribuicao de faixa_risco
    print("\nDistribuicao faixa_risco:")
    for faixa in ["baixo", "medio", "alto"]:
        count = (df["faixa_risco"] == faixa).sum()
        pct = count / len(df) * 100
        print(f"  {faixa}: {count} ({pct:.1f}%)")

    # 3. Nulls
    print("\nNulls:")
    for col in ["vibracao_g", "temperatura_motor"]:
        n_null = df[col].isna().sum()
        pct = n_null / len(df) * 100
        print(f"  {col}: {n_null} ({pct:.1f}%)")

    # 4. Ranges numericos
    print("\nRanges numericos:")
    cols_num = [
        "temperatura_ar", "precipitacao_mm", "umidade_solo", "velocidade_vento",
        "distancia_agua_m", "declividade", "velocidade_kmh", "vibracao_g",
        "temperatura_motor", "horas_operacao", "horario_operacao",
        "idade_equipamento", "historico_sinistros", "risco_score",
    ]
    for col in cols_num:
        d = df[col].dropna()
        print(f"  {col:<22}: {d.min():.1f} a {d.max():.1f}")

    # 5. Consistencia: tem_iot=False com temperatura_motor preenchido
    v1 = ((~df["tem_iot"]) & df["temperatura_motor"].notna()).sum()
    v2 = ((df["tipo_operacao"] == "parado") & (df["velocidade_kmh"] > 0)).sum()
    v3 = ((df["tipo_equipamento"] == "implemento") & df["temperatura_motor"].notna()).sum()
    print("\nConsistencia:")
    print(f"  [{'OK' if v1 == 0 else 'FALHA'}] tem_iot=false com temperatura_motor preenchido: {v1}")
    print(f"  [{'OK' if v2 == 0 else 'FALHA'}] parado com velocidade > 0: {v2}")
    print(f"  [{'OK' if v3 == 0 else 'FALHA'}] implemento com temperatura_motor preenchido: {v3}")


# ---------------------------------------------------------------------------
# 8. Main
# ---------------------------------------------------------------------------

def main():
    np.random.seed(42)

    print("=== SafeField - Geracao do Dataset ===\n")

    print(f"Gerando {N_EQUIPAMENTOS} equipamentos...")
    equipamentos = generate_equipamentos(N_EQUIPAMENTOS)

    # Sortear qual equipamento corresponde a cada registro (~25 avaliacoes por equip.)
    equip_idx = np.random.choice(N_EQUIPAMENTOS, size=N_REGISTROS, replace=True)
    equip_records = equipamentos.iloc[equip_idx].reset_index(drop=True)

    print(f"Gerando {N_REGISTROS} registros...")
    ambientais = generate_ambientais(N_REGISTROS)
    geograficos = generate_geograficos(N_REGISTROS)
    operacionais = generate_operacionais(N_REGISTROS, equipamentos, equip_idx)

    df = pd.concat([
        equip_records[["equipamento_id"]],
        operacionais[["timestamp"]],
        ambientais,
        geograficos,
        operacionais[["tipo_operacao", "velocidade_kmh", "horas_operacao", "horario_operacao"]],
        equip_records[["tipo_equipamento", "idade_equipamento", "historico_sinistros", "tem_iot"]],
    ], axis=1)

    print("Aplicando regras de consistencia...")
    df = apply_consistency_rules(df)

    print("Calculando risk score...")
    df = calculate_risk_score(df)

    # Reordenar colunas conforme spec
    colunas_finais = [
        "equipamento_id", "timestamp",
        "temperatura_ar", "precipitacao_mm", "umidade_solo", "velocidade_vento", "condicao_clima",
        "latitude", "longitude", "tipo_solo", "distancia_agua_m", "declividade",
        "tipo_operacao", "velocidade_kmh", "vibracao_g", "temperatura_motor",
        "horas_operacao", "horario_operacao",
        "tipo_equipamento", "idade_equipamento", "historico_sinistros", "tem_iot",
        "risco_score", "faixa_risco",
    ]
    df = df[colunas_finais]

    validate_dataset(df)

    print("\nSalvando...")
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    caminho_parquet = os.path.join(raiz, "data", "dataset_safefield.parquet")
    caminho_csv = os.path.join(raiz, "data", "dataset_safefield.csv")

    df.to_parquet(caminho_parquet, index=False)
    print(f"  -> {caminho_parquet} ({len(df)} registros)")

    df.to_csv(caminho_csv, index=False)
    print(f"  -> {caminho_csv} ({len(df)} registros)")

    print("\n[OK] Dataset gerado com sucesso!")


if __name__ == "__main__":
    main()