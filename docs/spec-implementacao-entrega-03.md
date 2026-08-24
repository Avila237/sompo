# Spec de implementação — Entrega 3 (Integração)

> Companheira de [`spec-sprint-03.md`](spec-sprint-03.md), que define **o que** o enunciado exige.
> Este documento define **como** será construído: arquitetura, contratos, estrutura de arquivos e
> critério de pronto por requisito.
>
> Decisões fechadas em sessão de grilling em 24/08/2026. Onde uma decisão foi tomada contra
> recomendação técnica, isso está registrado em §9 — não é ruído, é dívida rastreada.

---

## 1. Estado verificado do ambiente

Levantado por inspeção em 24/08/2026, não presumido:

| Fato | Valor | Consequência |
|---|---|---|
| Python disponível | 3.13.1 **e** 3.14.3 | venv em **3.13** — 3.14 é risco de wheel ausente para `xgboost`/`shap`/`numpy` |
| Node | v22.23.1 | dashboard roda sem ajuste |
| Supabase `sompo` | `ACTIVE_HEALTHY`, `sa-east-1`, ref `rnznhiexdaudrkvllres` | reativado |
| Dados no banco | equipamentos **200** · operadores **80** · avaliacoes **5.000** · predicoes **5.000** | sobreviveram à pausa; **não** repopular |
| Leitura anônima | HTTP 200 com **0 linhas** nas 4 tabelas | **RLS já habilitada sem policy para `anon`** |
| Leitura `service_role` | retorna tudo | confirma que o bloqueio é RLS, não perda de dados |
| `data/*.parquet`, `models/*.joblib` | **ausentes** (git-ignored) | dataset e modelo precisam ser regenerados |
| Docker, pyenv, uv, CI | ausentes | tudo roda direto na máquina |

> **Consequência não óbvia:** com RLS ligada e sem policy, o dashboard atual — que lê pela anon key —
> **não exibe dado nenhum hoje**. Religar à API não é refinamento arquitetural: é o conserto.

---

## 2. Arquitetura alvo

```
┌──────────────┐   POST /avaliacoes    ┌────────────────────────────────┐
│  simulador   │──────────────────────►│         API FastAPI            │
│  (telemetria │   Bearer <JWT>        │                                │
│  + operação) │                       │  valida (Pydantic)             │
└──────────────┘                       │       ↓                        │
                                       │  enriquece clima ──► Open-Meteo│
┌──────────────┐   GET /* + Bearer     │       ↓ (fallback: payload)    │
│  dashboard   │──────────────────────►│  persiste avaliação            │
│    React     │◄──────────────────────│       ↓                        │
└──────────────┘        JSON           │  XGBoost + SHAP (in-process)   │
                                       │       ↓                        │
                                       │  persiste predição + auditoria │
                                       └───────────────┬────────────────┘
                                                       │ service_role
                                                       ▼
                                       ┌────────────────────────────────┐
                                       │   Supabase (PostgreSQL + RLS)  │
                                       │  anon: sem acesso              │
                                       └────────────────────────────────┘
```

**Invariante central:** nenhum cliente fala com o banco. O browser não carrega chave de banco.

**Direção de dependência** (nunca invertida):

```
api ──► services ──► ml
             └────► db
    core ◄── todos          (core não importa ninguém)
```

---

## 3. Estrutura de arquivos

Novos, salvo indicação:

```
backend/
├── api/
│   ├── main.py              app, CORS, handlers de exceção, startup do modelo
│   ├── deps.py              dependências: usuário autenticado, cliente do banco
│   ├── schemas.py           modelos Pydantic de entrada e saída
│   └── routers/
│       ├── auth.py          POST /auth/token
│       ├── avaliacoes.py    POST /avaliacoes
│       ├── equipamentos.py  GET /equipamentos, GET /equipamentos/{id}
│       ├── alertas.py       GET /alertas
│       ├── kpis.py          GET /kpis
│       └── health.py        GET /health
├── core/
│   ├── config.py            leitura de env, sem dependência nova
│   ├── security.py          emissão e validação de JWT
│   ├── logging.py           logging estruturado para stdout
│   └── exceptions.py        exceções de domínio + handlers
├── services/
│   ├── scoring.py           orquestração do fluxo completo
│   ├── clima.py             cliente Open-Meteo + fallback
│   └── auditoria.py         gravação do registro de auditoria
├── ml/
│   ├── preprocess.py        EXTRAÍDO de train.py (ver §7 · RF-04)
│   └── predictor.py         carrega artefatos uma vez, prediz + SHAP
└── db/
    └── migrations/
        └── 001_entrega03.sql   idempotente, SEM DROP

scripts/
└── simulate_telemetry.py    emite leituras contra a API

tests/
└── test_api.py              testes novos (ver §7 · RF-11)
```

> ⚠️ **`backend/db/schema.sql` começa com `DROP TABLE`.** Reexecutá-lo apaga os 10.280 registros
> que acabaram de ser confirmados. Toda alteração de estrutura nesta entrega vai em
> `migrations/001_entrega03.sql`, que é idempotente e não destrói nada.

---

## 4. Mudanças no banco

`backend/db/migrations/001_entrega03.sql`:

```sql
-- Procedência do dado (decisão 8)
ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS
    fonte VARCHAR NOT NULL DEFAULT 'seed';          -- 'seed' | 'telemetria'

-- Procedência do clima (decisão 15)
ALTER TABLE avaliacoes ADD COLUMN IF NOT EXISTS
    clima_origem VARCHAR NOT NULL DEFAULT 'seed';   -- 'open-meteo' | 'payload' | 'seed'

-- Registro de uso (RF-08)
CREATE TABLE IF NOT EXISTS auditoria (
    auditoria_id  BIGSERIAL PRIMARY KEY,
    timestamp     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    usuario       VARCHAR NOT NULL,
    perfil        VARCHAR NOT NULL,
    acao          VARCHAR NOT NULL,
    equipamento_id VARCHAR,
    avaliacao_id  BIGINT,
    score_gerado  NUMERIC(5,2),
    modelo_versao VARCHAR,
    status        VARCHAR NOT NULL   -- 'sucesso' | 'erro'
);
CREATE INDEX IF NOT EXISTS idx_auditoria_ts      ON auditoria(timestamp);
CREATE INDEX IF NOT EXISTS idx_auditoria_usuario ON auditoria(usuario);

-- RLS explícita e documentada nas 5 tabelas
ALTER TABLE equipamentos ENABLE ROW LEVEL SECURITY;
ALTER TABLE operadores   ENABLE ROW LEVEL SECURITY;
ALTER TABLE avaliacoes   ENABLE ROW LEVEL SECURITY;
ALTER TABLE predicoes    ENABLE ROW LEVEL SECURITY;
ALTER TABLE auditoria    ENABLE ROW LEVEL SECURITY;
-- Nenhuma policy para anon: sem policy, RLS nega tudo.
-- service_role bypassa RLS por definição — é o único caminho de acesso.
```

---

## 5. Contrato da API

| Método | Rota | Auth | Requisitos |
|---|---|---|---|
| `POST` | `/auth/token` | — | RF-07 |
| `GET`  | `/health` | — | RF-02 |
| `POST` | `/avaliacoes` | Bearer | RF-01, RF-03, RF-04, RF-05 |
| `GET`  | `/equipamentos` | Bearer | RF-09 |
| `GET`  | `/equipamentos/{id}` | Bearer | RF-09, RF-10 |
| `GET`  | `/alertas` | Bearer | RF-09 |
| `GET`  | `/kpis` | Bearer | RF-09 |

**`POST /avaliacoes` — entrada** (campos climáticos opcionais; se ausentes, buscados na Open-Meteo):

```json
{
  "equipamento_id": "EQ-0042",
  "operador_id": "OP-0015",
  "latitude": -12.6819, "longitude": -55.7139,
  "tipo_operacao": "colheita",
  "velocidade_kmh": 6.2, "horas_operacao": 7.5, "horario_operacao": 14,
  "vibracao_g": 1.8, "temperatura_motor": 92.0,
  "tipo_solo": "argiloso", "distancia_agua_m": 120.0, "declividade": 8.4,
  "pct_velocidade_acima_recomendada": 22.0, "freq_eventos_bruscos": 4.1,
  "pct_operacoes_noturnas": 18.0, "score_operador_historico": 61.0,
  "ultima_manutencao_dias": 210, "ultima_manutencao_horas_op": 640.0,
  "temperatura_ar": 28.4, "precipitacao_mm": 42.0,
  "umidade_solo": 78.0, "velocidade_vento": 12.0, "condicao_clima": "chuvoso"
}
```

**Saída** (preserva RF-10 — score nunca vem sozinho):

```json
{
  "avaliacao_id": 5001,
  "equipamento_id": "EQ-0042",
  "risco_score": 74.3,
  "faixa_risco": "alto",
  "clima_origem": "open-meteo",
  "contribuicoes_por_grupo": {
    "ambiental": 12.4, "geografico": 6.1, "operacional": 9.8,
    "equipamento": 18.6, "operador": 8.1, "manutencao": 3.2
  },
  "top_fatores": [
    {"feature": "historico_sinistros", "rotulo": "Histórico de sinistros",
     "shap_value": 18.6, "grupo": "equipamento"}
  ],
  "modelo_versao": "xgboost-v1-baseline",
  "timestamp": "2026-08-24T14:30:00Z"
}
```

**Erros:** `400` payload inválido · `401` sem token ou token expirado · `404` equipamento
inexistente · `502` falha de dependência externa não contornável · `500` erro interno, com
`request_id` correlacionável ao log. Nenhuma resposta expõe stack trace.

---

## 6. Configuração

Acrescentar ao `.env.example` — **apenas placeholders**, nunca valores reais:

```bash
SUPABASE_SERVICE_ROLE_KEY=defina-no-env-local   # superusuário: nunca no frontend, nunca no git
JWT_SECRET_KEY=gerar-com-openssl-rand-hex-32
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=480
DEMO_USERS=analista:senha:analista,gestor:senha:gestor,operador:senha:operador
OPENMETEO_BASE_URL=https://api.open-meteo.com/v1
OPENMETEO_TIMEOUT_S=5
API_CORS_ORIGINS=http://localhost:5173,http://localhost:5175
```

`dashboard/.env.local` perde as chaves do Supabase e ganha só `VITE_API_BASE_URL`.

---

## 7. Trabalho por requisito

Cada bloco vira uma issue no Linear (decisão 12).

### RF-00 · Ambiente executável *(pré-requisito de tudo)*
venv em Python 3.13, `pip install -r backend/requirements.txt`, `python scripts/generate_dataset.py`,
`python backend/ml/train.py`.
**Pronto quando:** `models/xgboost_model.joblib` e `encoder.joblib` existem e `pytest tests/ -v`
roda. Divergência entre as métricas regeneradas e `models/metrics.json` deve ser **registrada, não
corrigida** — o modelo não é objeto desta entrega.

### RF-01 · Backend integrador
`main.py`, `deps.py`, `routers/`, `services/scoring.py`, `ml/predictor.py`. Modelo carregado uma
vez no startup, não por requisição.
**Pronto quando:** `POST /avaliacoes` devolve score com decomposição, tendo gravado avaliação e
predição.

### RF-02 · Modularidade e exceções
`core/exceptions.py` com handlers registrados; direção de dependência de §2 respeitada.
**Pronto quando:** banco fora do ar, modelo ausente e payload malformado produzem resposta tratada
e log — nenhum derruba o processo, nenhum vaza stack.

### RF-03 · Persistência
Escrita de `avaliacoes` e `predicoes` na mesma operação lógica; se a predição falhar após a
avaliação ter sido gravada, o registro não fica órfão em silêncio — o erro é registrado e a
avaliação marcada.
**Pronto quando:** cada `POST` bem-sucedido produz uma linha em cada tabela, ligadas por `avaliacao_id`.

### RF-04 · Pipeline e integridade histórica
Extrair `preprocess_features()` e `derive_faixa()` de `train.py` para `ml/preprocess.py`;
`train.py` passa a importar de lá e **reexporta os nomes**, para não quebrar os testes existentes.
Remover `clear_predicoes()` do caminho normal de `populate_predictions.py`, atrás de `--reset`.
**Pronto quando:** treino e inferência usam a mesma função; rodar o script duas vezes não apaga
histórico; os 251 testes seguem verdes.

### RF-05 · Ingestão validada + Open-Meteo
`schemas.py` com validação de faixas e das regras de consistência de `docs/data schema.md`
(`parado` ⇒ velocidade 0; `tem_iot=false` ⇒ `temperatura_motor` nula). `services/clima.py` com
timeout e fallback para o payload, gravando `clima_origem`. `scripts/simulate_telemetry.py`.
**Pronto quando:** payload inválido é rejeitado com 400 e **não** persiste; com a rede cortada, a
requisição ainda completa marcando `clima_origem='payload'` e registrando o incidente.

### RF-06 · Documentação do caminho do dado
Seção no README descrevendo cada salto do fluxo.
**Pronto quando:** um leitor externo segue o caminho de um dado sem abrir código.

### RF-07 · Controle de acesso
`core/security.py` (emissão/validação JWT), `routers/auth.py`, dependência de autenticação em
todas as rotas de dado. Migration com RLS explícita. `service_role` só server-side.
**Pronto quando:** requisição sem token recebe 401; o bundle do dashboard não contém chave de
banco; a anon key não lê nada.

### RF-08 · Registros de uso
`core/logging.py` (stdout estruturado com `request_id`) e `services/auditoria.py` (tabela).
**Pronto quando:** dada uma predição, é possível reconstruir quem a pediu e quando, consultando
`auditoria`.

### RF-09 · Dashboard religado
Reescrever `dashboard/src/data/api.ts` para HTTP contra a API; remover `lib/supabase.ts` do caminho
de dados; adicionar tela ou filtro de agregação **por tipo de operação**; alertas vindos de `/alertas`.
**Pronto quando:** as 3 telas exibem dados reais sem que o browser toque o Supabase.

### RF-10 · Saídas interpretáveis
Preservar o contrato de §5: score sempre acompanhado de faixa, grupos e top fatores rotulados em
português.
**Pronto quando:** nenhuma resposta da API devolve score sem decomposição.

### RF-11 · Testes
`tests/test_api.py`: payload inválido rejeitado sem persistir · 401 sem token · scoring
end-to-end com dependências externas mockadas.
**Pronto quando:** os três passam e a suíte existente continua verde.

### RF-12 · README e diagrama
Atualizar arquitetura, diagrama Mermaid, instruções de execução do sistema completo, seção de
evolução vs. entrega anterior, corrigir as referências quebradas de `docs/references/`.
**Pronto quando:** um terceiro sobe o sistema seguindo só o README.

### RF-13 · Vídeo
≤5 min, narração humana, demonstra entrada → score → interface, explica arquitetura, publicado
como **não listado**, link no README.

### RF-14 · Conformidade do repositório
Repositório privado com `fiap-tutoria` como colaborador; `.gitignore` recebe `AUDITORIA.md`;
commit da spec.

---

## 8. Riscos

| Risco | Impacto | Mitigação |
|---|---|---|
| `xgboost`/`shap`/`numpy` sem wheel no Python instalado | bloqueia tudo | venv em 3.13, não 3.14 |
| Reexecutar `schema.sql` | apaga 10.280 registros | toda mudança via `migrations/001_entrega03.sql` |
| Métricas do retreino divergirem de `metrics.json` | ruído de última hora | registrar a divergência, não perseguir; o modelo não é objeto da entrega |
| `service_role` vazar para o frontend ou para o Git | acesso total ao banco | só em `.env`; `.env.example` com placeholder; conferir bundle antes de gravar o vídeo |
| Open-Meteo indisponível durante a gravação | demo interrompida | fallback da decisão 15 já cobre |
| Supabase pausar de novo por inatividade | banco fora | verificar status antes de gravar o vídeo |

---

## 9. Dívidas registradas

Assumidas conscientemente nesta entrega, para a leva de melhorias seguinte:

| # | Dívida | Por quê agora | O que fazer depois |
|---|---|---|---|
| D1 | **Credenciais em variável de ambiente**, sem tabela de usuários com hash | decisão do Guilherme contra recomendação de tabela com `passlib` | tabela `usuarios` com hash bcrypt |
| D2 | **JWT próprio** em vez de Supabase Auth | `python-jose` já declarado; evita configurar provider | migrar para Supabase Auth e RLS decidindo por linha via `auth.uid()` |
| D3 | **Perfis sem escopo de dados distinto** — operador, gestor e analista veem o mesmo | decisão 7 (piso) | policies por perfil |
| D4 | Modelo com **operador e manutenção quase sem peso** (`historico_sinistros` domina) | fora do escopo desta entrega | recalibrar pesos e regenerar a cadeia |
| D5 | `docs/data schema.md` **divergente do código** na fórmula de score | depende de D4 | sincronizar após recalibrar |
| D6 | Dashboard sem router — sem deep link por equipamento | não avaliado | `react-router-dom` já está instalado |
| D7 | **Sem deploy** — roda local | decisão 5 | Railway/Render/Vercel |
| D8 | **Sem CI** | não avaliado | lint + testes + audit de dependências |

> D1, D2 e D3 são a mesma dívida vista de três ângulos e devem ser resolvidas juntas.
