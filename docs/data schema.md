# SafeField — Schema do Dataset

> Referência única para geração, validação e consumo dos dados do projeto.
> Este documento é a spec que o script `scripts/generate_dataset.py` deve seguir.

---

## 1. Visão Geral

- **Tamanho alvo:** ~5.000 registros
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
  - `idade 3–10` → historico 0–3
  - `idade > 10` → historico 0–6, com possibilidade de até 10

### Regra 9 — Distribuição de tipos de operação
- Não uniforme. Sugestão: colheita 30%, transporte 25%, plantio 20%, pulverizacao 15%, parado 10%

### Regra 10 — Distribuição de tipos de equipamento
- Sugestão: trator 45%, colheitadeira 35%, implemento 20%
- Implementos não têm motor próprio → `temperatura_motor` null mesmo com IoT? **Decisão: sim.** Implemento com `tem_iot = true` lê vibração mas não temperatura de motor.

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
    precipitacao_mm * 0.15          # 0–120 → máx ~18 pts
    + umidade_solo * 0.10           # 5–95  → máx ~9.5 pts
    + velocidade_vento * 0.05       # 0–80  → máx ~4 pts
    + agua_score * 15               # 0–1   → máx 15 pts (ver abaixo)
    + declividade * 0.20            # 0–45  → máx ~9 pts
    + velocidade_kmh * 0.15         # 0–40  → máx ~6 pts
    + horas_operacao * 0.8          # 0–24  → máx ~19 pts
    + noturno * 6                   # 0/1   → 0 ou 6 pts
    + idade_equipamento * 0.4       # 0–25  → máx ~10 pts
    + historico_sinistros * 2.0     # 0–10  → máx ~20 pts
)
# Máximo teórico do score_base: ~117 (caso extremo, improvável)
# Caso típico alto: ~55-70

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

# Máximo teórico das interações: 77 (todas ativas simultaneamente, muito raro)
# Caso típico: 0–25
```

### 4.4 Score final

```python
import numpy as np

ruido = np.random.normal(0, 3)  # ruído gaussiano para evitar aprendizado perfeito
score_raw = score_base + interacoes + ruido
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
- **Baixo (0–33):** ~40% dos registros
- **Médio (34–66):** ~35% dos registros
- **Alto (67–100):** ~25% dos registros

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
1. Shape: (5000, 22)
2. Distribuição de `faixa_risco` (% por faixa)
3. Contagem de nulls em `vibracao_g` e `temperatura_motor`
4. Ranges de todas as colunas numéricas (min/max)
5. Consistência: nenhum registro com `tem_iot=false` e `temperatura_motor` preenchido
6. Consistência: nenhum `parado` com `velocidade_kmh > 0`

---

## 6. Evolução Futura

- Quando dados reais forem coletados (app + IoT), este schema será a referência para validação de entrada
- O schema pode ser convertido em um contrato Pandera ou Pydantic para validação automatizada
- Novas features podem ser adicionadas (ex: dados OBD-II) seguindo o mesmo formato