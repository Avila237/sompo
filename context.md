# CLAUDE.md — SafeField

## O que é este projeto

Plataforma de análise preditiva de riscos para equipamentos agrícolas, desenvolvida como Challenge FIAP + Sompo Seguros. A Sompo é a 3ª maior seguradora de máquinas e implementos agrícolas no Brasil, com produtos Benfeitorias e Penhor Rural que cobrem colisão, tombamento, transporte, operação próxima de água, furto e incêndio.

O sistema cruza dados ambientais, operacionais e geográficos para gerar um score de risco (0–100) por equipamento, com alertas preventivos e explicabilidade via SHAP.

## Arquitetura

Cinco camadas:
1. **Fontes de dados:** app móvel (GPS, inputs), IoT ESP32 (MPU-6050 + DS18B20 via BLE), APIs externas (Open-Meteo, IBGE shapefiles)
2. **Ingestão:** app recebe IoT via BLE, envia tudo ao backend. Backend enriquece com clima e geodados
3. **Motor de IA:** XGBoost (regressão, score 0–100) + SHAP (explicabilidade) + MLflow (auditoria)
4. **API:** FastAPI com JWT, endpoints de score, alertas, histórico, relatórios
5. **Interfaces:** app móvel (operador/gestor) + dashboard Streamlit (Sompo/analistas)

**Decisão arquitetural central:** o app móvel é o centro — funciona sem IoT (GPS + acelerômetro do celular). O IoT ESP32 é complemento opcional para equipamentos modernos.

## Stack

| Componente | Tecnologia |
|---|---|
| Firmware IoT | ESP32 DOIT DevKit — C++ / Arduino IDE |
| Sensores | MPU-6050 GY-521 (accel+gyro, I2C), DS18B20 (temp, OneWire) |
| Regulador | LM2596 (12/24V do veículo → 5V pro ESP32) |
| App Móvel | React Native ou Flutter (a definir) |
| Backend | FastAPI (Python) |
| ML | XGBoost + SHAP |
| Rastreabilidade | MLflow |
| Dados externos | Open-Meteo (clima), IBGE shapefiles (geo) |
| Dashboard | Streamlit |
| Deploy | Railway ou` Render |

## Estrutura de pastas

```
/
├── README.md
├── context.md              ← guia do projeto para o Claude Code
├── .gitignore
├── .env.example
├── docs/
│   ├── data schema.md      ← schema do dataset, fórmula de score, regras
│   └── references/         ← materiais externos (PDFs, enunciado, etc.)
├── backend/
│   ├── api/                ← FastAPI (routers, schemas, endpoints)
│   ├── ml/                 ← treinamento, SHAP, MLflow
│   ├── core/               ← config, database, auth, utils
│   └── requirements.txt
├── mobile/                 ← app React Native ou Flutter
├── dashboard/              ← Streamlit
├── firmware/               ← ESP32 C++/Arduino
├── data/
│   ├── dataset_safefield.parquet  ← dataset primário (5.000 registros)
│   ├── dataset_safefield.csv      ← cópia visual/debug
│   └── eda_01_target.png … eda_08_geo.png  ← gráficos gerados no EDA
├── models/                 ← modelos serializados (.pkl, .joblib)
├── notebooks/
│   └── 01_eda.ipynb        ← análise exploratória do dataset
├── scripts/
│   └── generate_dataset.py ← geração do dataset simulado (seed 42)
└── tests/
    ├── test_dataset.py     ← 50 testes: schema, ranges, regras, distribuições
    └── test_generate_dataset.py  ← 39 testes: funções, fórmula, interações
```

## Convenções

### Commits (Conventional Commits)

Formato: `tipo(escopo): descrição curta`

- `feat` — nova funcionalidade
- `fix` — correção de bug
- `docs` — documentação
- `style` — formatação sem mudança de lógica
- `refactor` — refatoração sem mudar comportamento
- `test` — testes
- `chore` — configs, deps, CI
- `data` — datasets, simulações
- `hw` — firmware/hardware ESP32

Escopo opcional. Exemplo: `feat(api): adicionar endpoint de risk score`, `hw(esp32): integrar MPU-6050`

### Código

- Backend em Python, seguir PEP 8
- Firmware em C++, estilo Arduino
- Documentação e comentários em português

## Personas

1. **Sompo (seguradora):** score explicável, trilha de auditoria, visão agregada por região/equipamento
2. **Cliente segurado (produtor rural):** painel de risco, alertas antes de operações críticas, recomendações práticas
3. **Usuários finais:** operador (alertas diretos no celular), gestor de frota (ranking de risco), técnico de manutenção (padrões pré-dano), corretor (explicação objetiva de fatores)

## Hardware IoT — resumo rápido

- ESP32 → MPU-6050 via I2C (GPIO 21 SDA, GPIO 22 SCL)
- ESP32 → DS18B20 via OneWire (GPIO 4, pull-up 4.7kΩ obrigatório)
- Alimentação: USB/powerbank em bancada, LM2596 no veículo
- Transmissão: JSON via BLE a cada 1s com ax/ay/az, gx/gy/gz, mag, incl, impact, temp_c
- O MPU-6050 substituiu o MMA8452 (6 eixos vs 3, 16 bits vs 12, mais barato)

## Modelo preditivo

- XGBoost regressão → score 0–100 → faixas: baixo (0–33), médio (34–66), alto (67–100)
- Features: ambientais (clima, precipitação), geográficas (solo, distância água, declividade), operacionais (velocidade, vibração, temp motor, horas), equipamento (tipo, idade, histórico sinistros)
- SHAP decompõe cada predição nos top fatores contribuintes
- Dataset simulado com ~5.000 registros para MVP
- MLflow registra cada treinamento (params, métricas, artefatos)
- Fórmula de score usa pesos calibrados (score_base + 8 interações + risco_acumulado + ruído) — detalhes em `docs/data schema.md` seção 4
- O XGBoost aprende a fórmula a partir do dataset; em produção quem calcula o score é o modelo, não a fórmula

## Dataset

- **Localização:** `data/dataset_safefield.parquet` (primário) e `data/dataset_safefield.csv`
- **Registros:** 5.000 avaliações de risco de ~200 equipamentos ao longo de 2025
- **Colunas:** 24 (identificação, ambientais, geográficas, operacionais, equipamento, target)
- **Target:** `risco_score` (0–100) + `faixa_risco` (baixo/medio/alto)
- **Distribuição:** ~40% baixo, ~35% médio, ~25% alto
- **Spec completa:** `docs/data schema.md` (schema, regras de consistência, fórmula de score)
- **Geração:** `python scripts/generate_dataset.py` (seed 42, reprodutível)
- **Nulls esperados:** `vibracao_g` (~21%) e `temperatura_motor` (~72%) — campos IoT opcionais

## Testes

- **Framework:** pytest
- **Executar:** `pytest tests/ -v`
- **Total:** 89 testes (todos passando)
- `tests/test_dataset.py` — 50 testes validando o dataset gerado (schema, ranges, regras, distribuições)
- `tests/test_generate_dataset.py` — 39 testes validando o script de geração (funções, fórmula, interações, reprodutibilidade)
- **Convenção:** sempre criar testes junto com código novo (TDD quando possível)

## Dependências Python

Instalar na venv do projeto:

```bash
pip install pandas numpy pyarrow pytest matplotlib seaborn jupyter
```

Dependências completas do backend em `backend/requirements.txt`.

## Metodologia de trabalho com IA

Seguimos o princípio de pair programming com IA (driver/navigator), conforme artigo do Akita. A IA não programa sozinha — o desenvolvedor mantém o controle arquitetural e a IA executa sob supervisão. Features novas representam ~37% dos commits; testes, refactoring, docs e infra compõem os outros 63%.

Fluxo de trabalho atual: planejamento e decisões arquiteturais n → specs e prompts claros → execução no (VSCode) → testes automatizados validando cada entrega.

## Equipe

| Nome | Frente |
|---|---|
| Guilherme (Avila) | Backend, ML, arquitetura geral |
| Kainan | App móvel, integração BLE/IoT, dashboard |

## Fases do projeto

1. **Semanas 1–2:** Fundação e dados (Sprint 1 — esta entrega)
2. **Semanas 3–5:** Modelo e backend
3. **Semanas 6–8:** App móvel e integração
4. **Semanas 9–10:** Polimento e apresentação
5. **Semanas 11–12:** Buffer

## Estado atual

**Fase atual:** Fase 2 — Modelo e Backend (Semanas 3–5)

**Concluído na Fase 2:**
- Schema do dataset definido e documentado (`docs/data schema.md`)
- Script de geração do dataset simulado (`scripts/generate_dataset.py`)
- Dataset gerado: 5.000 registros, 24 colunas, distribuição 40/35/25 (baixo/medio/alto)
- Notebook de análise exploratória (`notebooks/01_eda.ipynb`)
- Suíte de testes: 89 testes passando (50 validação do dataset + 39 validação do script)

**Próximos passos da Fase 2:**
- Treinar e validar modelo XGBoost
- Implementar explicabilidade com SHAP
- Configurar MLflow para rastreabilidade
- Desenvolver API FastAPI (endpoints de score, alertas, histórico)
- Integração com Open-Meteo e IBGE shapefiles

## Referências

- Enunciado do Challenge: `docs/references/challenge_sompo.txt`
- Apresentação institucional Sompo: `docs/references/apresentacao_sompo.pdf`
- Documentação de hardware: `docs/references/hardware_iot.txt`
- Artigo Akita (metodologia IA): `docs/references/akita_ia.pdf`
