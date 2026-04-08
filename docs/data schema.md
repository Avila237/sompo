# SafeField — Schema do Dataset

> Referência única para geração, validação e consumo dos dados do projeto.
> Este documento é a spec que o script `scripts/generate_dataset.py` deve seguir.

---

## 1. Visão Geral

> **Dataset v2** — expandido com features de operador e manutenção (~40 colunas).

- **Tamanho alvo:** ~5.000 registros
- **Colunas:** ~40 (identificação, ambientais, geográficas, operacionais, equipamento, operador, manutenção, metadados RAG, target)
- **Formato de saída:** `.parquet` (primário) + `.csv` (referência visual)
- **Localização:** `data/dataset_safefield.parquet` e `data/dataset_safefield.csv`
- **Cada registro representa:** uma avaliação de risco de um equipamento em um momento e contexto operacional específico

---

## 2. Schema das Colunas

### 2.1 Identificação

| Coluna | Tipo Python | Domínio | Nullable | Fonte | Descrição |
|---|---|---|---|---|---|
| `equipamento_id` | str | `EQ-0001` a `EQ-0200` | não | cadastro | Identificador único. ~200 equipamentos com múltiplas avaliações cada |
| `timestamp` | datetime | 2025-01-01 a 2025-12-31 | não | sistema | Momento da avaliação. Distribuído ao longo de um ano |

### 2.2 Dados Ambientais (origem: Open-Meteo)

| Coluna | Tipo Python | Domínio | Nullable | Descrição |
|---|---|---|---|---|
| `temperatura_ar` | float | -5.0 a 45.0 °C | não | Temperatura ambiente no momento da operação |
| `precipitacao_mm` | float | 0.0 a 120.0 mm | não | Chuva acumulada nas últimas 24h |
| `umidade_solo` | float | 5.0 a 95.0 % | não | Estimativa derivada (ver regra de consistência 3) |
| `velocidade_vento` | float | 0.0 a 80.0 km/h | não | Intensidade do vento na região |
| `condicao_clima` | str (cat) | ensolarado, nublado, chuvoso, tempestade | não | Condição climática geral |

### 2.3 Dados Geográficos (origem: IBGE + GPS)

| Coluna | Tipo Python | Domínio | Nullable | Descrição |
|---|---|---|---|---|
| `latitude` | float | -33.75 a -2.50 | não | Latitude (limites do Brasil) |
| `longitude` | float | -73.99 a -34.79 | não | Longitude (limites do Brasil) |
| `tipo_solo` | str (cat) | arenoso, argiloso, misto | não | Tipo de solo derivado da região |
| `distancia_agua_m` | float | 10.0 a 5000.0 | não | Distância ao corpo d'água mais próximo (metros) |
| `declividade` | float | 0.0 a 45.0 % | não | Inclinação do terreno na posição atual |

### 2.4 Dados Operacionais (origem: App + IoT)

| Coluna | Tipo Python | Domínio | Nullable | Descrição |
|---|---|---|---|---|
| `tipo_operacao` | str (cat) | colheita, plantio, pulverizacao, transporte, parado | não | Tipo de operação em execução |
| `velocidade_kmh` | float | 0.0 a 40.0 km/h | não | Velocidade de deslocamento (ver regra 4) |
| `vibracao_g` | float | 0.1 a 4.0 g | **sim** | Acelerômetro. Null se sem nenhum sensor |
| `temperatura_motor` | float | 50.0 a 120.0 °C | **sim** | Sensor DS18B20 via IoT. Null se `tem_iot=false` |
| `horas_operacao` | float | 0.0 a 24.0 h | não | Horas contínuas de operação na sessão atual |
| `horario_operacao` | int | 0 a 23 | não | Hora do dia (20–5 = noturno = risco elevado) |

### 2.5 Dados do Equipamento (origem: cadastro no app)

| Coluna | Tipo Python | Domínio | Nullable | Descrição |
|---|---|---|---|---|
| `tipo_equipamento` | str (cat) | colheitadeira, trator, implemento | não | Tipo da máquina |
| `idade_equipamento` | int | 0 a 25 anos | não | Tempo desde fabricação |
| `historico_sinistros` | int | 0 a 10 | não | Quantidade de sinistros anteriores registrados |
| `tem_iot` | bool | true / false | não | Se possui dispositivo IoT acoplado |

### 2.6 Variável Alvo

| Coluna | Tipo Python | Domínio | Nullable | Descrição |
|---|---|---|---|---|
| `risco_score` | float | 0.0 a 100.0 | não | Score contínuo de risco (gerado pela fórmula da seção 4) |
| `faixa_risco` | str (cat) | baixo, medio, alto | não | Derivada: baixo (0–33), medio (34–66), alto (67–100) |

### 2.7 Dados do Operador (origem: app + histórico calculado)

| Coluna | Tipo Python | Domínio | Nullable | Descrição |
|---|---|---|---|---|
| `operador_id` | str | `OP-0001` a `OP-0080` | não | ~80 operadores, múltiplos equipamentos cada |
| `pct_velocidade_acima_recomendada` | float | 0.0 a 100.0 % | não | % do tempo acima da velocidade recomendada para a operação |
| `freq_eventos_bruscos` | float | 0.0 a 20.0 /hora | não | Eventos de aceleração/frenagem brusca por hora |
| `pct_operacoes_noturnas` | float | 0.0 a 100.0 % | não | Proporção histórica de operações realizadas no período noturno |
| `score_operador_historico` | float | 0.0 a 100.0 | não | Média móvel do score de risco do operador nos últimos 30 dias |

### 2.8 Dados de Manutenção (origem: app + base de conhecimento)

| Coluna | Tipo Python | Domínio | Nullable | Descrição |
|---|---|---|---|---|
| `ultima_manutencao_dias` | int | 0 a 365 | não | Dias desde a última manutenção declarada pelo operador |
| `ultima_manutencao_horas_op` | float | 0.0 a 2000.0 | não | Horas de operação acumuladas desde a última manutenção |
| `intervalo_manut_recomendado_dias` | int | 90 a 365 | não | Intervalo recomendado pelo fabricante em dias |
| `intervalo_manut_recomendado_horas` | int | 200 a 1500 | não | Intervalo recomendado pelo fabricante em horas de operação |
| `manutencao_atrasada` | bool | true / false | não | Calculado: `true` se ultrapassou qualquer um dos dois limites |
| `atraso_manutencao_pct` | float | 0.0 a 3.0 | não | 1.0 = no limite, 1.5 = 50% atrasado, 0.5 = metade do caminho (ver Regra 14) |

### 2.9 Metadados do Equipamento para RAG (não são features do modelo)

> Estas colunas são informativas — usadas para busca na base de conhecimento após o treinamento do XGBoost. Não devem entrar como features de entrada do modelo.

| Coluna | Tipo Python | Domínio | Nullable | Descrição |
|---|---|---|---|---|
| `modelo_equipamento` | str (cat) | lista de modelos simulados (ver Regra 15) | não | Modelo específico do equipamento (ex: "John Deere S790") |
| `categoria_manual` | str (cat) | colheitadeira_operacao, colheitadeira_manutencao, trator_operacao, trator_manutencao, implemento_operacao, implemento_manutencao | não | Categoria do manual técnico para busca RAG |

<!-- TODO: definir lista completa de modelos simulados por tipo de equipamento -->

---

## 3. Regras de Consistência

O script de geração **deve** respeitar estas regras. Dados que violem qualquer regra são inválidos.

### Regra 1 — IoT e nullability
- Se `tem_iot = false` → `temperatura_motor` **deve** ser `null`
- Se `tem_iot = true` → `temperatura_motor` **deve** ter valor (50–120)
- `vibracao_g`:
  - `tem_iot = true` → range 0.1–4.0 (acelerômetro dedicado, mais sensível)
  - `tem_iot = false` → 70% das vezes tem valor (acelerômetro do celular), range 0.1–2.0; 30% é `null`
- Proporção sugerida: ~30% dos equipamentos com IoT, ~70% sem

### Regra 2 — Faixa de risco é derivada
- `faixa_risco` é **sempre** calculada a partir de `risco_score`, nunca gerada independentemente
- Faixas: `baixo` (0.0–33.0), `medio` (33.1–66.0), `alto` (66.1–100.0)

### Regra 3 — Umidade do solo correlaciona com precipitação + tipo de solo
- Fórmula sugerida:
  ```
  base_umidade = precipitacao_mm * 0.5 + random(5, 15)
  fator_solo = 1.3 se argiloso, 1.0 se misto, 0.7 se arenoso
  umidade_solo = clip(base_umidade * fator_solo, 5, 95)
  ```
- Argiloso retém mais água → mesma chuva gera mais umidade

### Regra 4 — Velocidade correlaciona com tipo de operação
- Ranges por operação:
  - `parado` → 0.0 km/h (fixo)
  - `colheita` → 3.0–8.0 km/h
  - `plantio` → 3.0–8.0 km/h
  - `pulverizacao` → 8.0–15.0 km/h
  - `transporte` → 15.0–40.0 km/h

### Regra 5 — Condição clima correlaciona com precipitação
- `precipitacao_mm` 0–2 → `ensolarado` ou `nublado`
- `precipitacao_mm` 2–20 → `nublado` ou `chuvoso`
- `precipitacao_mm` 20–50 → `chuvoso`
- `precipitacao_mm` > 50 → `chuvoso` ou `tempestade`

### Regra 6 — Vibração correlaciona com operação e velocidade
- Operações com mais impacto mecânico geram mais vibração:
  - `parado` → 0.1–0.3
  - `colheita` → 0.8–2.5 (ceifar gera impacto)
  - `plantio` → 0.5–1.5
  - `pulverizacao` → 0.3–1.0
  - `transporte` → 0.4–2.0 (depende da estrada/terreno)
- Adicionar leve correlação positiva com `velocidade_kmh` dentro de cada faixa

### Regra 7 — Temperatura do motor correlaciona com horas de operação
- Mais horas → motor mais quente
- Fórmula sugerida: `temperatura_motor = 60 + horas_operacao * 3 + random(-5, 5)`
- Clip em [50, 120]

### Regra 8 — Histórico de sinistros correlaciona com idade
- Equipamentos mais velhos tendem a ter mais sinistros:
  - `idade < 3` → historico 0–1 (90%), 2 (10%)
  - `idade 3–10` → distribuição estratificada: 50% baixo (0–1), 30% médio (1–3), 20% alto (3–6)  (calibrado)
  - `idade > 10` → distribuição estratificada: 35% baixo (0–2), 30% médio (2–5), 35% alto (5–10)  (calibrado)

### Regra 9 — Distribuição de tipos de operação
- Não uniforme. Sugestão: colheita 30%, transporte 25%, plantio 20%, pulverizacao 15%, parado 10%

### Regra 10 — Distribuição de tipos de equipamento
- Sugestão: trator 45%, colheitadeira 35%, implemento 20%
- Implementos não têm motor próprio → `temperatura_motor` null mesmo com IoT? **Decisão: sim.** Implemento com `tem_iot = true` lê vibração mas não temperatura de motor.

### Regra 11 — horas_operacao correlaciona com tipo_operacao  (calibrado)
- Distribuições de horas por tipo de operação para maior realismo:
  - `colheita` → gamma(2, 5) → média ~10h (safras longas)
  - `transporte` → gamma(1.5, 6) → média ~9h
  - `plantio` → gamma(1.5, 3) → média ~4.5h
  - `pulverizacao` → exponencial(3) → média ~3h
  - `parado` → exponencial(1.5) → média ~1.5h
- Todas clampadas em [0, 24]

### Regra 12 — Manutenção correlaciona com idade e tipo de equipamento
- Equipamentos mais velhos tendem a ter manutenção mais atrasada:
  - `idade < 3` → `ultima_manutencao_dias` tende a ser baixo (0–60), `atraso_manutencao_pct` ≤ 1.0 na maioria
  - `idade 3–10` → distribuição equilibrada, ~30% com `manutencao_atrasada = true`
  - `idade > 10` → ~50% com `manutencao_atrasada = true`, `atraso_manutencao_pct` pode chegar a 2.0
- Intervalos recomendados variam por tipo:
  - `colheitadeira` → `intervalo_manut_recomendado_dias` 90–180, horas 200–500 (manutenção mais frequente)
  - `trator` → dias 120–365, horas 300–1000
  - `implemento` → dias 180–365, horas 500–1500

### Regra 13 — Perfil do operador é consistente por operador_id
- O mesmo `operador_id` deve ter valores semelhantes de `pct_operacoes_noturnas` e `score_operador_historico` entre avaliações próximas (não muda radicalmente de uma avaliação para outra)
- Variação permitida entre avaliações do mesmo operador: ±10% em `pct_operacoes_noturnas` e `score_operador_historico`
- `freq_eventos_bruscos` e `pct_velocidade_acima_recomendada` podem variar mais entre avaliações (refletem comportamento na sessão atual)
- Implementação sugerida: gerar perfil base por `operador_id` e adicionar ruído gaussiano pequeno em cada avaliação

### Regra 14 — atraso_manutencao_pct é derivado
- Calculado como o máximo entre o atraso em dias e o atraso em horas:
  ```
  atraso_manutencao_pct = max(
      ultima_manutencao_dias / intervalo_manut_recomendado_dias,
      ultima_manutencao_horas_op / intervalo_manut_recomendado_horas
  )
  ```
- `manutencao_atrasada = atraso_manutencao_pct > 1.0`
- Nunca gerar `manutencao_atrasada` e `atraso_manutencao_pct` de forma independente — sempre derivar

### Regra 15 — modelo_equipamento correlaciona com tipo_equipamento
- Modelos de colheitadeira só aparecem em registros com `tipo_equipamento = "colheitadeira"`, e assim por diante
- Exemplos sugeridos por tipo:
  - `colheitadeira` → "John Deere S790", "Case IH A8810", "New Holland CR10.90"
  - `trator` → "John Deere 7J195", "Massey Ferguson 7S.180", "New Holland T7.290"
  - `implemento` → "Jumil JM-1440", "Baldan BFNT-15", "Marchesan CAP-7"

### Regra 16 — Operadores por equipamento
- Cada equipamento pode ter 1–3 operadores diferentes ao longo do ano
- Cada operador pode operar 1–5 equipamentos diferentes
- Implementação: gerar mapeamento `equipamento_id → lista de operador_id` durante a geração dos equipamentos

---

## 4. Fórmula de Geração do Score (Modelo Professor)

> **IMPORTANTE:** Esta fórmula é usada **exclusivamente** no script de geração.
> O XGBoost nunca vê esta fórmula — ele recebe features + score e aprende a relação sozinho.
> Em produção, quem calcula o score é o modelo treinado, não esta fórmula.

### 4.1 Variáveis auxiliares

```python
noturno = 1 if (horario_operacao >= 20 or horario_operacao <= 5) else 0

vibracao_valor = vibracao_g if not null else 0  # para cálculo do score, null tratado como 0
```

### 4.2 Contribuições individuais (pesos recalibrados)

Os pesos foram calibrados para que o score_base raramente ultrapasse 70 em condições
normais, deixando espaço para as interações elevarem o score em combinações perigosas.

```python
score_base = (
    precipitacao_mm * 0.10          # 0–120 → máx ~12 pts   (calibrado)
    + umidade_solo * 0.08           # 5–95  → máx ~7.6 pts  (calibrado)
    + velocidade_vento * 0.05       # 0–80  → máx ~4 pts
    + agua_score * 12               # 0–1   → máx 12 pts (ver abaixo)  (calibrado)
    + declividade * 0.15            # 0–45  → máx ~6.75 pts (calibrado)
    + velocidade_kmh * 0.12         # 0–40  → máx ~4.8 pts  (calibrado)
    + horas_operacao * 1.20         # 0–24  → máx ~28.8 pts (calibrado)
    + noturno * 5                   # 0/1   → 0 ou 5 pts    (calibrado)
    + idade_equipamento * 0.4       # 0–25  → máx ~10 pts
    + historico_sinistros * 6.0     # 0–10  → máx ~60 pts   (calibrado)
    # --- features de operador ---
    + pct_velocidade_acima_recomendada * 0.12  # 0–100 → máx ~12 pts
    + freq_eventos_bruscos * 0.8               # 0–20  → máx ~16 pts
    + score_operador_historico * 0.05          # 0–100 → máx ~5 pts
    # --- features de manutenção ---
    + atraso_manutencao_pct * 8.0              # 0–3   → máx ~24 pts
)
# Máximo teórico do score_base: ~214 (caso extremo, improvável)
# Caso típico alto: ~70-90

# agua_score: transformação não-linear da distância
agua_score = max(0, (500 - distancia_agua_m)) / 500  # 0 se >500m, 1 se 10m
```

### 4.3 Bônus de interação

Cada interação usa uma condição booleana. Se verdadeira, soma o bônus ao score.

```python
interacoes = 0

# 1. Chuva forte + solo argiloso = terreno perigoso
if precipitacao_mm > 30 and tipo_solo == "argiloso":
    interacoes += 12

# 2. Velocidade alta + declividade = risco de tombamento
if velocidade_kmh > 20 and declividade > 15:
    interacoes += 10

# 3. Proximidade de água + chuva = risco de alagamento
if distancia_agua_m < 200 and precipitacao_mm > 25:
    interacoes += 15

# 4. Operação noturna + velocidade alta = visibilidade ruim
if noturno and velocidade_kmh > 15:
    interacoes += 8

# 5. Equipamento velho + vibração alta = falha mecânica
if idade_equipamento > 10 and vibracao_valor > 2.0:
    interacoes += 10

# 6. Transporte rápido em terreno inclinado = cenário grave
if tipo_operacao == "transporte" and velocidade_kmh > 25 and declividade > 10:
    interacoes += 12

# 7. Muitas horas + noturno = fadiga extrema
if horas_operacao > 8 and noturno:
    interacoes += 10

# 8. Equipamento com histórico alto + operação prolongada = risco composto  (calibrado)
risco_acumulado = max(0, historico_sinistros - 3) * horas_operacao * 0.60
# Captura risco composto: equipamentos acidentados operando por muitas horas.
# Exemplo: sinistros=8, horas=12 → bônus de +30 pontos

# 9. Operador agressivo + condições ruins = risco composto
if pct_velocidade_acima_recomendada > 30 and precipitacao_mm > 20:
    interacoes += 10

# 10. Manutenção atrasada + operação intensa = falha mecânica provável
if atraso_manutencao_pct > 1.2 and horas_operacao > 8:
    interacoes += 12

# 11. Operador noturno habitual + operação noturna atual = fadiga crônica
if pct_operacoes_noturnas > 50 and noturno:
    interacoes += 8

# Máximo teórico das interações: 107 (todas ativas simultaneamente, muito raro)
# Caso típico: 0–30
```

### 4.4 Score final

```python
import numpy as np

ruido = np.random.normal(0, 3)  # ruído gaussiano para evitar aprendizado perfeito
score_raw = score_base + interacoes + risco_acumulado + ruido
risco_score = np.clip(score_raw, 0, 100).round(1)

# Faixa derivada
if risco_score <= 33:
    faixa_risco = "baixo"
elif risco_score <= 66:
    faixa_risco = "medio"
else:
    faixa_risco = "alto"
```

### 4.5 Distribuição alvo

Após geração, verificar se a distribuição aproxima:
- **Baixo (0–33):** ~40% dos registros (obtido com seed=42: 39.9%)
- **Médio (34–66):** ~35% dos registros (obtido com seed=42: 35.1%)
- **Alto (67–100):** ~25% dos registros (obtido com seed=42: 24.9%)

Se a distribuição estiver muito diferente, ajustar os pesos da seção 4.2.
Essa proporção reflete a realidade de seguros: a maioria das operações é segura,
um grupo intermediário merece atenção, e uma minoria é realmente perigosa.

---

## 5. Orientações para Implementação

### 5.1 Estrutura sugerida do script

```
scripts/
  generate_dataset.py     ← script principal
data/
  dataset_safefield.parquet  ← formato primário (preserva tipos)
  dataset_safefield.csv      ← formato visual (debug/apresentação)
docs/
  data_schema.md           ← este documento
```

### 5.2 Dependências do script
- `pandas` — manipulação de dados
- `numpy` — distribuições e ruído
- `pyarrow` — salvar parquet

### 5.3 Seed para reprodutibilidade
- Usar `np.random.seed(42)` no início do script
- O dataset gerado deve ser idêntico em qualquer execução

### 5.4 Validações pós-geração (o script deve imprimir)
1. Shape: (5000, ~40)
2. Distribuição de `faixa_risco` (% por faixa)
3. Contagem de nulls em `vibracao_g` e `temperatura_motor`
4. Ranges de todas as colunas numéricas (min/max)
5. Consistência: nenhum registro com `tem_iot=false` e `temperatura_motor` preenchido
6. Consistência: nenhum `parado` com `velocidade_kmh > 0`
7. Consistência: `manutencao_atrasada` sempre derivado corretamente de `atraso_manutencao_pct`
8. Consistência: `modelo_equipamento` compatível com `tipo_equipamento` (Regra 15)
9. Perfil de operador: variação de `score_operador_historico` dentro de ±10% por `operador_id` (Regra 13)

---

## 6. Evolução Futura

- Quando dados reais forem coletados (app + IoT), este schema será a referência para validação de entrada
- O schema pode ser convertido em um contrato Pandera ou Pydantic para validação automatizada
- Novas features podem ser adicionadas (ex: dados OBD-II) seguindo o mesmo formato