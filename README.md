# Plataforma de Análise Preditiva de Riscos para Equipamentos Agrícolas

> **Challenge FIAP + Sompo Seguros**
> Entrega 4 — Consolidação: MVP integrado, validado, com controle de acesso por perfil, relatórios e recomendações

---

## Sumário

0. [Como Rodar o Projeto](#como-rodar-o-projeto)
1. [Descrição do Problema](#1-descrição-do-problema)
2. [Solução Proposta](#2-solução-proposta)
3. [Personas e Necessidades](#3-personas-e-necessidades)
4. [Estruturação dos Dados](#4-estruturação-dos-dados)
5. [Arquitetura da Solução](#5-arquitetura-da-solução)
6. [Modelo Preditivo](#6-modelo-preditivo)
7. [Evolução ao Longo das Quatro Sprints](#7-evolução-ao-longo-das-quatro-sprints)
8. [Estado Final, Decisões de Escopo e Dívidas](#8-estado-final-decisões-de-escopo-e-dívidas)
9. [Vídeo de Apresentação](#9-vídeo-de-apresentação)
10. [Equipe](#10-equipe)

---

## Como rodar o projeto

### Pré-requisitos

**Python 3.13.** Não use 3.14 — `xgboost`, `shap` e `numpy` ainda não publicam wheels para
essa versão e a instalação falha ou tenta compilar do zero. Confira com `python3.13 --version`; sem
ele, instale pelo [python.org](https://www.python.org/downloads/) ou, no macOS,
`brew install python@3.13`.

**Node.js 20.19+, 22.13+ ou 24+** (a faixa mais estreita entre o Vite 8 e o ESLint 10, que a CI
roda no `npm run lint`), para o dashboard. Confira com `node -v`.

**macOS — `libomp` (OpenMP).** O XGBoost depende do runtime OpenMP, que **não** vem pelo
`pip`. Sem ele, `import xgboost` falha com `libxgboost.dylib could not be loaded`:

```bash
brew install libomp
```

Linux e Windows já trazem o runtime equivalente (`libgomp` / `vcomp140`) e não precisam
deste passo.

### Primeira vez (setup completo)

O sistema tem duas metades que sobem em terminais separados: a **API** e o **dashboard**. A API
precisa estar no ar primeiro — sem ela o dashboard não tem de onde ler.

#### Terminal 1 — backend e API

```bash
# 1. Clonar o repositório
git clone https://github.com/Avila237/sompo.git
cd sompo

# 2. Criar ambiente virtual (Python 3.13)
python3.13 -m venv .venv          # Windows: py -3.13 -m venv .venv

# 3. Ativar ambiente virtual
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# 4. Instalar dependências (≈2 min no macOS; ≈12 min no Windows)
pip install -r backend/requirements.txt

# 4b. Criar o .env ANTES dos testes: a API e os testes leem a configuração ao importar
cp .env.example .env              # Windows: copy .env.example .env
#     e troque os placeholders — ver "Configuração do backend (.env na raiz)" abaixo

# 5. Gerar o dataset
python scripts/generate_dataset.py

# 6. Treinar o modelo (gera models/*.joblib, exigidos pelos testes e pela API)
python backend/ml/train.py

# 7. Rodar os testes (a mesma seleção da CI)
pytest -m "not seed and not rede"

# 8. Subir a API
uvicorn backend.api.main:app --reload --port 8000
```

Com a API no ar, o Swagger navegável fica em **http://localhost:8000/docs** e a verificação de
saúde em **http://localhost:8000/health**.

#### Terminal 2 — dashboard

```bash
cd dashboard
cp .env.example .env.local     # VITE_API_BASE_URL=http://localhost:8000
npm install
npm run dev
# Abrir o endereço que o Vite imprimir (por padrão http://localhost:5173)
```

O dashboard pede usuário e senha na abertura. As credenciais são trocadas por um JWT em
`POST /auth/token` — **nenhuma credencial fica no bundle nem em `.env.local`**, cuja única
variável é a base da API.

#### Configuração do backend (`.env` na raiz)

Use o [`.env.example`](.env.example) como base. O arquivo **não vai para o Git**. A
`SUPABASE_SERVICE_ROLE_KEY` é combinada fora do repositório.

**Usuários** ficam na tabela `usuarios` do banco (senha em hash scrypt), não no `.env`. Cadastre com
`python scripts/criar_usuario.py <usuario> --perfil <perfil>`, com perfil entre `analista`,
`gestor`, `tecnico` e `operador`; o operador exige `--operador OP-xxxx`. A senha é pedida no
terminal, sem eco, com no mínimo 12 caracteres.

Troque **todos** os placeholders. A API recusa subir se faltar variável obrigatória ou se o
`JWT_SECRET_KEY` tiver menos de 32 bytes, o que inclui o placeholder do exemplo. Gere o segredo
com `python -c "import secrets; print(secrets.token_hex(32))"`.

> ⚠️ A `service_role` é superusuário do banco: só server-side, nunca no frontend, nunca versionada.

**Sem as credenciais reais do Supabase ainda?** Dá para validar parte do setup com valores de
teste (a CI usa `SUPABASE_URL=http://supabase.invalid`) e o segredo gerado acima. Sem banco
funcionam: a suíte do passo 7, a API subindo com `/health` respondendo e o dashboard abrindo na
tela de login. **Login e rotas de dado dependem do banco** e respondem `503 Banco de dados
indisponível`; o teste de ponta a ponta exige as credenciais reais.

#### Notas de ambiente

Se `pytest` falhar reclamando de artefato de modelo ausente, o passo 6 não rodou — os `.joblib`
são git-ignored e precisam ser gerados localmente.

`pytest tests/` sem o `-m` também roda os testes marcados `rede`, que conectam no Supabase de
verdade: com credenciais de teste no `.env` eles falham (erro de conexão), e isso não é bug. Rode-os
só com o banco real configurado: `pytest -m "rede and not seed"`. O `-m` da linha de comando
substitui o `-m "not seed"` do `pytest.ini`; sem o `and not seed`, entram também os testes `seed`,
que assumem as 5.000 avaliações exatas do seed e falham assim que houver ingestão pela API.

Se a tela de login acusar que não consegue falar com a API, confira se o Terminal 1 está de pé e
se a porta em `VITE_API_BASE_URL` bate com a do `uvicorn`.

#### Roteiro de demonstração (`scripts/demo.sh`)

Com o setup feito (venv, `.env`, modelo treinado e usuário `analista` cadastrado),
`bash scripts/demo.sh` sobe a API e o dashboard e percorre o fluxo integrado. `--auto 4` avança
sozinho, e `--sem-web` roda só a API.

- **Windows:** rode no **Git Bash**, não no PowerShell nem no cmd. O script acha o Python em
  `.venv\Scripts\python.exe`.
- As portas 8000 e 5173 precisam estar livres: o script não encerra processos que não iniciou.
  Use `--porta N` para trocar a da API.
- Os logs ficam num diretório temporário, cujo caminho aparece no início.
- A checagem de RLS (etapa 2d) precisa da `SUPABASE_ANON_KEY`. Sem ela, a etapa aparece como
  "não verificado".

#### Onde as instruções foram testadas

- **macOS:** clone limpo seguindo só esta seção (BRA-467).
- **CI:** o job de backend roda em **Ubuntu, Windows e macOS** a cada PR.
- **Windows, manualmente:** validação do setup completo em andamento (BRA-442).

### Atualizando (repositório já clonado)

```bash
git pull
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
pytest -m "not seed and not rede"
cd dashboard && npm install      # se package.json mudou
```

---

## 1. Descrição do Problema

O setor agrícola brasileiro opera com equipamentos de alto valor — colheitadeiras, tratores e implementos — expostos diariamente a riscos operacionais e ambientais como colisões com obstáculos no solo, tombamentos, atolamento por instabilidade do terreno, operação em proximidade de corpos d'água e danos durante o transporte entre propriedades.

Hoje, a gestão desses riscos é predominantemente reativa: o sinistro ocorre, gera custos elevados (reparo, indisponibilidade, perda total) e só então medidas corretivas são tomadas. A Sompo, que ocupa a 3ª posição no mercado brasileiro de seguros de máquinas e implementos agrícolas, enfrenta esse cenário diretamente — seus produtos Benfeitorias e Penhor Rural cobrem desde incêndio e furto até colisão de colheitadeiras e operação próxima de água.

O problema central é a **baixa previsibilidade desses eventos**. Faltam sistemas que correlacionem fatores ambientais (clima, tipo de solo, precipitação, proximidade de rios) com fatores operacionais (tipo de operação, velocidade, horário, histórico do equipamento) para antecipar situações de risco antes que o dano aconteça.

Os impactos diretos incluem: alto custo de sinistros para a seguradora, perdas financeiras e de produtividade para o produtor rural, e riscos à segurança dos operadores em campo.

---

## 2. Solução Proposta

A solução proposta é uma **plataforma de análise preditiva de riscos para equipamentos agrícolas**, composta por um aplicativo móvel como interface principal, um backend inteligente com modelo de machine learning e, opcionalmente, um dispositivo IoT embarcado (ESP32) para coleta de dados telemétricos em tempo real.

O sistema cruza dados ambientais (clima, precipitação, tipo de solo, proximidade de corpos d'água), operacionais (tipo de operação, vibração, temperatura, velocidade, histórico de uso) e geográficos (localização, relevo, hidrografia via shapefiles do IBGE) para gerar um **score de risco por equipamento e contexto operacional**.

A partir desse score, a plataforma entrega três tipos de saída:

- **Alertas preventivos** em tempo de decisão (antes ou durante a operação)
- **Recomendações práticas** de mitigação (ajuste de rota, adiamento, redução de velocidade)
- **Relatórios explicáveis** com os principais fatores que contribuem para o risco, utilizando SHAP para garantir transparência e auditabilidade

A arquitetura é **mobile-first** — o app funciona como ponto central de coleta (GPS, inputs do operador) e entrega (alertas, dashboard). O dispositivo IoT com ESP32 é um complemento opcional para equipamentos modernos, adicionando sensores de vibração (acelerômetro + giroscópio MPU-6050 GY-521) e temperatura (DS18B20) via Bluetooth Low Energy. Essa decisão garante **cobertura universal**: qualquer equipamento, inclusive máquinas mais antigas sem porta OBD, pode ser monitorado apenas com o celular do operador.

O valor entregue é a transformação de decisões reativas em ações preventivas, reduzindo frequência e severidade de sinistros para a Sompo e custos operacionais para o produtor rural.

> **Visão × MVP entregue.** Os parágrafos acima descrevem o horizonte do produto. O MVP da Sprint 4
> entrega o núcleo: ingestão por simulação, score com explicação SHAP, recomendações por regra
> determinística, alertas, relatórios de tendência e um dashboard web com leitura por perfil. App
> móvel, ESP32, RAG e shapefiles do IBGE saíram de escopo, cada um com motivo, na
> [seção 8](#8-estado-final-decisões-de-escopo-e-dívidas).

A plataforma foi projetada para evoluir de uma solução de scoring ambiental e operacional para um ecossistema completo de gestão de risco: com perfil comportamental do operador incorporado ao modelo, manutenção preventiva comparada com os intervalos recomendados pelo fabricante, explicações contextuais geradas a partir de uma base de conhecimento técnico simulada (RAG), e Usage-Based Insurance para precificação dinâmica baseada em risco histórico real.

---

## 3. Personas e Necessidades

A solução atende três perspectivas principais, desdobradas em perfis específicos:

### 3.1 Sompo (Seguradora)

A Sompo precisa identificar e quantificar fatores que elevam a probabilidade de sinistros, gerar scores de risco por equipamento/região/tipo de operação para apoiar subscrição e precificação, e manter trilha de auditoria sobre os dados e modelos utilizados. As áreas internas beneficiadas incluem:

- **Subscrição:** score explicável para decisões técnicas e recomendações ao cliente.
- **Sinistros:** contexto ambiental e operacional do evento para triagem e aprendizado preventivo.
- **Gestão de risco:** visão agregada para orientar prevenção e reduzir frequência de sinistros.

### 3.2 Cliente Segurado (Produtor Rural / Empresa Agrícola)

O produtor rural ou gestor da operação agrícola precisa de um painel simples de risco por equipamento e operação, alertas antes de operações críticas, recomendações práticas sobre o que mudar (rota, horário, velocidade) e relatórios por fazenda/região/período que comprovem evolução e justifiquem investimentos em segurança. Precisa também poder configurar políticas internas, como definir quando apenas alertar e quando bloquear uma operação.

### 3.3 Usuário Final (por perfil operacional)

- **Operador de equipamento:** precisa de alertas diretos e objetivos no celular — risco de colisão, solo instável, proximidade de água — para ajustar a condução em tempo real.
- **Gestor de frota:** precisa de ranking de risco por equipamento e área, visão comparativa entre modos de uso (campo vs. transporte) e configuração de políticas de alerta.
- **Técnico de manutenção:** precisa identificar padrões operacionais que antecedem danos para atuar preventivamente e reduzir indisponibilidade.
- **Corretor(a):** precisa de explicação objetiva dos fatores de risco e ações preventivas sugeridas para orientar o cliente.

---

## 4. Estruturação dos Dados

A solução integra dados de quatro categorias principais:

### 4.1 Variáveis

**Dados Ambientais** *(fonte: Open-Meteo API)*

| Variável | Tipo | Descrição |
|---|---|---|
| `temperatura_ar` | °C | Temperatura ambiente no momento da operação |
| `precipitacao_mm` | mm | Volume de chuva acumulado nas últimas 24h |
| `umidade_solo` | % | Estimativa de umidade do solo (precipitação recente + tipo de solo) |
| `velocidade_vento` | km/h | Intensidade do vento na região |
| `condicao_clima` | categórico | Ensolarado, nublado, chuvoso, tempestade |

**Dados Geográficos** *(fonte: IBGE Shapefiles + GPS do app)*

| Variável | Tipo | Descrição |
|---|---|---|
| `latitude` | float | Posição do equipamento |
| `longitude` | float | Posição do equipamento |
| `tipo_solo` | categórico | Arenoso, argiloso, misto (derivado da região) |
| `distancia_agua_m` | metros | Distância até o corpo d'água mais próximo |
| `declividade` | % | Inclinação do terreno na posição atual |

**Dados Operacionais** *(fonte: app móvel + IoT opcional)*

| Variável | Tipo | Descrição |
|---|---|---|
| `tipo_operacao` | categórico | Colheita, plantio, pulverização, transporte, parado |
| `velocidade_kmh` | km/h | Velocidade de deslocamento do equipamento |
| `vibracao_g` | g | Nível de vibração (acelerômetro IoT ou celular) |
| `temperatura_motor` | °C | Temperatura próxima ao motor (sensor DS18B20 via IoT) |
| `horas_operacao` | horas | Horas acumuladas de operação contínua na sessão |
| `horario_operacao` | hora | Hora do dia (operações noturnas = risco elevado) |

**Dados do Equipamento** *(fonte: cadastro no app)*

| Variável | Tipo | Descrição |
|---|---|---|
| `tipo_equipamento` | categórico | Colheitadeira, trator, implemento |
| `idade_equipamento` | anos | Tempo desde fabricação |
| `historico_sinistros` | int | Quantidade de sinistros anteriores registrados |
| `tem_iot` | booleano | Se possui dispositivo IoT acoplado |

**Dados do Operador** *(fonte: app + histórico calculado)*

| Variável | Tipo | Descrição |
|---|---|---|
| `operador_id` | str | Identificador do operador (OP-0001 a OP-0080) |
| `pct_velocidade_acima_recomendada` | % | % do tempo acima da velocidade recomendada |
| `freq_eventos_bruscos` | /hora | Eventos de aceleração/frenagem brusca por hora |
| `pct_operacoes_noturnas` | % | Proporção histórica de operações noturnas |
| `score_operador_historico` | 0–100 | Média móvel do score do operador (30 dias) |

**Dados de Manutenção** *(fonte: app + base de conhecimento)*

| Variável | Tipo | Descrição |
|---|---|---|
| `ultima_manutencao_dias` | int | Dias desde a última manutenção declarada |
| `ultima_manutencao_horas_op` | float | Horas de operação desde última manutenção |
| `atraso_manutencao_pct` | 0.0–3.0 | 1.0 = no limite, 1.5 = 50% atrasado |
| `manutencao_atrasada` | bool | Calculado: ultrapassou algum dos limites |

**Variável Alvo**

| Variável | Tipo | Descrição |
|---|---|---|
| `risco_score` | 0–100 | Score contínuo de risco calculado pelo modelo |
| `faixa_risco` | categórico | Baixo (0–33), médio (34–66), alto (67–100) |

### 4.2 Dataset Simulado (exemplo)

| equipamento_id | tipo_equip | tipo_operacao | precip_mm | umid_solo | dist_agua_m | tipo_solo | vel_kmh | vibr_g | temp_motor | horas_op | horario | idade | hist_sin | operador_id | atraso_manut | score | faixa |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| EQ-001 | colheitadeira | colheita | 42 | 78 | 120 | argiloso | 6.2 | 1.8 | 92 | 7.5 | 14:30 | 5 | 2 | OP-012 | 1.4 | 74 | alto |
| EQ-002 | trator | transporte | 3 | 25 | 2800 | arenoso | 28 | 0.6 | 68 | 2.0 | 09:15 | 2 | 0 | OP-034 | 0.6 | 18 | baixo |
| EQ-003 | colheitadeira | colheita | 18 | 55 | 450 | misto | 5.1 | 1.2 | 85 | 5.0 | 17:45 | 8 | 1 | OP-012 | 0.9 | 52 | médio |
| EQ-004 | trator | pulverização | 0 | 15 | 3500 | arenoso | 12 | 0.4 | 71 | 3.0 | 10:00 | 1 | 0 | OP-067 | 0.7 | 11 | baixo |
| EQ-005 | implemento | transporte | 35 | 70 | 80 | argiloso | 32 | 2.1 | — | 1.5 | 22:00 | 12 | 3 | OP-021 | 1.8 | 88 | alto |

> **Leitura do exemplo EQ-005:** o risco alto se justifica pela combinação de chuva recente significativa (35mm), solo argiloso com alta umidade (70%), proximidade de água (80m), alta velocidade em transporte (32 km/h), vibração elevada, equipamento antigo com histórico de sinistros e operação noturna.

Para o desenvolvimento e validação do modelo, foi gerado um dataset simulado com **5.000 registros** e **37 colunas**, cobrindo variações realistas de todas as variáveis e distribuição balanceada entre as faixas de risco.

---

## 5. Arquitetura da Solução

A arquitetura é organizada em cinco camadas:

### 5.1 O invariante

**Nenhum cliente fala com o banco.**

A API é a única porta. O browser não carrega chave de banco; o acesso ao PostgreSQL é feito
server-side com `service_role`, e a RLS está ativa sem policy para `anon` — leitura anônima
retorna zero linhas. Tudo o mais nesta seção decorre disso.

Na entrega anterior o dashboard lia o Supabase direto, com a chave embutida no bundle do browser.
Quem abrisse a página conseguia ler e escrever as tabelas. Com dado sintético o dano ficava
contido; com dado de segurado real, seria exposição de dado pessoal sob a LGPD.

### 5.2 Direção de dependência

```
api ──▶ services ──▶ ml
              └────▶ db
     core ◀── todos          (core não importa ninguém)
```

A direção nunca se inverte. `core` concentra configuração, segurança e exceções, e não conhece
quem o usa — o que permite testar as camadas de cima sem subir banco nem carregar modelo.

### 5.3 Entrada de dados

A entrada acontece por `POST /avaliacoes`, autenticada. Duas origens estão previstas:

- **Simulador de telemetria** (`scripts/simulate_telemetry.py`) — emite leituras contra a API,
  cobrindo o requisito de ingestão *"por simulação ou por dispositivos reais"*
- **App móvel + ESP32 via BLE** — evolução futura; o hardware está especificado em
  [`docs/references/`](docs/references/), fora do escopo desta entrega

Fontes externas: **Open-Meteo** para clima pela coordenada da leitura, com fallback para o payload
e recusa explícita (`502`) se ambos faltarem. O enriquecimento geográfico via shapefiles do IBGE
saiu de escopo — solo, distância de água e declividade já vêm
no dataset.

### 5.4 Processamento e modelo

A API valida com Pydantic, complementa com o cadastro do equipamento, monta o vetor de 30
features com o **mesmo encoder ajustado no treino** e chama o modelo. Só depois de ter score e
explicação em mãos ela persiste a avaliação e a predição.

O **XGBoost** é carregado uma vez no startup, não por requisição, e devolve score de 0 a 100. O
**SHAP** decompõe esse score em contribuições por grupo de features, preservando o sinal. O
**MLflow** registra os runs de treino (experimento `safefield-xgboost`).

O percurso completo, salto a salto e com o estado real de cada um, está em
**[5.7](#57-o-caminho-de-um-dado-salto-a-salto)**.

### 5.5 Segurança

**Autenticação.** JWT próprio (PyJWT), emitido em `POST /auth/token` com validade de 8 horas.
Usuários vivem na tabela `usuarios`, com senha em hash **scrypt** (parâmetros da OWASP gravados no
próprio hash); o cadastro é feito por `scripts/criar_usuario.py`, que pede a senha sem eco. O login
limita tentativas antes de calcular o hash e responde igual, no mesmo tempo, para usuário
inexistente, inativo ou senha errada. Só `/auth/token` e `/health` são públicas.

**Controle de acesso por perfil.** Há uma frota só; os perfis diferem no **recorte**, aplicado na
API (o front só evita abrir tela que a API recusaria):

| Rota | analista (Sompo) | gestor de frota | técnico | operador |
|---|---|---|---|---|
| `POST /avaliacoes` | qualquer operador | `403` | `403` | só em nome próprio, em equipamento que já operou |
| `GET /equipamentos`, `/{id}`, `/alertas` | frota | frota | frota | só os equipamentos que operou |
| `GET /kpis`, `GET /tendencias` | sim | sim | sim | `403` (agregação da frota) |

O token do operador carrega o `operador_id`, que liga o login ao recorte. Negado → `403` com o
motivo em `detail`. Matriz completa em [`docs/contrato-api.md`](docs/contrato-api.md).

**Minimização (LGPD).** Nos equipamentos que operou, o operador vê as avaliações de **outros**
operadores sem `operador_id`, `latitude` e `longitude` (também mascarados nos fatores SHAP). Os
perfis de frota veem tudo. Os campos internos de idempotência (`leitura_id`, `payload_hash`) não
saem em nenhuma resposta de leitura.

**Proteção do dado.** Nenhum cliente fala com o banco (5.1): `service_role` só server-side, RLS
ligada sem policy para `anon`. O token fica em `sessionStorage`, e o build de produção do dashboard
aplica **CSP** estrita (`script-src 'self'`, `connect-src` só para a API). O segredo JWT abaixo de
32 bytes impede a API de subir. Localização precisa não vai para o log.

**Rastreabilidade.** Toda requisição tem um `request_id` (header `X-Request-ID`, também no corpo do
`500`), presente em cada linha de log; o dashboard mostra esse código em erros 5xx. Toda decisão e
recusa de `POST /avaliacoes` grava uma linha em `auditoria`, com usuário, ação, status, score e
versão do modelo. Falhas previsíveis respondem `503` (banco ou modelo indisponível), não `500`.

**Limitações declaradas.** O token vale até expirar: desativar ou rebaixar um usuário só vale no
próximo login.

### 5.6 Interfaces

**Dashboard web (React)**, consumindo exclusivamente a API. O perfil vem do login e define o menu e
a tela inicial:

| Tela | Consome | Exibe | Perfis |
|---|---|---|---|
| Visão geral | `GET /kpis`, `GET /alertas`, `GET /equipamentos` | KPIs, mapa por região, risco por tipo de operação, tendência e alertas | analista, gestor, técnico |
| Equipamentos | `GET /equipamentos` | ranking com filtro, busca e ordenação | analista, gestor, técnico |
| Detalhe | `GET /equipamentos/{id}` | recomendações com o critério que as disparou, decomposição SHAP, manutenção e histórico | todos (operador: só os dele) |
| Relatórios | `GET /tendencias` | tendência do score por equipamento, região e operação, com datas reais e exportação CSV | analista, gestor, técnico |
| Manutenção da frota | `GET /equipamentos` | frota ordenada pelo atraso de manutenção | técnico (tela inicial) |
| Meus equipamentos | `GET /equipamentos`, `GET /alertas` | só os equipamentos que o operador operou e seus alertas | operador (tela inicial) |

O card de recomendações abre filtrado no público do perfil. A tela não afirma nada que não veio da
API: sem confirmação de ação simulada, sem notificação fictícia, e ausência de dado aparece como
ausência ("sem avaliação"). Falhas da API (fora do ar, lenta, resposta malformada, 5xx, sessão
expirada) produzem mensagem legível com "Tentar de novo" — evidências em
[`docs/evidencias/front/`](docs/evidencias/front/). Simulador e UBI · Prêmios seguem atrás de
**"Em breve"**. Stack: React 19 + TypeScript + Vite + Tailwind CSS v4. Detalhes em
[`dashboard/README.md`](dashboard/README.md).

**App móvel** — fora de escopo (seção 8).

### 5.6.1 Diagrama de arquitetura

A API como orquestradora entre entrada, banco, modelo e interface. A aresta tracejada para a
Open-Meteo marca a dependência externa, que tem fallback; a aresta cortada marca o caminho fechado.

```mermaid
flowchart TB
    SIM["Simulador de telemetria<br/>scripts/simulate_telemetry.py"]
    DASH["Dashboard React<br/>menu e recorte por perfil"]
    METEO["Open-Meteo<br/>clima pela coordenada"]

    subgraph API["API FastAPI — unica porta"]
        direction TB
        AUTH["Login + JWT<br/>perfil e operador_id"]
        ESC["Escopo por perfil<br/>403 fora do recorte"]
        VAL["Validacao Pydantic<br/>faixas e consistencia cruzada"]
        ENR["Clima<br/>medido em campo prevalece"]
        PRE["preprocess_features<br/>vetor de 30 features"]
        MOD["XGBoost + SHAP<br/>carregado no startup"]
        REC["Recomendacoes<br/>regras deterministicas"]
        PERS["Grava avaliacao + predicao<br/>+ auditoria"]
        CON["Consultas<br/>kpis, alertas, tendencias"]
        AUTH --> ESC
        ESC --> VAL --> ENR --> PRE --> MOD --> REC --> PERS
        ESC --> CON
    end

    subgraph DB["Supabase — PostgreSQL + RLS"]
        TAB[("equipamentos, operadores<br/>avaliacoes, predicoes")]
        USR[("usuarios<br/>hash scrypt")]
        AUD[("auditoria")]
    end

    SIM -->|"POST /avaliacoes · Bearer"| AUTH
    DASH -->|"GET · Bearer"| AUTH
    CON -->|JSON| DASH
    ENR -.->|"sem clima no payload · timeout curto"| METEO
    AUTH -->|service_role| USR
    PERS -->|service_role| TAB
    PERS -->|service_role| AUD
    CON -->|service_role| TAB
    DASH --x|"anon: RLS nega"| DB
```

> **A seta cortada continua o invariante.** Na Entrega 2 ela era o caminho principal: o dashboard
> lia o banco direto. Desde a Entrega 3 está fechada; na Sprint 4 a porta única ganhou escopo por
> perfil, usuários com hash e auditoria de cada decisão.

### 5.7 O caminho de um dado, salto a salto

Esta seção responde à exigência do enunciado de *"definição clara de como os dados chegam ao
sistema e como são utilizados para alimentar o modelo preditivo"*. O percurso é o mesmo para
qualquer leitura, do momento em que ela é emitida até aparecer na tela.

```
origem → validação → complemento cadastral → enriquecimento climático → vetor de 30 features →
XGBoost → SHAP → persistência da avaliação → persistência da predição → API → interface
```

Legenda de estado: **✅ implementado** · **🟡 parcial**

#### 1. Origem ✅

Uma leitura chega por `POST /avaliacoes`, autenticada com `Authorization: Bearer <JWT>`. O cliente
envia **apenas o que observa em campo** — posição, telemetria, tipo de operação, dados do operador
e da última manutenção. Não envia nada que possa forjar o resultado: o cadastro do equipamento e a
faixa de risco são resolvidos pelo servidor.

Na Entrega 3 a origem é o simulador de telemetria (`scripts/simulate_telemetry.py`), que emite
leituras contra a API. O app móvel com ESP32 via BLE permanece como evolução futura — o enunciado
aceita explicitamente *"por simulação ou por dispositivos reais"*.

#### 2. Validação ✅

`backend/api/schemas.py` valida com Pydantic antes de qualquer escrita. Cada campo tem faixa
declarada — latitude entre −33,75 e −2,50, velocidade entre 0 e 40 km/h, `equipamento_id` no
padrão `EQ-9999`, e assim por diante. Payload fora de faixa recebe **`422`** com o campo e o
motivo, e **não é persistido**.

O schema também **recusa campo desconhecido** (`extra="forbid"`) em vez de descartar em silêncio.
Isso vale para os campos que o servidor deriva — `faixa_risco`, `atraso_manutencao_pct`,
`manutencao_atrasada`: enviá-los é erro, não é ignorado. É o que impede um cliente de forjar o
resultado passando o campo já pronto.

Além das faixas, a leitura precisa ser **consistente entre campos**, pelas regras de
[`docs/data schema.md`](docs/data%20schema.md), e é recusada com **`422`** sem persistir se não for:

| Regra | Recusa |
|---|---|
| 4 | operação `parado` com velocidade maior que zero |
| 5 | `condicao_clima` incompatível com `precipitacao_mm` (ex.: tempestade sem chuva) |
| 1 e 10 | `temperatura_motor` para equipamento sem IoT, ou para implemento, que não tem motor próprio |

As duas primeiras dependem só do payload e ficam no schema. A terceira depende do cadastro e é
checada no serviço, depois de buscar o equipamento. As faixas de velocidade por tipo de operação
da Regra 4 **não** são impostas: descrevem a distribuição do dataset simulado, e uma colheita a
9 km/h é plausível no campo.

#### 3. Complemento cadastral ✅

O servidor busca no banco o que não vem no payload: tipo, modelo, idade, histórico de sinistros,
`tem_iot` e os intervalos de manutenção recomendados pelo fabricante. A partir disso **deriva**
`atraso_manutencao_pct` e `manutencao_atrasada`, seguindo a Regra 14 do schema de dados.

Equipamento ou operador inexistente interrompe o fluxo com **`404`**, antes de qualquer escrita.

#### 4. Enriquecimento climático ✅

Os cinco campos climáticos (`temperatura_ar`, `precipitacao_mm`, `umidade_solo`,
`velocidade_vento`, `condicao_clima`) são **opcionais**, e **o clima medido em campo prevalece**:
com os cinco no payload, a Open-Meteo nem é consultada (`clima_origem='payload'`). Sem nenhum, o
servidor busca na Open-Meteo pela coordenada, com timeout curto (`OPENMETEO_TIMEOUT_S`), e marca
`open-meteo`. Com parte deles, a Open-Meteo completa o que falta e a origem fica `misto`. A chuva
da Open-Meteo é a soma das últimas 24 horas; umidade do solo e condição são derivadas dela pelas
mesmas regras do dataset de treino.

**Quando falham os dois** — Open-Meteo fora *e* payload sem clima completo — a requisição é
recusada com **`502`**, listando os campos ausentes. O servidor não inventa clima para alimentar o
modelo: um score derivado de dado fabricado é pior que score nenhum.

#### 5. Vetor de 30 features ✅

`backend/ml/preprocess.py` converte o registro validado e enriquecido, ainda em memória, no vetor
que o modelo espera, na ordem declarada em `models/features.json`, aplicando o encoder ajustado no
treino.

O ponto importante é que treino e inferência não podem divergir. Divergência de pré-processamento
é a classe de bug que não aparece em teste unitário e envenena silenciosamente toda predição em
produção. Na inferência, `preprocess_features()` é o único caminho: a API, o script de predições em
lote, os testes e o próprio treino passam por ela. O treino só acrescenta um passo antes:
**ajustar** o encoder (`ajustar_encoder()`), que a inferência depois apenas aplica.

#### 6. XGBoost → score ✅

O modelo é carregado **uma vez no startup**, não a cada requisição, e devolve um score contínuo de
0 a 100. A faixa vem de `derive_faixa()`: `≤33` baixo, `≤66` médio, acima disso alto, derivada do
score cru e gravada junto com ele, já arredondado a duas casas. O servidor é a única fonte da
faixa: as rotas de consulta devolvem a faixa gravada, sem recalcular a partir do score
arredondado, o que divergiria logo acima de 33 e de 66.

#### 7. SHAP → explicação ✅

Sobre a mesma predição, o SHAP decompõe o score em contribuições por feature, agregadas em seis
grupos: ambiental, geográfico, operacional, equipamento, operador e manutenção.

A soma preserva o **sinal**: contribuição positiva empurra o risco para cima, negativa puxa para
baixo. É o que permite a leitura *"este equipamento pontuou alto apesar do operador, por causa da
proximidade de água"* — que é a informação acionável, não o número sozinho.

#### 8. Persistência da avaliação ✅

Só com score e explicação calculados a leitura vira uma linha em `avaliacoes`, já com o
`risco_score` e a `faixa_risco` que o modelo produziu. Se o modelo falhar, nada foi gravado.
Avaliação e predição são gravadas numa **transação só**: se qualquer uma falhar, nenhuma fica, e
nada fica órfão.

**Reenvio não duplica.** O cliente pode mandar um `leitura_id` (UUID gerado antes do primeiro
envio e reusado no retry). Reenvio com o mesmo payload devolve `200` com o resultado original, sem
gravar; o mesmo `leitura_id` com payload diferente é `409`. O reenvio é decidido antes de consultar
o clima ou rodar o modelo.

**Procedência** — duas colunas criadas em
`supabase/migrations/20260824120000_entrega03.sql` tornam a origem auditável sem cruzar log com
banco:

| Coluna | Valores | Responde a |
|---|---|---|
| `fonte` | `seed` · `telemetria` | O registro veio da carga inicial ou de uma leitura real? |
| `clima_origem` | `seed` · `open-meteo` · `payload` | O clima foi buscado na API, ou é o fallback? |

Sem elas, as 5.000 linhas do seed e as geradas pela API ficam indistinguíveis — e um score
calculado com clima de fallback pareceria idêntico a um calculado com clima medido.

> A estrutura do banco vive só em `supabase/migrations/`, aplicadas em ordem de nome a partir de
> `20260527000000_base.sql`, que substituiu o antigo `backend/db/schema.sql` (removido porque
> começava com `DROP TABLE`). Todas são aditivas e idempotentes e não destroem nada. Com a CLI
> logada: `supabase db push --linked`.

#### 9. Persistência da predição ✅

O resultado vira uma linha em `predicoes`, ligada à avaliação por `avaliacao_id`, contendo score,
faixa, os top fatores SHAP em JSONB e a **versão do modelo** que a gerou.

Guardar `modelo_versao` é o que torna o histórico auditável: uma predição de seis meses atrás
continua explicável pelo modelo que a produziu, mesmo depois de retreino. O histórico é
append-only — reprocessar não sobrescreve predição anterior.

> **Formato dos fatores SHAP:** as 5.000 predições do seed foram gravadas com a chave `group`
> (inglês) e sem o campo `valor`; as geradas pela API usam `grupo` e `valor`. A API **normaliza na
> leitura** e sempre devolve o formato em português, com `valor` nulo quando a predição é do seed.
> Sem essa normalização a interface quebraria em silêncio conforme o equipamento aberto.

#### 10. Registro de uso ✅

Duas trilhas paralelas, atendendo ao RF-08.

**Log estruturado** (`backend/core/logging.py`) — cada linha carrega um `request_id` propagado por
`ContextVar`, correlacionando a entrada da requisição, a decisão do modelo e a resposta. Um erro
de produção é rastreável de ponta a ponta por esse identificador.

**Tabela `auditoria`** (`backend/services/auditoria.py`) — registra quem pediu, quando, para qual
equipamento, qual score saiu, qual versão do modelo decidiu e se a operação teve sucesso.

A diferença entre as duas importa: o log responde *"o que aconteceu naquela requisição"* e é
volátil; a tabela responde *"quem é responsável por esta predição"* e é permanente. Governança de
uso de IA exige a segunda.

#### 11. API → interface ✅

O dashboard nunca toca o banco. Ele lê três rotas, todas autenticadas:

| Rota | Alimenta |
|---|---|
| `GET /equipamentos` | Ranking e Top 5 — uma linha por equipamento, já agregada |
| `GET /kpis` | KPIs, distribuição geográfica e agregação por tipo de operação |
| `GET /alertas` | Alertas recentes, filtráveis por faixa mínima |
| `GET /equipamentos/{id}` | Detalhe: última avaliação, predição, decomposição SHAP e histórico |

O contrato completo, capturado da API em execução, está em
[`docs/contrato-api.md`](docs/contrato-api.md); o schema OpenAPI, em
[`docs/openapi.json`](docs/openapi.json).

#### O invariante que sustenta tudo

**Nenhum cliente fala com o banco.** O browser não carrega chave de banco; o acesso é feito
server-side com `service_role`, e a RLS nega leitura anônima. É o que faz do caminho acima o
**único** caminho — não há atalho pelo qual um dado entre sem passar por validação, ou saia sem
passar por autenticação.

---

### 5.8 Stack Tecnológica

| Componente | Tecnologia | Estado |
|---|---|---|
| Backend / API | FastAPI + Uvicorn (Python 3.13) | ✅ em uso |
| Validação de entrada | Pydantic | ✅ faixas e consistência entre campos |
| Autenticação | JWT via PyJWT; senhas em hash scrypt (stdlib) | ✅ em uso |
| Modelo de ML | XGBoost | ✅ em uso |
| Explicabilidade | SHAP | ✅ em uso |
| Rastreabilidade ML | MLflow (`safefield-xgboost`) | ✅ em uso |
| Banco de dados | Supabase (PostgreSQL + RLS) | ✅ em uso |
| Dashboard | React 19 + TypeScript + Vite + Tailwind CSS v4 | ✅ em uso |
| Clima | Open-Meteo (`requests`) | ✅ em uso |
| Simulador de telemetria | Python | ✅ em uso |
| Log e auditoria | `logging` + tabela `auditoria` | ✅ em uso |
| Firmware IoT | ESP32 (DOIT DevKit) — C++ / Arduino | 📋 especificado, fora de escopo |
| Sensores | MPU-6050 GY-521, DS18B20, LM2596 | 📋 especificado, fora de escopo |
| OBD-II | ELM327 Bluetooth | 📋 especificado, fora de escopo |
| App Móvel | React Native ou Flutter | 📋 futuro |
| Deploy | execução local nesta entrega | 📋 futuro |

---

## 6. Modelo Preditivo

### 6.1 Abordagem

O modelo utiliza **XGBoost para regressão**, gerando um score contínuo de risco de 0 a 100 por equipamento e contexto operacional. A partir desse score, são derivadas três faixas categóricas (baixo, médio, alto) que determinam o tipo de resposta do sistema — informativo, alerta ou recomendação de ação.

### 6.2 Justificativa do XGBoost

O XGBoost foi escolhido por três razões principais. Primeiro, lida bem com variáveis mistas (numéricas e categóricas) e dados tabulares, que é exatamente o formato do dataset do projeto. Segundo, é robusto a valores faltantes — importante porque equipamentos sem IoT terão campos como `vibracao_g` e `temperatura_motor` ausentes. Terceiro, tem excelente relação entre desempenho preditivo e custo computacional, viabilizando inferência rápida em uma API com recursos limitados.

### 6.3 Entradas e Saídas

**Entradas:** features ambientais, geográficas, operacionais, do equipamento, do **operador** (perfil comportamental histórico) e de **manutenção** (atraso em relação ao intervalo recomendado) — detalhadas na [seção 4](#4-estruturação-dos-dados). Total: **30 features de entrada** (das 37 colunas do dataset, excluídas IDs, timestamp e targets).

**Saídas:** score de risco (0–100), faixa de risco (baixo/médio/alto, derivada do score cru e gravada), decomposição SHAP por grupo, top 5 fatores e **recomendações preventivas** — cada uma com o público que age (operador, gestor, técnico) e o critério explícito que a disparou, com os valores da leitura. As recomendações vêm de regras determinísticas (`backend/services/recomendacoes.py`), nunca de texto gerado.

**Desempenho atual** (test set de 1.000 registros, 20% do dataset — valores em [`models/metrics.json`](models/metrics.json)):

| Métrica | Valor | Leitura |
|---|---|---|
| MAE | 4.67 | Erro médio de ~5 pontos no score de 0–100 |
| RMSE | 6.04 | Penaliza os desvios grandes; próximo do MAE indica poucos outliers |
| R² | 0.9473 | O modelo explica ~95% da variância do score |
| Acurácia por faixa | 89.1% | Acerto na classificação baixo / médio / alto |

Treino: 4.000 registros · 30 features de entrada.

Esses são os números de **referência**, gerados no retreino da Entrega 3; o arquivo registra a
plataforma e as versões. Retreinar em outra plataforma, com o mesmo código, a mesma semente e as
mesmas versões, dá números ligeiramente diferentes (no Windows x86: MAE 4.72, acurácia 88.7%),
sempre dentro dos critérios de aceite. Por isso `train.py` grava por padrão em
`models/metrics.local.json`, ignorado pelo Git, e só atualiza a referência com `--referencia`.

**Dívida conhecida (D4).** `historico_sinistros` domina a explicação e as features de operador e
manutenção têm peso quase nulo na decomposição. A recalibração (S4-17) ficou fora desta entrega por
decisão de prioridade; está registrada, não escondida.

### 6.4 Explicabilidade com SHAP

O SHAP (SHapley Additive exPlanations) é aplicado sobre cada predição individual para decompor o score nos fatores que o geraram. Isso atende diretamente às user stories da Sompo, que exigem resultados explicáveis para sustentar conversas técnicas com clientes e áreas internas, e trilha de auditoria para governança do uso de IA. A decomposição por grupo (ambiental, geográfico, operacional, equipamento, operador, manutenção) permite exibir "dos 74 pontos, 45 vêm do ambiente, 18 do operador e 11 da manutenção".

**Importância global das features.** Cada ponto é um registro do test set; a posição no eixo X é o quanto aquela feature empurrou o score daquele registro para cima (direita) ou para baixo (esquerda). O driver dominante é `historico_sinistros` (mean |SHAP| = 18.58), seguido por horas de operação e distância do corpo d'água.

<p align="center">
  <img src="data/shap_summary_beeswarm.png" alt="SHAP beeswarm — importância global das features" width="700">
</p>

**Decomposição de uma predição individual.** O mesmo mecanismo aplicado a um único equipamento classificado como risco alto: partindo da média do dataset (E[f(X)] = 47.6), o histórico de sinistros sozinho adiciona +41.5 pontos, levando o score final a 87.3. É essa cadeia que a API devolve — em `POST /avaliacoes` e em `GET /equipamentos/{id}` — não apenas o número.

<p align="center">
  <img src="data/shap_waterfall_alto.png" alt="SHAP waterfall — decomposição de uma predição de risco alto" width="800">
</p>

### 6.5 Exemplo de Saída

Resposta real de `POST /avaliacoes`, capturada da API em execução. O contrato completo está em
[`docs/contrato-api.md`](docs/contrato-api.md).

```json
{
  "avaliacao_id": 5001,
  "equipamento_id": "EQ-0042",
  "risco_score": 69.47,
  "faixa_risco": "alto",
  "contribuicoes_por_grupo": {
    "ambiental": 17.7577,
    "geografico": 12.0574,
    "operacional": -2.0559,
    "equipamento": -4.9901,
    "operador": -0.9026,
    "manutencao": -0.0194
  },
  "top_fatores": [
    { "feature": "distancia_agua_m", "valor": 120.0, "shap_value": 11.5357, "grupo": "geografico" },
    { "feature": "precipitacao_mm",  "valor": 42.0,  "shap_value": 11.3671, "grupo": "ambiental" }
  ],
  "modelo_versao": "xgboost-v1-baseline",
  "timestamp": "2026-08-24T13:02:53.465989+00:00"
}
```

**O score nunca vem sozinho** (RF-10): sempre acompanhado da faixa, da decomposição por grupo e dos
fatores que o produziram, rotulados em português na interface.

As contribuições somam **com sinal** — positivo empurra o risco para cima, negativo puxa para
baixo. No exemplo, o equipamento pontuou alto por geografia e clima *apesar* do perfil do operador
e do estado de manutenção, que reduziram o score. É essa leitura que sustenta a decisão, e não o
número isolado.

### 6.6 Rastreabilidade com MLflow

Cada treinamento e cada versão do modelo são registrados no MLflow com: parâmetros (hiperparâmetros do XGBoost), métricas (RMSE, MAE, distribuição de erros por faixa), artefatos (modelo serializado, gráficos SHAP globais) e dataset utilizado. Isso permite auditoria completa e rollback para versões anteriores se necessário.

### 6.7 Explicação Contextual (RAG) — fora de escopo

A proposta inicial previa usar os top fatores SHAP para buscar trechos em uma base de conhecimento
técnico simulada e sintetizar recomendações em linguagem natural via LLM, num endpoint `/explain`.

**Isso foi retirado do escopo.** O enunciado desta entrega não menciona RAG, LLM nem geração de
linguagem natural, e restringe a solução às disciplinas do primeiro ano. Construir o componente
consumiria esforço em algo não avaliado.

A explicabilidade exigida pelo RF-10 é atendida pelo SHAP, que já entrega a decomposição por grupo
e os fatores rotulados. A camada de linguagem natural permanece como evolução possível.

### 6.8 Evolução Futura

Na fase de protótipo, o modelo será treinado com dados simulados (~5.000 registros). Conforme dados reais forem coletados via app e IoT, o modelo poderá ser retreinado incrementalmente. A arquitetura também permite substituir ou complementar o XGBoost com outros modelos (LightGBM, redes neurais) sem alterar a interface da API.

---

## 7. Evolução ao Longo das Quatro Sprints

| Dimensão | Sprint 1 · Fundação | Sprint 2 · Modelo | Sprint 3 · Integração | Sprint 4 · Consolidação |
|---|---|---|---|---|
| Dados | dataset v1, EDA inicial | dataset de 37 colunas; Supabase com 4 tabelas | ingestão por API, com procedência (`fonte`, `clima_origem`) | consistência cruzada na entrada; clima medido em campo prevalece; reenvio idempotente por `leitura_id` e gravação atômica |
| Modelo | — | XGBoost + SHAP por grupo; MLflow | inferência por requisição, modelo carregado no startup | pré-processamento único entre treino e inferência; métricas de referência versionadas |
| Backend | — | FastAPI declarado, sem rotas | API integradora: 7 rotas, validação, scoring e persistência | recomendações, tendências por eixo, 503 previsível, `request_id` |
| Segurança | — | chave do banco no bundle do browser | JWT; nenhum cliente fala com o banco | usuários com hash scrypt, escopo por perfil, CSP, auditoria de cada decisão |
| Interface | — | dashboard com 3 telas lendo o banco | as mesmas 3 telas lendo a API | relatórios de tendência, recomendações no Detalhe, leitura por perfil, robustez a falhas |
| Qualidade | primeira suíte de testes | testes do modelo e do SHAP | testes de integração da API | CI com lint, testes e auditoria de dependências, backend em Ubuntu, Windows e macOS; setup validado em clone limpo |

### O que a Sprint 4 consolidou

A Sprint 3 fez os componentes conversarem; a Sprint 4 tornou a conversa **confiável e útil para
cada perfil**:

- **Confiabilidade.** Leitura incoerente é recusada (`422`) antes de gravar; falha previsível responde
  `503` com `request_id`; o dashboard trata API fora do ar, lenta, resposta malformada e sessão
  expirada com mensagem e recuperação.
- **Segurança e rastreabilidade.** Credenciais fora do `.env`, perfis com recorte real nas rotas e
  uma linha de auditoria por decisão.
- **Valor ao usuário.** Recomendações com critério explícito, tendência de risco nos três eixos que o
  enunciado pede e uma tela de entrada para cada perfil (analista, gestor, técnico, operador).
- **Reprodutibilidade.** Versões fixadas, CI em todo PR com o backend testado em Ubuntu, Windows
  e macOS, o "Como rodar" corrigido a partir de um clone limpo e um roteiro de demonstração
  (`scripts/demo.sh`) que roda também no Git Bash do Windows.

---

## 8. Estado Final, Decisões de Escopo e Dívidas

### Decisões de escopo

| Item | Decisão | Motivo |
|---|---|---|
| RAG / LLM | fora | Restrito às disciplinas do primeiro ano; a recomendação por regra determinística atende o requisito com critério explícito (ver 6.7) |
| App móvel | fora | O enunciado aceita relatórios e dashboards; a interface é o dashboard web |
| Firmware ESP32 físico | fora | O enunciado aceita entradas reais **ou simuladas**; o simulador cobre a ingestão (hardware especificado em [`docs/references/`](docs/references/)) |
| Shapefiles do IBGE | fora | Solo, distância de água e declividade já vêm no dataset; não há exigência de enriquecimento geográfico em tempo real |
| Deploy em nuvem | fora | O enunciado exige execução reproduzível, não hospedagem: execução local + CI |
| Simulador e UBI | "Em breve" | Não citados no enunciado; ficam visíveis como próximos passos, sem dado fictício passando por real |

### Dívidas conhecidas

- **D4 — calibração do modelo** (seção 6.3): operador e manutenção com peso quase nulo.
- **Revogação de sessão:** desativar um usuário só vale no próximo login.
- **Telas com dados reais nas evidências** dependem do banco configurado; os cenários de falha já estão registrados.

### Evidências

- Front, falhas da API: [`docs/evidencias/front/`](docs/evidencias/front/)
- Backend: `docs/evidencias/` (BRA-461, em andamento)
- Contrato da API, conferido contra o código: [`docs/contrato-api.md`](docs/contrato-api.md)
- Requisitos da Sprint 4 e estado de cada um: [`docs/spec-sprint-04.md`](docs/spec-sprint-04.md)

### Divisão de Responsabilidades

| Responsável | Frente Principal |
|---|---|
| Guilherme | Backend (FastAPI), modelo de ML (XGBoost/SHAP), segurança, arquitetura geral |
| Kainan | Dashboard React, integração com a API, leitura por perfil, evidências do front |
| Ambos | Documentação, testes integrados, revisão cruzada, apresentação |

### Ferramentas de Gestão

O acompanhamento é feito no **Linear**, com uma issue por requisito da sprint, responsável definido
e relações de bloqueio. Cada issue vira uma branch e um Pull Request revisado pelo outro integrante
antes do merge; a CI roda lint, testes e auditoria de dependências em todo PR.

---
## 9. Vídeo de Apresentação

🔗 **Sprint 4:** _link a incluir após a gravação (não listado no YouTube)._

> Vídeos das entregas anteriores: Sprint 3 em https://youtu.be/Wy_LPCzjrlQ · Sprint 2 em
> https://youtu.be/lLwrnie-Qmk.

---

## 10. Equipe

| Nome | RM |
|---|---|
| Guilherme Avila | 571294 |
| Kainan | 570594 |

---


