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
│   ├── knowledge_base/            ← Markdowns simulados para RAG (futuro)
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
- Modelo único com ~40 features: ambientais (clima, precipitação), geográficas (solo, distância água, declividade), operacionais (velocidade, vibração, temp motor, horas), equipamento (tipo, idade, histórico sinistros), **operador** (velocidade acima recomendada, eventos bruscos, operações noturnas, score histórico), **manutenção** (dias/horas desde manutenção, atraso relativo)
- SHAP decompõe cada predição nos top fatores contribuintes — e por grupo de features, permitindo exibir contribuição por categoria no app (ex: "dos 74 pontos, 45 vêm do ambiente, 18 do operador e 11 da manutenção")
- Dataset simulado com ~5.000 registros, ~40 colunas para MVP
- MLflow registra cada treinamento (params, métricas, artefatos)
- Fórmula de score usa pesos calibrados (score_base + 11 interações + risco_acumulado + ruído) — detalhes em `docs/data schema.md` seção 4
- O XGBoost aprende a fórmula a partir do dataset; em produção quem calcula o score é o modelo, não a fórmula
- Quatro componentes expandidos incorporados ao escopo — ver seção "Componentes expandidos"

## Dataset

- **Localização:** `data/dataset_safefield.parquet` (primário) e `data/dataset_safefield.csv`
- **Registros:** 5.000 avaliações de risco de ~200 equipamentos ao longo de 2025
- **Colunas:** ~40 (identificação, ambientais, geográficas, operacionais, equipamento, operador, manutenção, metadados RAG, target)
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

**Fase 1 — Fundação e Dados (Semanas 1–2) ✅ CONCLUÍDA**
- Sprint 1 documentação e estrutura do repositório
- Dataset v1 (24 colunas) + EDA + testes (89 passando)

**Fase 2 — Dataset Expandido e Modelo (Semanas 3–7)**
- Expandir dataset com features de operador e manutenção (~40 colunas)
- Atualizar testes e EDA
- Treinar e validar XGBoost com dataset completo
- SHAP para explicabilidade (decomposição por grupo de features)
- MLflow para rastreabilidade
- Construir base de conhecimento simulada (Markdowns para RAG)

**Fase 3 — Backend e API (Semanas 8–11)**
- API FastAPI (endpoints de score, alertas, histórico, /explain RAG)
- Integração Open-Meteo + IBGE shapefiles
- Implementação do RAG (LlamaIndex/LangChain + LLM)
- Testes unitários e de integração do backend

**Fase 4 — App Móvel e Dashboard (Semanas 12–16)**
- App mobile (telas de login, dashboard de risco, alertas, histórico, perfil operador)
- Integração app ↔ backend (API REST)
- Integração app ↔ IoT via BLE
- Dashboard Streamlit (visão Sompo + simulador de cenários + UBI)

**Fase 5 — UBI e Polimento (Semanas 17–20)**
- Implementação do UBI (índice histórico + simulação de precificação)
- Simulador de cenários no Streamlit
- Refinamento de UX
- Testes de cenários realistas

**Fase 6 — Apresentação e Entrega (Semanas 21–23)**
- Documentação final
- Gravação do vídeo de apresentação
- Preparação da demo funcional
- Buffer para ajustes

**Entrega final: 15/09/2026**

## Estado atual

**Fase atual:** Fase 2 — Dataset Expandido e Modelo (Semanas 3–7)

**Concluído (Fase 1):**
- Schema do dataset definido e documentado (`docs/data schema.md`)
- Script de geração do dataset simulado (`scripts/generate_dataset.py`)
- Dataset v1 gerado: 5.000 registros, 24 colunas, distribuição 40/35/25 (baixo/medio/alto)
- Notebook de análise exploratória (`notebooks/01_eda.ipynb`)
- Suíte de testes: 89 testes passando (50 validação do dataset + 39 validação do script)
- Escopo expandido definido: 4 componentes novos especificados e documentados

**Próximo passo imediato (Fase 2):**
- **Expandir dataset:** adicionar features de operador e manutenção (~40 colunas total)
- Atualizar script de geração, testes e EDA para o dataset v2
- Treinar e validar modelo XGBoost com dataset completo
- Implementar explicabilidade com SHAP (decomposição por grupo)
- Configurar MLflow para rastreabilidade
- Construir base de conhecimento simulada (Markdowns para RAG)

## Componentes expandidos

Quatro componentes foram incorporados ao escopo na transição para a Fase 2:

1. **Perfil de risco do operador** — features comportamentais (velocidade acima do recomendado, eventos bruscos, operações noturnas, score histórico) entram no mesmo modelo XGBoost; SHAP decompõe contribuição por grupo de features.
2. **RAG com base de conhecimento simulada** — top fatores SHAP acionam busca em manuais técnicos simulados (Markdown em ) e geram recomendações em linguagem natural via LLM. Implementado **após** o treinamento do XGBoost.
3. **Manutenção preventiva vs. fabricante** — cruza manutenção declarada pelo operador com intervalos recomendados pelo fabricante;  entra como feature de risco no modelo.
4. **Usage-Based Insurance e simulador** — índice de risco histórico por equipamento/operador para precificação dinâmica simulada + interface Streamlit com sliders. Implementado **após** modelo e API.

> Priorização: features de operador e manutenção entram no dataset agora (Fase 2). RAG, UBI e simulador são implementados nas fases 3–5.

## Referências

- Enunciado do Challenge: `docs/references/challenge_sompo.txt`
- Apresentação institucional Sompo: `docs/references/apresentacao_sompo.pdf`
- Documentação de hardware: `docs/references/hardware_iot.txt`
- Artigo Akita (metodologia IA): `docs/references/akita_ia.pdf`


## Fluxo de trabalho com Git

### Regra principal

Ninguém commita direto na `main`. Toda alteração entra via Pull Request.

### Passo a passo

#### 1. Atualizar a main local antes de começar qualquer tarefa

```bash
git checkout main
git pull
```

#### 2. Criar a branch a partir da main atualizada

```bash
git checkout -b feature/expandir-dataset
```

#### 3. Trabalhar normalmente — commitar quantas vezes precisar

```bash
git add .
git commit -m "data(dataset): adicionar features de operador"
git add .
git commit -m "data(dataset): adicionar features de manutenção"
```

#### 4. Subir a branch pro GitHub

```bash
git push -u origin feature/expandir-dataset
```

#### 5. Abrir o PR no GitHub

- Entrar no repositório no navegador
- O GitHub mostra um banner "Compare & pull request" — clicar nele
- Escrever título e descrição do que foi feito
- Atribuir o colega como reviewer
- Clicar em "Create pull request"

#### 6. Revisão e merge

- O colega revisa, comenta se precisar
- Quando aprovado, clicar em "Merge pull request" → "Confirm merge"
- Deletar a branch remota (o GitHub oferece o botão)

#### 7. Voltar pra main local e atualizar

```bash
git checkout main
git pull
git branch -d feature/expandir-dataset
```

O `git branch -d` deleta a branch local que já foi mergeada. Aí começa o ciclo de novo pra próxima tarefa.

### Convenção de nomes de branch

```
feature/nome-da-tarefa    → funcionalidade nova
fix/nome-do-bug           → correção
docs/nome-do-doc          → documentação
data/nome-do-dataset      → datasets e dados
hw/nome-do-componente     → firmware/hardware
```

### Convenção de commits (Conventional Commits)

Formato: `tipo(escopo): descrição curta`

Tipos: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `data`, `hw`

## Como Rodar o Projeto

### 1. Clonar o repositório

```bash
git clone <url-do-repositório>
cd Sompo
```

### 2. Criar e ativar o ambiente virtual

**Windows:**
```bash
python -m venv .venv
.venv\Scripts\activate
```

**Mac/Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar dependências

```bash
pip install pandas numpy pyarrow pytest matplotlib seaborn jupyter
```

### 4. Gerar o dataset simulado

```bash
python scripts/generate_dataset.py
```

O script cria `data/dataset_safefield.parquet` e `data/dataset_safefield.csv` (~5.000 registros).

### 5. Rodar os testes

```bash
pytest tests/ -v
```

Saída esperada: 89 testes passando.

### 6. Abrir o notebook de EDA

```bash
jupyter notebook
```

Abra `notebooks/01_eda.ipynb` no navegador.

---