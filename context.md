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
5. **Interfaces:** app móvel (operador/gestor) + dashboard React (Sompo/analistas)

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
| Dashboard | React 19 + TypeScript + Vite + Tailwind CSS v4 |
| Banco de dados | Supabase (PostgreSQL) |
| Deploy | Vercel, Railway ou Render |

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
│   ├── api/                ← FastAPI (routers, schemas, endpoints) — Sprint 3
│   ├── ml/
│   │   ├── train.py            ← treinamento XGBoost + pré-processamento
│   │   ├── shap_explainer.py   ← explicabilidade SHAP (6 grupos de features)
│   │   └── mlflow_tracking.py  ← rastreabilidade de runs de treinamento
│   ├── db/
│   │   ├── schema.sql          ← schema das 4 tabelas PostgreSQL
│   │   └── supabase_client.py  ← cliente Supabase encapsulado
│   ├── core/               ← config, database, auth, utils — Sprint 3
│   └── requirements.txt
├── mobile/                 ← app React Native ou Flutter — Sprint 4
├── dashboard/              ← React 19 + TS + Vite + Tailwind v4 (visão Sompo)
│   ├── src/
│   │   ├── App.tsx              ← roteamento por persona + nav lateral
│   │   ├── main.tsx · types.ts · index.css (tema dark, Tailwind v4)
│   │   ├── lib/supabase.ts      ← cliente Supabase (VITE_SUPABASE_*)
│   │   ├── data/
│   │   │   ├── api.ts           ← fetch + agregação (KPIs, SHAP, histórico)
│   │   │   └── mock.ts          ← dados mockados (telas não integradas)
│   │   ├── components/          ← ComingSoon (overlay), Icons, SideNav, TopBar, shared
│   │   └── pages/
│   │       ├── sompo/           ← Overview, Ranking, Detail (dados reais Supabase)
│   │       │                       Simulator, UBI, Reports (overlay "Em breve")
│   │       ├── broker/          ← Corretor (overlay "Em breve")
│   │       └── technician/      ← Técnico (overlay "Em breve")
│   ├── .env.local              ← credenciais VITE_* (não commitado, git-ignored)
│   ├── package.json · vite.config.ts · tsconfig*.json
│   └── README.md
├── firmware/               ← ESP32 C++/Arduino
├── data/
│   ├── dataset_safefield.parquet  ← dataset primário (5.000 registros, 37 colunas)
│   ├── dataset_safefield.csv      ← cópia visual/debug
│   ├── knowledge_base/            ← Markdowns simulados para RAG — Sprint 3
│   └── eda_01_target.png … eda_10_temporal.png  ← 10 gráficos do EDA v2
├── models/
│   ├── xgboost_model.joblib   ← modelo treinado (XGBoost regressor)
│   ├── encoder.joblib          ← OrdinalEncoder para variáveis categóricas
│   ├── features.json           ← lista das 30 features usadas no modelo
│   ├── metrics.json            ← MAE 4.72, RMSE 6.08, R² 0.9466, acc 88.3%
│   └── shap_values.npy         ← SHAP values pré-calculados (500 amostras)
├── mlruns/                 ← experimentos MLflow (experimento safefield-xgboost)
├── notebooks/
│   ├── 01_eda.ipynb        ← EDA dataset v2 (37 colunas, 10 figuras exportadas)
│   └── 02_treinamento.ipynb ← pipeline completo de treinamento documentado (11 seções)
├── scripts/
│   ├── generate_dataset.py         ← geração do dataset simulado (seed 42, reprodutível)
│   ├── generate_notebook_01_v2.py  ← gerador do notebook de EDA v2
│   ├── generate_notebook_02.py     ← gerador do notebook de treinamento
│   ├── seed_supabase.py            ← seed: equipamentos, operadores, avaliacoes
│   └── populate_predictions.py     ← popula predicoes com modelo + SHAP
└── tests/
    ├── test_dataset.py          ← 70 testes: schema, ranges, regras, distribuições
    ├── test_generate_dataset.py ← 63 testes: funções, fórmula, interações, operador, manutenção
    ├── test_model.py            ← 26 testes: artefatos, predições, métricas, encoding, faixas
    ├── test_shap.py             ← 38 testes: grupos, SHAP values, contribuições, artefatos
    ├── test_mlflow.py           ← 25 testes: registro, runs, parâmetros, métricas, fallback
    ├── test_supabase.py         ← 18 testes: conexão, contagens, integridade, distribuição
    └── test_predicoes.py        ← 11 testes: predições, SHAP JSON, correlação
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
- **30 features no modelo** (subset de 37 colunas do dataset — excluídas: IDs, timestamp, targets e metadados RAG): ambientais (clima, precipitação), geográficas (solo, distância água, declividade), operacionais (velocidade, vibração, temp motor, horas), equipamento (tipo, idade, histórico sinistros), **operador** (velocidade acima recomendada, eventos bruscos, operações noturnas, score histórico), **manutenção** (dias/horas desde manutenção, atraso relativo)
- **Métricas reais** (test set 1.000 registros): MAE 4.72 · RMSE 6.08 · R² 0.9466 · Acurácia faixas 88.3%
- **SHAP** decompõe cada predição nos top fatores contribuintes e por grupo de features, permitindo exibir "dos 74 pontos, 45 vêm do ambiente, 18 do operador e 11 da manutenção". Top driver global: `historico_sinistros` (mean |SHAP| = 18.58)
- **MLflow** registra cada treinamento: experimento `safefield-xgboost`, 9 parâmetros, 7 métricas, 10 artefatos por run. Graceful fallback: treino continua se MLflow falhar
- Fórmula de score usa pesos calibrados (score_base + 11 interações + risco_acumulado + ruído) — detalhes em `docs/data schema.md` seção 4
- O XGBoost aprende a fórmula a partir do dataset; em produção quem calcula o score é o modelo, não a fórmula
- Quatro componentes expandidos incorporados ao escopo — ver seção "Componentes expandidos"

## Dataset

- **Localização:** `data/dataset_safefield.parquet` (primário) e `data/dataset_safefield.csv`
- **Registros:** 5.000 avaliações de risco de ~200 equipamentos ao longo de 2025
- **Colunas:** 37 (identificação, ambientais, geográficas, operacionais, equipamento, operador, manutenção, metadados RAG, target)
- **Target:** `risco_score` (0–100) + `faixa_risco` (baixo/medio/alto)
- **Distribuição:** ~40% baixo, ~35% médio, ~25% alto
- **Spec completa:** `docs/data schema.md` (schema, regras de consistência, fórmula de score)
- **Geração:** `python scripts/generate_dataset.py` (seed 42, reprodutível)
- **Nulls esperados:** `vibracao_g` (~21%) e `temperatura_motor` (~72%) — campos IoT opcionais

## Testes

- **Framework:** pytest
- **Executar:** `pytest tests/ -v`
- **Total:** 251 testes (226 passando + 25 MLflow requerem módulo instalado)
- `tests/test_dataset.py` — 70 testes validando o dataset gerado (schema, ranges, regras de consistência, distribuições)
- `tests/test_generate_dataset.py` — 63 testes validando o script de geração (funções, fórmula, interações, operador, manutenção)
- `tests/test_model.py` — 26 testes validando o modelo treinado (artefatos, predições, métricas, encoding, faixas)
- `tests/test_shap.py` — 38 testes validando a explicabilidade SHAP (grupos, values, contribuições, artefatos)
- `tests/test_mlflow.py` — 25 testes validando o tracking MLflow (registro, runs, parâmetros, métricas, fallback)
- `tests/test_supabase.py` — 18 testes validando o Supabase (conexão, contagens, integridade, distribuição, nulls, indexes)
- `tests/test_predicoes.py` — 11 testes validando as predições (contagem, SHAP JSON, correlação, distribuição)
- **Convenção:** sempre criar testes junto com código novo (TDD quando possível)

## Dependências Python

Instalar na venv do projeto:

```bash
pip install -r backend/requirements.txt
```

Dependências completas do backend em `backend/requirements.txt`.

Para os scripts de seed do Supabase: `supabase` e `python-dotenv` (já incluídos no requirements.txt). Credenciais em `.env` (não commitado): `SUPABASE_URL` e `SUPABASE_KEY`.

## Dependências Frontend (dashboard)

Stack: **React 19 + TypeScript + Vite + Tailwind CSS v4**.

Instalar e rodar:

```bash
cd dashboard
npm install
npm run dev        # http://localhost:5173 (cai para a próxima porta livre, ex.: 5175)
```

Principais dependências (`dashboard/package.json`):

- `@supabase/supabase-js` — cliente do banco (consultas das telas integradas)
- `recharts` — gráficos
- `lucide-react` — ícones
- `react` / `react-dom` / `react-router-dom`
- dev: `vite`, `@vitejs/plugin-react`, `tailwindcss` (v4) + `@tailwindcss/vite`, `typescript`, `eslint`

Credenciais do frontend em `dashboard/.env.local` (não commitado, git-ignored via `*.local`): `VITE_SUPABASE_URL` e `VITE_SUPABASE_KEY`. O Vite só expõe variáveis com prefixo `VITE_`.

## Metodologia de trabalho com IA

Seguimos o princípio de pair programming com IA (driver/navigator), conforme artigo do Akita. A IA não programa sozinha — o desenvolvedor mantém o controle arquitetural e a IA executa sob supervisão. Features novas representam ~37% dos commits; testes, refactoring, docs e infra compõem os outros 63%.

Fluxo de trabalho atual: planejamento e decisões arquiteturais → specs e prompts claros → execução no VSCode → testes automatizados validando cada entrega.

## Equipe

| Nome | Frente |
|---|---|
| Guilherme (Avila) | Backend, ML, arquitetura geral |
| Kainan | App móvel, integração BLE/IoT, dashboard |

## Fases do projeto

**Sprint 1 — Fundação e Dados ✅ CONCLUÍDA**
- Documentação e estrutura do repositório
- Dataset v1 (24 colunas) + EDA + 89 testes passando

**Sprint 2 — Modelo e Explicabilidade (entrega: 04/06/2026)**

Concluído:
- Dataset expandido para 37 colunas (operador, manutenção, metadados RAG)
- Modelo XGBoost treinado e validado: MAE 4.72, R² 0.9466, acc faixas 88.3%
- SHAP para explicabilidade por grupo de features (`backend/ml/shap_explainer.py`)
- MLflow para rastreabilidade (`backend/ml/mlflow_tracking.py`, experimento `safefield-xgboost`)
- Notebooks documentados: EDA v2 (`01_eda.ipynb`) + treinamento completo (`02_treinamento.ipynb`)
- Supabase (PostgreSQL): 4 tabelas com dados completos (equipamentos, operadores, avaliacoes, predicoes)
- Predições: score predito + top 5 fatores SHAP em JSONB + versão do modelo por avaliação
- 251 testes automatizados (226 passando)
- Dashboard React (visão Sompo): 3 telas integradas ao Supabase (Visão Geral, Ranking, Detalhe com SHAP); demais telas com overlay "Em breve"

Pendente:
- Diagrama de arquitetura consolidado
- README atualizado com tudo da Sprint 2
- Vídeo de apresentação (até 5 min)

**Sprint 3 — Backend e API (a definir)**
- API FastAPI completa (endpoints de score, alertas, histórico, /explain)
- Implementação do RAG (LlamaIndex/LangChain + LLM)
- Base de conhecimento simulada (Markdowns para RAG)
- Integração Open-Meteo + IBGE shapefiles
- Testes de integração do backend

**Sprint 4 — App Móvel e UBI (a definir)**
- App mobile (telas de operador e gestor)
- Integração app ↔ backend e app ↔ IoT via BLE
- UBI + simulador de cenários no dashboard React

**Entrega final: 15/09/2026**
- Polimento de UX
- Documentação final
- Vídeo de apresentação final
- Demo funcional

## Estado atual

**Sprint atual:** Sprint 2 — finalização (entrega 04/06/2026)

**Concluído (Sprint 1):**
- Schema do dataset definido e documentado (`docs/data schema.md`)
- Script de geração do dataset simulado (`scripts/generate_dataset.py`)
- Dataset v1 gerado: 5.000 registros, 24 colunas, distribuição 40/35/25 (baixo/medio/alto)
- Notebook de análise exploratória v1 (`notebooks/01_eda.ipynb`)
- Suíte de testes: 89 testes passando (50 validação do dataset + 39 validação do script)
- Escopo expandido definido: 4 componentes novos especificados e documentados

**Concluído (Sprint 2 — até agora):**
- Dataset expandido para 37 colunas com features de operador e manutenção
- Modelo XGBoost treinado: MAE 4.72, RMSE 6.08, R² 0.9466, acurácia faixas 88.3%
- SHAP implementado: decomposição por 6 grupos, top driver `historico_sinistros` (18.58)
- MLflow integrado: experimento `safefield-xgboost` com 9 params, 7 métricas, 10 artefatos
- EDA reescrito para dataset v2 (10 figuras exportadas)
- Notebook de treinamento criado (11 seções documentando todo o pipeline)
- Supabase (PostgreSQL): 4 tabelas — equipamentos (200), operadores (80), avaliacoes (5000), predicoes (5000)
- Predições: score predito + top 5 fatores SHAP em JSONB + versão do modelo
- 251 testes automatizados (226 passando)
- Dashboard React (visão Sompo): React 19 + TypeScript + Vite + Tailwind v4. 3 telas integradas ao Supabase com dados reais — Visão Geral (KPIs, gráficos, alertas), Ranking (200 equipamentos com filtros e busca) e Detalhe do Equipamento (decomposição SHAP por grupo, top fatores, manutenção, histórico). Telas ainda não integradas (Simulador, UBI, Relatórios, Corretor, Técnico) exibem overlay "Em breve". Rodar com `cd dashboard && npm run dev`.

**Próximo passo imediato (Sprint 2 — pendente):**
- Diagrama de arquitetura atualizado
- README final da Sprint 2
- Vídeo de apresentação (até 5 min)

## Componentes expandidos

Quatro componentes foram incorporados ao escopo na transição para a Sprint 2:

1. **Perfil de risco do operador** — features comportamentais (velocidade acima do recomendado, eventos bruscos, operações noturnas, score histórico) entram no mesmo modelo XGBoost; SHAP decompõe contribuição por grupo de features.
2. **RAG com base de conhecimento simulada** — top fatores SHAP acionam busca em manuais técnicos simulados (Markdown em `data/knowledge_base/`) e geram recomendações em linguagem natural via LLM. Implementado na Sprint 3.
3. **Manutenção preventiva vs. fabricante** — cruza manutenção declarada pelo operador com intervalos recomendados pelo fabricante; entra como feature de risco no modelo.
4. **Usage-Based Insurance e simulador** — índice de risco histórico por equipamento/operador para precificação dinâmica simulada + interface React com sliders. Implementado na Sprint 4.

> Priorização: features de operador e manutenção estão no dataset (Sprint 2 concluído). RAG, UBI e simulador são implementados nas Sprints 3–4.

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
pip install -r backend/requirements.txt
```

### 4. Gerar o dataset simulado

```bash
python scripts/generate_dataset.py
```

O script cria `data/dataset_safefield.parquet` e `data/dataset_safefield.csv` (~5.000 registros, 37 colunas).

### 5. Treinar o modelo

```bash
python backend/ml/train.py
```

Treina o XGBoost e salva artefatos em `models/`. Exibe métricas e critérios de aceitação.

### 6. Rodar os testes

```bash
pytest tests/ -v
```

Saída esperada: 222 testes passando.

### 7. Abrir os notebooks

```bash
jupyter notebook
```

- `notebooks/01_eda.ipynb` — análise exploratória do dataset v2
- `notebooks/02_treinamento.ipynb` — pipeline completo de treinamento

---