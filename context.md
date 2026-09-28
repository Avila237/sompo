# CLAUDE.md — SafeField

## O que é este projeto

Plataforma de análise preditiva de riscos para equipamentos agrícolas, desenvolvida como Challenge FIAP + Sompo Seguros. A Sompo é a 3ª maior seguradora de máquinas e implementos agrícolas no Brasil, com produtos Benfeitorias e Penhor Rural que cobrem colisão, tombamento, transporte, operação próxima de água, furto e incêndio.

O sistema recebe leituras de campo, enriquece com clima, gera um score de risco (0–100) por equipamento com XGBoost, explica o score com SHAP e expõe tudo por uma API autenticada consumida por um dashboard React.

## Onde está cada verdade

Este arquivo descreve o que é estável. Números e estado mudam; leia-os na fonte, nunca copie para cá.

| Pergunta | Fonte |
|---|---|
| O que a entrega atual exige e o estado de cada requisito | `docs/spec-sprint-04.md` |
| O que está em andamento, com quem, bloqueado por quê | Linear, projeto SafeField, milestone **SPRINT 4** |
| Métricas atuais do modelo | `models/metrics.json` |
| Contrato da API (rotas, campos, erros) | `docs/contrato-api.md` · `docs/openapi.json` |
| Schema do dataset, regras de consistência, fórmula de score | `docs/data schema.md` |
| Como rodar do zero | `README.md`, seção "Como rodar o projeto" |
| Onde a sessão anterior parou | `.claude/handoff.md` |
| Enunciados da FIAP | `docs/references/` |

## Arquitetura

**Invariante central: nenhum cliente fala com o banco.** A API é a única porta. O browser não carrega chave de banco; o backend acessa o Supabase com `service_role`, e a RLS está ativa sem policy para `anon`.

```
simulador ──POST /avaliacoes──▶ API FastAPI ──service_role──▶ Supabase (PostgreSQL + RLS)
dashboard ──GET  /* (Bearer)──▶     │
                                    ├── Open-Meteo (clima; fallback: payload; 502 se faltar os dois)
                                    └── XGBoost + SHAP (carregados uma vez no startup)
```

Fluxo de `POST /avaliacoes` (`backend/services/scoring.py`):

1. JWT
2. Validação Pydantic (`extra="forbid"`)
3. Busca do equipamento e do operador no cadastro (404 se não existem)
4. Clima via Open-Meteo, com o payload como fallback
5. Derivação da manutenção (Regra 14)
6. Predição e SHAP
7. Gravação da avaliação
8. Gravação da predição (se falhar, a avaliação é removida)
9. Auditoria

A predição acontece **antes** de gravar.

### Camadas e direção de dependência

```
api ──▶ services ──▶ ml
              └────▶ db
     core ◀── todos          (core não importa ninguém)
```

- `backend/api/` — app, rotas, schemas Pydantic, dependências de auth
- `backend/services/` — orquestração: `scoring`, `consultas`, `clima`, `auditoria`
- `backend/ml/` — `preprocess` (função única de features), `predictor` (carrega artefatos), `shap_explainer`, `train`, `mlflow_tracking`
- `backend/db/` — `repository` (acesso ao Supabase), `supabase_client` (usado pelos scripts de seed)
- `backend/core/` — `config` (lê o ambiente), `security` (JWT), `logging` (request_id via ContextVar), `exceptions`

A direção nunca se inverte. Hoje há desvios conhecidos: `api/main.py` e `api/routers/health.py` importam `ml` direto. Estão registrados na task S4-21.

## Stack

| Componente | Tecnologia | Estado |
|---|---|---|
| Backend / API | FastAPI + Uvicorn, Python **3.13** | em uso |
| Validação | Pydantic 2 | em uso |
| Autenticação | JWT próprio (`python-jose`), perfis `operador` · `gestor` · `analista` | em uso |
| Modelo | XGBoost (regressão) + SHAP | em uso |
| Rastreabilidade ML | MLflow, experimento `safefield-xgboost`, store local `mlruns/` | em uso |
| Banco | Supabase (PostgreSQL + RLS), projeto `sompo` | em uso |
| Clima | Open-Meteo via `requests` | em uso |
| Dashboard | React 19 + TypeScript + Vite + Tailwind CSS v4, sem outras dependências de runtime | em uso |
| Telemetria | `scripts/simulate_telemetry.py` | em uso |
| Firmware IoT | ESP32 DOIT DevKit, MPU-6050, DS18B20, via BLE | especificado, fora de escopo |
| App móvel | — | fora de escopo |
| Deploy | — | fora de escopo; execução local |

## Estrutura de pastas

```
/
├── README.md                ← documento de entrega (lido pelo tutor)
├── context.md               ← este arquivo
├── .env.example             ← variáveis do backend (.env nunca vai para o Git)
├── pytest.ini               ← marker 'seed' excluído por padrão
├── backend/
│   ├── api/                 main.py · deps.py · schemas.py · routers/{auth,avaliacoes,consultas,health}.py
│   ├── services/            scoring.py · consultas.py · clima.py · auditoria.py
│   ├── ml/                  preprocess.py · predictor.py · shap_explainer.py · train.py · mlflow_tracking.py
│   ├── db/                  repository.py · supabase_client.py · schema.sql (⚠️ ver Armadilhas)
│   ├── core/                config.py · security.py · logging.py · exceptions.py
│   └── requirements.txt
├── supabase/migrations/     ← toda mudança de estrutura do banco entra aqui
├── dashboard/
│   ├── .env.example         ← só VITE_API_BASE_URL
│   └── src/
│       ├── App.tsx · main.tsx · types.ts · index.css
│       ├── lib/             apiClient.ts (HTTP + ApiError) · auth.ts (sessão JWT em sessionStorage)
│       ├── data/            api.ts (chamadas e adaptação) · mock.ts (telas "Em breve" e utilitários de faixa)
│       ├── components/      Login · SideNav · TopBar · ComingSoon · Icons · shared
│       └── pages/           sompo/{Overview,Ranking,Detail} consomem a API;
│                            sompo/{Simulator,UBI,Reports}, broker/, technician/ são mock sob "Em breve"
├── scripts/
│   ├── generate_dataset.py        ← dataset simulado (seed 42)
│   ├── simulate_telemetry.py      ← emite leituras contra a API
│   ├── seed_supabase.py           ← carga inicial do banco (⚠️ ver Armadilhas)
│   ├── populate_predictions.py    ← predições do seed; append-only, --reset para limpar
│   ├── demo.sh                    ← roteiro da demo (só Unix)
│   └── generate_notebook_*.py, patch_notebook.py  ← one-off, candidatos a remoção (S4-32)
├── models/                  features.json · metrics.json versionados; *.joblib gerados localmente
├── data/                    figuras EDA/SHAP versionadas; *.parquet e *.csv gerados localmente
├── notebooks/               01_eda.ipynb · 02_treinamento.ipynb
├── tests/                   test_api · test_dataset · test_generate_dataset · test_model ·
│                            test_shap · test_mlflow · test_supabase · test_predicoes
├── docs/
│   ├── spec-sprint-04.md    ← requisitos da entrega atual (normativa)
│   ├── spec-sprint-03.md · spec-implementacao-entrega-03.md  ← registro da Entrega 3
│   ├── contrato-api.md · openapi.json · data schema.md
│   └── references/          enunciados das sprints e hardware IoT
├── firmware/ · mobile/      ← vazios (fora de escopo)
└── .claude/handoff.md       ← único arquivo de .claude/ versionado
```

## Modelo preditivo

- XGBoost regressor → score 0–100 → faixa por `derive_faixa()` em `backend/ml/preprocess.py`: `≤33` baixo, `≤66` médio, acima disso alto.
- **30 features** na ordem de `models/features.json`: ambientais, geográficas, operacionais, equipamento, operador e manutenção.
- SHAP decompõe cada predição e agrega em 6 grupos, preservando o sinal. `predicoes.top_fatores_shap` guarda os top 5.
- Cada predição grava `modelo_versao`. O histórico de predições é append-only.
- O dataset é gerado por uma fórmula (`scripts/generate_dataset.py`); o XGBoost aprende a fórmula a partir do dado, e em produção quem calcula é o modelo.
- **Dívida D4:** `historico_sinistros` domina a explicação; operador e manutenção têm peso quase nulo. A recalibração (S4-17) está em standby por decisão: fica por último, se der tempo.

## Dataset

- `data/dataset_safefield.parquet`: 5.000 avaliações de 200 equipamentos e 80 operadores, 37 colunas. É gerado localmente, não versionado.
- Nulos esperados: `vibracao_g` e `temperatura_motor`, campos de IoT opcional.
- Spec completa em `docs/data schema.md`. A §4 (fórmula) diverge do código até a S4-05 ser concluída; na dúvida, vale o código.

## Testes

- `pytest tests/ -v`. O marker `seed` fica excluído por padrão; rode `pytest -m seed` logo após um seed.
- Dependências por arquivo:

  | Arquivo | Precisa de |
  |---|---|
  | `test_generate_dataset` | nada externo |
  | `test_dataset` | parquet local |
  | `test_model`, `test_shap`, `test_mlflow` | parquet + `.joblib` |
  | `test_api` | `.env` válido e `.joblib`; Supabase e Open-Meteo são mockados |
  | `test_supabase`, `test_predicoes` | Supabase real; são pulados sem `SUPABASE_URL`/`SUPABASE_KEY` |

- ⚠️ `test_shap` hoje sobrescreve `models/shap_values.npy` e `data/shap_*.png` versionados. Rode `git status` depois da suíte (corrigido em S4-11).
- Convenção: teste no mesmo passo da feature; teste de regressão antes do fix; nunca enfraquecer teste para passar.

## Configuração

- Backend: `.env` na raiz, a partir do `.env.example`. `backend/core/config.py` é a referência do que é lido. Obrigatórias:
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY` (aceita `SUPABASE_KEY` como fallback)
  - `JWT_SECRET_KEY`
  - `DEMO_USERS` (`usuario:senha:perfil,...`)
- Dashboard: `dashboard/.env.local` com `VITE_API_BASE_URL` apenas.
- ⚠️ O `.env.example` atual está incompleto (falta `DEMO_USERS`) e traz um segredo JWT placeholder utilizável. Corrigido em S4-07.
- `service_role` é superusuário do banco: só no servidor, nunca no frontend, nunca versionada.

## Armadilhas

| Estado | Neutralização |
|---|---|
| Vontade de rodar `backend/db/schema.sql` | **Não.** Começa com `DROP TABLE` e não contém a migration da E3. Toda mudança de estrutura vai em `supabase/migrations/`, aditiva e idempotente |
| `seed_supabase.py` manda rodar `schema.sql` primeiro | Mesmo caso. Não seguir até a S4-13 corrigir |
| Supabase não responde | O projeto pausa por inatividade. Reative no painel antes de diagnosticar código |
| Python 3.14 | `xgboost`/`shap`/`numpy` sem wheel. Use 3.13 |
| macOS: `libxgboost.dylib could not be loaded` | `brew install libomp` |
| Reexecutar `populate_predictions.py` | Duplica predições (sem unique em `avaliacao_id`). Não rodar até a S4-13 |
| `top_fatores_shap` com `group` vs `grupo` | O seed gravou `group`, a API grava `grupo`; `services/consultas.py` normaliza na leitura |
| Faixa perto de 33 ou 66 | Backend e front reclassificam sobre o valor arredondado e podem divergir da faixa gravada (S4-16) |

## Convenções

### Código
- Backend em Python, PEP 8. Identificadores e commits em inglês; comentários e documentação em português.
- Firmware em C++, estilo Arduino.

### Commits (Conventional Commits)

Formato `tipo(escopo): descrição curta`. Tipos:

| Tipo | Uso |
|---|---|
| `feat` | nova funcionalidade |
| `fix` | correção de bug |
| `docs` | documentação |
| `style` | formatação sem mudança de lógica |
| `refactor` | refatoração sem mudar comportamento |
| `test` | testes |
| `chore` | configs, deps, CI |
| `data` | datasets, simulações |
| `hw` | firmware/hardware ESP32 |

Exemplo: `feat(api): adicionar endpoint de risk score`.

### Git
- **Ninguém commita direto na `main`.** Toda alteração entra por Pull Request revisado pelo outro integrante.
- Branch a partir da `main` atualizada:
  - `feature/<tarefa>`
  - `fix/<bug>`
  - `docs/<doc>`
  - `data/<dataset>`
  - `hw/<componente>`
- Uma issue do Linear por unidade de trabalho; o nome da branch sugerido pelo Linear também serve.

## Personas

1. **Sompo (seguradora):** score explicável, trilha de auditoria, visão agregada por região, equipamento e operação.
2. **Cliente segurado (produtor rural):** painel de risco, alertas antes de operações críticas, recomendações práticas.
3. **Usuários finais:**
   - operador: alertas diretos;
   - gestor de frota: ranking de risco;
   - técnico de manutenção: padrões pré-dano;
   - corretor: explicação objetiva dos fatores.

## Hardware IoT (especificado, fora de escopo)

- ESP32 → MPU-6050 via I2C (GPIO 21 SDA, GPIO 22 SCL); DS18B20 via OneWire (GPIO 4, pull-up 4,7 kΩ obrigatório).
- Alimentação por USB/powerbank em bancada, LM2596 no veículo.
- JSON via BLE a cada 1 s: ax/ay/az, gx/gy/gz, mag, incl, impact, temp_c.
- Detalhes em `docs/references/# Hardware IoT .txt`.

## Histórico das entregas

| Entrega | Eixo | Resultado |
|---|---|---|
| 1 — Fundação e dados | problema, personas, arquitetura, dataset v1, EDA | concluída |
| 2 — Modelo e explicabilidade | dataset de 37 colunas, XGBoost, SHAP, MLflow, Supabase, dashboard lendo o banco | concluída |
| 3 — Integração | API FastAPI, JWT, RLS, simulador, Open-Meteo, auditoria, dashboard religado à API | concluída em 24/08/2026 |
| 4 — MVP consolidado e validado | reprodutibilidade, integridade de dados, segurança, relatórios e recomendações, evidências | **em andamento**; ver `docs/spec-sprint-04.md` |

Saíram de escopo, com justificativa nas specs: RAG/LLM, app móvel, firmware físico, integração IBGE, deploy.

## Equipe

| Nome | Frente |
|---|---|
| Guilherme (Avila) | Backend, ML, arquitetura geral |
| Kainan | Dashboard, integração com a API |

## Metodologia de trabalho com IA

Pair programming com IA (driver/navigator): o desenvolvedor mantém o controle arquitetural e a IA executa sob supervisão. Fluxo: decisões e specs → execução → testes automatizados validando cada entrega.
