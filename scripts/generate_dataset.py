"""
SafeField - Geracao do Dataset Simulado v2
Gera ~5.000 registros de avaliacoes de risco para equipamentos agricolas.
Dataset v2: expandido com features de operador (secao 2.7), manutencao (secao 2.8)
e metadados RAG (secao 2.9).

Spec: docs/data_schema.md
Execucao: python scripts/generate_dataset.py (a partir da raiz do projeto)

=== NOTA DE CALIBRACAO DOS PESOS ===
Os pesos foram recalibrados para atingir a distribuicao alvo de ~40% baixo / ~35% medio / ~25% alto.

Calibracao v1 (24 colunas):
  precipitacao_mm:     0.15 -> 0.10
  umidade_solo:        0.10 -> 0.08
  agua_score:          15   -> 12
  declividade:         0.20 -> 0.15
  velocidade_kmh:      0.15 -> 0.12
  horas_operacao:      0.80 -> 1.20  (aumentado: operacoes longas = mais fadiga/risco)
  noturno:             6    -> 5
  historico_sinistros: 2.0  -> 6.0   (aumentado: historico e o preditor mais forte)

Calibracao v2 (novas features de operador e manutencao):
  Para compensar as novas contribuicoes ao score_base, pesos ajustados em relacao a spec:
  historico_sinistros:              6.0  -> 5.70  (calibrado)
  horas_operacao:                   1.20 -> 0.82  (calibrado)
  pct_velocidade_acima_recomendada: 0.12 -> 0.02  (calibrado)
  freq_eventos_bruscos:             0.80 -> 0.10  (calibrado)
  score_operador_historico:         0.05 -> 0.01  (calibrado)
  atraso_manutencao_pct:            8.00 -> 0.60  (calibrado)
  noturno:                          5    -> 4     (calibrado)
  idade_equipamento:                0.40 -> 0.35  (calibrado)
  Interacoes 9/10/11:               10/12/8 -> 4/6/3 (calibrado)

Distribuicao obtida (seed=42): ~39% baixo / ~36% medio / ~25% alto

Adicionado: risco_acumulado = max(0, sinistros-3) * horas * 0.60
  Captura o risco composto: equipamentos acidentados + operacao prolongada.
  Ex: sinistros=8, horas=12 -> bonus de +30 pontos.

Adicionado: horas_operacao correlacionada com tipo_operacao:
  colheita/transporte: gamma(2,5) e gamma(1.5,6) -> media ~10h e ~9h
  plantio: gamma(1.5,3) -> media ~4.5h
  pulverizacao: exponencial(3) -> media ~3h
  parado: exponencial(1.5) -> media ~1.5h

Adicionado: distribuicao estratificada de sinistros em generate_equipamentos:
  Para equipamentos velhos (>10 anos): 35% baixo risco (0-2), 30% medio (2-5), 35% alto (5-10)
  Para equipamentos medios (3-10 anos): 50% baixo (0-1), 30% medio (1-3), 20% alto (3-6)
"""

import os
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

N_EQUIPAMENTOS = 200
N_REGISTROS = 5000
N_OPERADORES = 80

TIPOS_EQUIPAMENTO = ["trator", "colheitadeira", "implemento"]
TIPOS_OPERACAO = ["colheita", "transporte", "plantio", "pulverizacao", "parado"]
TIPOS_SOLO = ["argiloso", "misto", "arenoso"]
PESO_OPERACAO = [0.30, 0.25, 0.20, 0.15, 0.10]
PESO_EQUIPAMENTO = [0.45, 0.35, 0.20]
PESO_SOLO = [0.40, 0.35, 0.25]

MODELOS_EQUIPAMENTO = {
    "colheitadeira": ["John Deere S790", "Case IH A8810", "New Holland CR10.90"],
    "trator":        ["John Deere 7J195", "Massey Ferguson 7S.180", "New Holland T7.290"],
    "implemento":    ["Jumil JM-1440", "Baldan BFNT-15", "Marchesan CAP-7"],
}


# ---------------------------------------------------------------------------
# 1. Equipamentos
# ---------------------------------------------------------------------------

def generate_equipamentos(n=N_EQUIPAMENTOS):
    """
    Gera a tabela base de equipamentos com distribuicao estratificada de sinistros.
    Regra 1: ~30% com IoT, ~70% sem.
    Regra 8 (estendida): sinistros correlacionados com idade, em 3 tiers de risco.
    Regra 10: distribuicao de tipos.
    Regra 12: intervalos de manutencao recomendados por tipo.
    Regra 15: modelo de equipamento consistente com tipo.
    """
    ids = [f"EQ-{i:04d}" for i in range(1, n + 1)]
    tipos = np.random.choice(TIPOS_EQUIPAMENTO, size=n, p=PESO_EQUIPAMENTO)
    idades = np.random.randint(0, 26, size=n)

    sinistros = np.zeros(n, dtype=int)
    for i, idade in enumerate(idades):
        tier = np.random.random()
        if idade < 3:
            sinistros[i] = 2 if np.random.random() < 0.10 else np.random.randint(0, 2)
        elif idade <= 10:
            if tier < 0.50:
                sinistros[i] = np.random.randint(0, 2)
            elif tier < 0.80:
                sinistros[i] = np.random.randint(1, 4)
            else:
                sinistros[i] = np.random.randint(3, 7)
        else:
            if tier < 0.35:
                sinistros[i] = np.random.randint(0, 3)
            elif tier < 0.65:
                sinistros[i] = np.random.randint(2, 6)
            else:
                sinistros[i] = np.random.randint(5, 11)
    sinistros = np.clip(sinistros, 0, 10)

    tem_iot = np.random.random(n) < 0.30

    # Regra 15: modelo consistente com tipo_equipamento
    modelo_equipamento = [
        np.random.choice(MODELOS_EQUIPAMENTO[tipo]) for tipo in tipos
    ]

    # Regra 12: intervalos recomendados variam por tipo
    intervalo_dias = np.zeros(n, dtype=int)
    intervalo_horas = np.zeros(n, dtype=int)
    for i, tipo in enumerate(tipos):
        if tipo == "colheitadeira":
            intervalo_dias[i] = np.random.randint(90, 181)
            intervalo_horas[i] = np.random.randint(200, 501)
        elif tipo == "trator":
            intervalo_dias[i] = np.random.randint(120, 366)
            intervalo_horas[i] = np.random.randint(300, 1001)
        else:  # implemento
            intervalo_dias[i] = np.random.randint(180, 366)
            intervalo_horas[i] = np.random.randint(500, 1501)

    return pd.DataFrame({
        "equipamento_id": ids,
        "tipo_equipamento": tipos,
        "idade_equipamento": idades,
        "historico_sinistros": sinistros,
        "tem_iot": tem_iot,
        "modelo_equipamento": modelo_equipamento,
        "intervalo_manut_recomendado_dias": intervalo_dias,
        "intervalo_manut_recomendado_horas": intervalo_horas,
    })


# ---------------------------------------------------------------------------
# 1b. Operadores (Regras 13 e 16)
# ---------------------------------------------------------------------------

def generate_operadores(n=N_OPERADORES):
    """
    Gera perfis base dos operadores.
    Regra 13: pct_operacoes_noturnas e score_historico sao propriedades estaveis
    do operador, geradas uma vez e usadas com ruido pequeno em cada avaliacao.
    """
    ids = [f"OP-{i:04d}" for i in range(1, n + 1)]
    pct_noturnas_base = np.random.uniform(0, 100, n).round(1)
    score_historico_base = np.random.uniform(0, 100, n).round(1)

    return pd.DataFrame({
        "operador_id": ids,
        "pct_operacoes_noturnas_base": pct_noturnas_base,
        "score_operador_historico_base": score_historico_base,
    })


def assign_operadores_to_equipamentos(equipamentos_df, operadores_df):
    """
    Cria mapeamento equipamento_id -> lista de operador_id.
    Regra 16: cada equipamento tem 1-3 operadores; cada operador opera ate 5 equipamentos.
    Fallback permite exceder levemente o limite se todos os operadores estiverem no teto.
    """
    equip_ids = equipamentos_df["equipamento_id"].values
    op_ids = operadores_df["operador_id"].values
    n_op = len(op_ids)

    equip_op_map = {}
    op_count = np.zeros(n_op, dtype=int)

    for equip_id in equip_ids:
        n_ops = np.random.randint(1, 4)
        available = np.where(op_count < 5)[0]
        if len(available) == 0:
            available = np.arange(n_op)
            n_ops = 1
        elif len(available) < n_ops:
            n_ops = len(available)
        chosen = np.random.choice(available, size=n_ops, replace=False)
        equip_op_map[equip_id] = op_ids[chosen].tolist()
        op_count[chosen] += 1

    return equip_op_map


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
    Regra 11: horas_operacao correlacionada com tipo_operacao.
    """
    tipo_operacao = np.random.choice(TIPOS_OPERACAO, size=n, p=PESO_OPERACAO)

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

    # Regra 1: vibracao_g - sem IoT: 70% tem valor (0.1-2.0), 30% null
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
# 5b. Features de operador por avaliacao (Regras 13 e 16)
# ---------------------------------------------------------------------------

def generate_operador_features(df, operadores_df, equip_op_map):
    """
    Gera features de operador para cada registro de avaliacao.
    Regra 13: pct_operacoes_noturnas e score_operador_historico variam +-10% do perfil base.
    pct_velocidade_acima_recomendada e freq_eventos_bruscos sao por sessao (mais volateis).
    """
    n = len(df)
    equip_ids = df["equipamento_id"].values
    tipos_op = df["tipo_operacao"].values

    op_noturnas = operadores_df.set_index("operador_id")["pct_operacoes_noturnas_base"]
    op_score = operadores_df.set_index("operador_id")["score_operador_historico_base"]

    freq_ranges = {
        "parado":       (0.0, 1.0),
        "plantio":      (0.5, 5.0),
        "pulverizacao": (0.5, 5.0),
        "colheita":     (1.0, 10.0),
        "transporte":   (1.0, 12.0),
    }

    operador_ids = []
    pct_velocidade = np.zeros(n)
    freq_eventos = np.zeros(n)
    pct_noturnas = np.zeros(n)
    score_historico = np.zeros(n)

    for i in range(n):
        equip_id = equip_ids[i]
        tipo_op = tipos_op[i]

        ops = equip_op_map[equip_id]
        op_id = str(np.random.choice(ops))
        operador_ids.append(op_id)

        noturnas_base = op_noturnas[op_id]
        score_base_val = op_score[op_id]

        # Perfil base +- ruido pequeno (Regra 13: variacao +-10% ~ std=5)
        pct_noturnas[i] = float(np.clip(noturnas_base + np.random.normal(0, 5), 0, 100))
        score_historico[i] = float(np.clip(score_base_val + np.random.normal(0, 5), 0, 100))

        # pct_velocidade: correlacionada com score_historico do operador
        base_pct = score_historico[i] * 0.8 + np.random.normal(0, 15)
        pct_velocidade[i] = float(np.clip(base_pct, 0, 100))

        # freq_eventos: por tipo de operacao + agressividade do operador
        f_min, f_max = freq_ranges.get(tipo_op, (0.5, 5.0))
        aggression = score_historico[i] / 100.0
        base_freq = f_min + (f_max - f_min) * (aggression * 0.7 + 0.3) + np.random.normal(0, 1)
        freq_eventos[i] = float(np.clip(base_freq, 0, 20))

    return pd.DataFrame({
        "operador_id": operador_ids,
        "pct_velocidade_acima_recomendada": np.round(pct_velocidade, 1),
        "freq_eventos_bruscos": np.round(freq_eventos, 2),
        "pct_operacoes_noturnas": np.round(pct_noturnas, 1),
        "score_operador_historico": np.round(score_historico, 1),
    }, index=df.index)


# ---------------------------------------------------------------------------
# 5c. Features de manutencao (Regras 12 e 14)
# ---------------------------------------------------------------------------

def generate_manutencao_features(df):
    """
    Gera features de manutencao correlacionadas com idade e tipo de equipamento.
    Regra 12: equipamentos mais velhos tendem a ter manutencao mais atrasada.
    Regra 14: atraso_manutencao_pct SEMPRE derivado, nunca gerado independentemente.
    """
    n = len(df)
    idades = df["idade_equipamento"].values
    int_dias = df["intervalo_manut_recomendado_dias"].values.astype(float)
    int_horas = df["intervalo_manut_recomendado_horas"].values.astype(float)

    # Probabilidade de estar atrasado baseada na idade (Regra 12)
    prob_atrasada = np.where(idades < 3, 0.05, np.where(idades <= 10, 0.30, 0.50))
    max_ratio = np.where(idades < 3, 1.3, np.where(idades <= 10, 1.8, 2.5))

    atrasada_intended = np.random.random(n) < prob_atrasada

    # ultima_manutencao_dias
    r_on = np.random.uniform(0, 0.95, n)
    r_late = 1.01 + np.random.uniform(0, 1, n) * (max_ratio - 1.01)
    ratio_dias = np.where(atrasada_intended, r_late, r_on)
    ultima_dias = np.clip((ratio_dias * int_dias).astype(int), 0, 365)

    # ultima_manutencao_horas_op
    r_horas_on_factor = np.random.uniform(0.5, 1.5, n)
    r_horas_late = 1.01 + np.random.uniform(0, 1, n) * (max_ratio - 1.01)
    horas_on = np.clip(ratio_dias * int_horas * r_horas_on_factor, 0, int_horas * 0.99)
    horas_late = np.clip(r_horas_late * int_horas, 0, int_horas * max_ratio)
    ultima_horas = np.clip(np.where(atrasada_intended, horas_late, horas_on), 0, 2000.0)

    # Regra 14: SEMPRE derivar
    atraso_pct = np.maximum(
        ultima_dias / int_dias,
        ultima_horas / int_horas,
    )
    atraso_pct = np.round(np.clip(atraso_pct, 0, 3.0), 3)
    manutencao_atrasada = atraso_pct > 1.0

    return pd.DataFrame({
        "ultima_manutencao_dias": ultima_dias,
        "ultima_manutencao_horas_op": np.round(ultima_horas, 1),
        "manutencao_atrasada": manutencao_atrasada,
        "atraso_manutencao_pct": atraso_pct,
    }, index=df.index)


# ---------------------------------------------------------------------------
# 6. Calculo do score de risco
# ---------------------------------------------------------------------------

def calculate_risk_score(df):
    """
    Aplica a formula da secao 4 do data_schema.md com pesos recalibrados v2.
    Ver docstring do modulo para detalhes dos ajustes.
    """
    df = df.copy()

    noturno = ((df["horario_operacao"] >= 20) | (df["horario_operacao"] <= 5)).astype(int)
    vibracao_valor = df["vibracao_g"].fillna(0)

    agua_score = np.maximum(0, (500 - df["distancia_agua_m"]) / 500)

    # score_base: contribuicoes individuais (pesos recalibrados v2)
    score_base = (
        df["precipitacao_mm"]       * 0.10
        + df["umidade_solo"]        * 0.08
        + df["velocidade_vento"]    * 0.05
        + agua_score                  * 12
        + df["declividade"]         * 0.15
        + df["velocidade_kmh"]      * 0.12
        + df["horas_operacao"]      * 0.82   # calibrado: 1.20 -> 0.82
        + noturno                     * 4
        + df["idade_equipamento"]   * 0.35
        + df["historico_sinistros"] * 5.70   # calibrado: 6.00 -> 5.70
        # --- features de operador (secao 2.7) ---
        + df["pct_velocidade_acima_recomendada"] * 0.02   # spec 0.12, calibrado
        + df["freq_eventos_bruscos"]              * 0.10   # spec 0.80, calibrado
        + df["score_operador_historico"]          * 0.02   # spec 0.05, calibrado
        # --- features de manutencao (secao 2.8) ---
        + df["atraso_manutencao_pct"]             * 0.60   # spec 8.00, calibrado
    )

    # Bonus de interacoes (secao 4.3)
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

    # 8. Risco acumulado: equipamentos acidentados em operacoes longas
    risco_acumulado = (
        np.maximum(0, df["historico_sinistros"] - 3)
        * df["horas_operacao"]
        * 0.60
    )

    # 9. Operador agressivo + condicoes ruins = risco composto
    interacoes += (
        (df["pct_velocidade_acima_recomendada"] > 30) & (df["precipitacao_mm"] > 20)
    ) * 4

    # 10. Manutencao atrasada + operacao intensa = falha mecanica provavel
    interacoes += ((df["atraso_manutencao_pct"] > 1.2) & (df["horas_operacao"] > 8)) * 6

    # 11. Operador noturno habitual + operacao noturna atual = fadiga cronica
    interacoes += ((df["pct_operacoes_noturnas"] > 50) & (noturno == 1)) * 3

    ruido = np.random.normal(0, 5, len(df))
    score_raw = score_base + interacoes + risco_acumulado + ruido
    df["risco_score"] = np.clip(score_raw, 0, 100).round(1)

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

    def ok(cond):
        return "OK" if cond else "FALHA"

    print()
    print("=== Validacoes ===")
    print()
    print(f"Shape: {df.shape}")

    print()
    print("Distribuicao faixa_risco:")
    for faixa in ["baixo", "medio", "alto"]:
        count = (df["faixa_risco"] == faixa).sum()
        pct = count / len(df) * 100
        print(f"  {faixa}: {count} ({pct:.1f}%)")

    print()
    print("Nulls:")
    for col in ["vibracao_g", "temperatura_motor"]:
        n_null = df[col].isna().sum()
        pct = n_null / len(df) * 100
        print(f"  {col}: {n_null} ({pct:.1f}%)")

    print()
    print("Ranges numericos:")
    cols_num = [
        "temperatura_ar", "precipitacao_mm", "umidade_solo", "velocidade_vento",
        "distancia_agua_m", "declividade", "velocidade_kmh", "vibracao_g",
        "temperatura_motor", "horas_operacao", "horario_operacao",
        "idade_equipamento", "historico_sinistros",
        "pct_velocidade_acima_recomendada", "freq_eventos_bruscos",
        "pct_operacoes_noturnas", "score_operador_historico",
        "ultima_manutencao_dias", "ultima_manutencao_horas_op",
        "intervalo_manut_recomendado_dias", "intervalo_manut_recomendado_horas",
        "atraso_manutencao_pct", "risco_score",
    ]
    for col in cols_num:
        d = df[col].dropna()
        print(f"  {col:<42}: {d.min():.1f} a {d.max():.1f}")

    v1 = ((~df["tem_iot"]) & df["temperatura_motor"].notna()).sum()
    v2 = ((df["tipo_operacao"] == "parado") & (df["velocidade_kmh"] > 0)).sum()
    v3 = ((df["tipo_equipamento"] == "implemento") & df["temperatura_motor"].notna()).sum()
    print()
    print("Consistencia:")
    print(f"  [{ok(v1 == 0)}] tem_iot=false com temperatura_motor preenchido: {v1}")
    print(f"  [{ok(v2 == 0)}] parado com velocidade > 0: {v2}")
    print(f"  [{ok(v3 == 0)}] implemento com temperatura_motor preenchido: {v3}")

    v7a = ((df["manutencao_atrasada"]) & (df["atraso_manutencao_pct"] <= 1.0)).sum()
    v7b = ((~df["manutencao_atrasada"]) & (df["atraso_manutencao_pct"] > 1.0)).sum()
    print(f"  [{ok(v7a == 0)}] manutencao_atrasada=True com atraso<=1.0: {v7a}")
    print(f"  [{ok(v7b == 0)}] manutencao_atrasada=False com atraso>1.0: {v7b}")

    modelo_to_tipo = {}
    for tipo, modelos in MODELOS_EQUIPAMENTO.items():
        for modelo in modelos:
            modelo_to_tipo[modelo] = tipo
    tipo_esperado = df["modelo_equipamento"].map(modelo_to_tipo)
    incompat = (tipo_esperado != df["tipo_equipamento"]).sum()
    print(f"  [{ok(incompat == 0)}] modelo_equipamento incompativel com tipo: {incompat}")

    max_std = df.groupby("operador_id")["score_operador_historico"].std().max()
    ok_std = (max_std <= 10) if not np.isnan(max_std) else True
    print(f"  [{ok(ok_std)}] desvio padrao max score_operador por operador: {max_std:.2f} (esperado <=10)")

    print()
    print("Estatisticas adicionais:")
    n_op_unicos = df["operador_id"].nunique()
    print(f"  Operadores unicos: {n_op_unicos} (esperado ~80)")
    equip_por_op = df.groupby("operador_id")["equipamento_id"].nunique().mean()
    print(f"  Media de equipamentos por operador: {equip_por_op:.1f}")
    atrasada_n = df["manutencao_atrasada"].sum()
    print(f"  Manutencao atrasada: {atrasada_n} ({atrasada_n / len(df) * 100:.1f}%)")



# ---------------------------------------------------------------------------
# 8. Main
# ---------------------------------------------------------------------------

def main():
    np.random.seed(42)

    print("=== SafeField - Geracao do Dataset v2 ===")
    print()

    print(f"Gerando {N_EQUIPAMENTOS} equipamentos...")
    equipamentos = generate_equipamentos(N_EQUIPAMENTOS)

    print(f"Gerando {N_OPERADORES} operadores e mapeamentos (Regras 13, 16)...")
    operadores = generate_operadores(N_OPERADORES)
    equip_op_map = assign_operadores_to_equipamentos(equipamentos, operadores)

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
        equip_records[[
            "tipo_equipamento", "idade_equipamento", "historico_sinistros", "tem_iot",
            "modelo_equipamento",
            "intervalo_manut_recomendado_dias", "intervalo_manut_recomendado_horas",
        ]],
    ], axis=1)

    print("Aplicando regras de consistencia...")
    df = apply_consistency_rules(df)

    print("Gerando features de operador (Regras 13, 16)...")
    op_features = generate_operador_features(df, operadores, equip_op_map)
    df = pd.concat([df, op_features], axis=1)

    print("Gerando features de manutencao (Regras 12, 14)...")
    manut_features = generate_manutencao_features(df)
    df = pd.concat([df, manut_features], axis=1)

    rand_cat = np.random.random(len(df))
    prob_manut = np.where(df["manutencao_atrasada"], 0.50, 0.10)
    sufixo = np.where(rand_cat < prob_manut, "_manutencao", "_operacao")
    df["categoria_manual"] = df["tipo_equipamento"].values + sufixo

    print("Calculando risk score...")
    df = calculate_risk_score(df)

    colunas_finais = [
        "equipamento_id", "timestamp",
        "temperatura_ar", "precipitacao_mm", "umidade_solo", "velocidade_vento", "condicao_clima",
        "latitude", "longitude", "tipo_solo", "distancia_agua_m", "declividade",
        "tipo_operacao", "velocidade_kmh", "vibracao_g", "temperatura_motor",
        "horas_operacao", "horario_operacao",
        "tipo_equipamento", "idade_equipamento", "historico_sinistros", "tem_iot",
        "modelo_equipamento", "categoria_manual",
        "operador_id", "pct_velocidade_acima_recomendada", "freq_eventos_bruscos",
        "pct_operacoes_noturnas", "score_operador_historico",
        "ultima_manutencao_dias", "ultima_manutencao_horas_op",
        "intervalo_manut_recomendado_dias", "intervalo_manut_recomendado_horas",
        "manutencao_atrasada", "atraso_manutencao_pct",
        "risco_score", "faixa_risco",
    ]
    df = df[colunas_finais]

    validate_dataset(df)

    print()
    print("Salvando...")
    raiz = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    caminho_parquet = os.path.join(raiz, "data", "dataset_safefield.parquet")
    caminho_csv = os.path.join(raiz, "data", "dataset_safefield.csv")

    df.to_parquet(caminho_parquet, index=False)
    print(f"  -> {caminho_parquet} ({len(df)} registros)")

    df.to_csv(caminho_csv, index=False)
    print(f"  -> {caminho_csv} ({len(df)} registros)")

    print()
    print("[OK] Dataset v2 gerado com sucesso!")


if __name__ == "__main__":
    main()
