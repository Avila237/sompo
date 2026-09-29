# Spec — Sprint 4 (Challenge Sompo): MVP consolidado e validado

> **Fonte normativa:** enunciado "Entrega Sprint 4", fornecido pela FIAP/Sompo e versionado em
> [`references/Sprint4 Sompo.md`](references/Sprint4%20Sompo.md). Este documento é a especificação
> derivada desse enunciado. Onde houver conflito entre esta spec e qualquer outro documento do
> repositório, **esta spec prevalece**.
>
> **Data de entrega:** não informada no enunciado.
> **Escopo desta spec:** requisitos e critérios de aceite. O plano de execução vive no Linear
> (projeto SafeField, milestone **SPRINT 4**, tasks S4-01 a S4-32).

---

## 1. Objetivo da entrega

A Sprint 3 fez os módulos conversarem. A Sprint 4 pede que essa conversa seja **confiável**:

> *"Um sistema que funciona uma vez, no ambiente de quem o desenvolveu, ainda não é uma solução;
> ele só se torna uma quando o fluxo de ponta a ponta é reproduzível, quando trata as exceções do
> mundo real, quando os dados que entram são consistentes e quando as saídas sustentam uma decisão
> preventiva."*

O critério de julgamento declarado é *"clareza, viabilidade técnica, coerência das escolhas e
organização do repositório"*. Não se espera produto comercial, e sim um MVP consistente que
demonstre viabilidade técnica, rastreabilidade e aderência às user stories escolhidas na Sprint 1
(README §3).

**Meta declarada:** a solução completa prometida ao cliente, e não mais ~60% dela como na Entrega 3.

---

## 2. Restrições de arquitetura

As restrições R1–R4 da Entrega 3 ([`spec-sprint-03.md`](spec-sprint-03.md) §2) continuam valendo:

| # | Restrição | Estado |
|---|---|---|
| R1 | O dashboard consome a API do backend, nunca o banco | mantida — é o invariante "nenhum cliente fala com o banco" |
| R2 | Telemetria por simulador Python + Open-Meteo real | mantida |
| R3 | Backend em Python orquestrando o fluxo | mantida |
| R4 | Restrito às disciplinas do primeiro ano (sem LLM, RAG, embeddings) | o enunciado da S4 não a repete; mantida por coerência e porque recomendação precisa de critério explícito, não de texto gerado |

---

## 3. Numeração

Os requisitos desta sprint usam o prefixo **R4-**, para não colidir com os RF-01 a RF-14 da
Entrega 3, que seguem referenciados no README e no Linear.

**Divergência herdada da Entrega 3.** A partir de RF-11, a numeração de
[`spec-sprint-03.md`](spec-sprint-03.md) e a de
[`spec-implementacao-entrega-03.md`](spec-implementacao-entrega-03.md) divergem:

| Número | `spec-sprint-03.md` (normativa) | `spec-implementacao-entrega-03.md` e Linear |
|---|---|---|
| RF-11 | README atualizado | Testes da integração |
| RF-12 | Diagrama atualizado | README e diagrama |

A spec normativa prevalece. A de implementação acrescentou um requisito de testes que o enunciado
da E3 não pedia e deslocou os seguintes. Os dois documentos ficam como estão, por serem registro
histórico da entrega, e esta nota é a referência para quem ler os dois.

---

## 4. Requisitos

Cada requisito traz a origem no enunciado, o critério de aceite, o estado no fim da sprint
(28/09/2026) com a evidência que o sustenta, o estado no início da sprint e as tasks que o atendem.
O diagnóstico inicial completo está na primeira versão desta spec (`3c49b6b`).

**Legenda de estado:** ✅ atendido · 🟡 parcial · ❌ ausente

---

### Refinamento do código e da arquitetura

#### R4-01 · Código modular e arquitetura documentada

**Origem:** *"código Python organizado em módulos e funções padronizadas, com a arquitetura do
sistema documentada e o fluxo de execução claro do início ao fim"*

**Aceite:** a direção de dependência declarada (api → services → ml/db; core ← todos) é respeitada
sem exceção; nenhuma regra de negócio tem duas implementações; a documentação de arquitetura
descreve o código que existe.

**Estado:** 🟡 parcial
- `api` deixou de importar `ml` (#18, `4c0c514`). A faixa sai só de `derive_faixa()`
  (`backend/ml/preprocess.py`), e as consultas e o dashboard usam a faixa gravada, sem
  reclassificar (#20, `b2bc872`; #23, `4e119ce`).
- `context.md` reescrito para o código real (`1608139`) e atualizado junto com ele até o #46;
  dashboard refatorado (S4-24, via #24 `87827df`) e scripts one-off removidos (`cd734d2`).
- **Falta:** `api/main.py` importa `banco_indisponivel` de `db.repository`, pulando `services`
  (`cd0643e`); `db/supabase_client.py`, usado pelos scripts de carga, segue lendo o ambiente fora
  de `core.config`; o dashboard repete os limiares 33/66 em `faixaDaMedia`
  (`dashboard/src/lib/risco.ts`), para colorir médias agregadas que a API não classifica, e nas
  faixas desenhadas dos gráficos e do Simulador.

**Estado no início da sprint:** 🟡 — camadas sem ciclo, mas `api/main.py` e `api/routers/health.py`
importavam `ml` direto, a faixa era derivada em quatro lugares, `db/supabase_client.py` lia o
ambiente fora de `core.config` e `context.md` descrevia a Sprint 2.

**Tasks:** S4-02, S4-16, S4-21, S4-24, S4-32

#### R4-02 · Exceções e validação de entrada

**Origem:** *"tratamento de exceções e validações que garantam um fluxo estável e reproduzível, sem
interrupções diante de entradas ausentes, inválidas ou fora do padrão esperado"*

**Aceite:**
- Payload inconsistente é recusado com erro descritivo e não persiste.
- Dependência indisponível (modelo, banco, Open-Meteo) produz resposta tratada e registrada.
- Nenhuma falha deixa registro em estado intermediário.
- A interface não trava nem quebra diante de API lenta, fora do ar ou com resposta malformada.

**Estado:** ✅ atendido
- Leitura com campos que se contradizem (Regras 1, 4, 5 e 10) é recusada com 422 sem gravar (#16,
  `4a99c06`; `TestConsistenciaDoPayload` em `tests/test_confiabilidade_coleta.py`).
- Modelo ou banco fora respondem 503 com `request_id`, e não 500 (#18, `4c0c514`; `cd0643e` para o
  PostgREST sem Postgres; `tests/test_falhas.py`). Avaliação e predição são gravadas numa transação
  só, pela função `registrar_avaliacao`, sem avaliação órfã (#35, `a1dc9c9`).
- No dashboard: timeout de 15 s sobre a requisição inteira, resposta malformada legível,
  `ErrorBoundary` e "Tentar de novo" (S4-23, via #24 `87827df`; #23, `4e119ce`), com os cenários de
  falha em `docs/evidencias/front/` (#34, `f449e93`).

**Estado no início da sprint:** 🟡 — faixas por campo e campo desconhecido já davam 422, mas faltavam
a validação cruzada, o 503 de modelo e banco (as exceções existiam e nunca eram levantadas), uma
gravação que não deixasse avaliação sem predição e timeout e ErrorBoundary no dashboard.

**Tasks:** S4-13, S4-14, S4-21, S4-23

#### R4-03 · Execução reproduzível

**Origem:** *"fluxo de ponta a ponta funcionando de forma estável e reproduzível"* (§5.1) · *"um
sistema que funciona uma vez, no ambiente de quem o desenvolveu, ainda não é uma solução"* (§1)

**Aceite:** um clone limpo, seguindo só o README, sobe API, dashboard e simulador e roda a suíte
verde em Windows e macOS, com as mesmas versões de dependência nas duas máquinas; a CI confirma a
cada push.

**Estado:** 🟡 parcial
- `.env.example` completo, com a API recusando segredo JWT fraco (#7, `044e9f9`); versões exatas e
  `.python-version` 3.13 (#12, `762d901`).
- CI em todo PR e em todo push na `main`, com lint, testes, auditoria de dependências e checagem de
  árvore limpa (#15, `6bd5d5e`); o job de backend roda em Ubuntu, Windows e macOS, e o `demo.sh`
  ficou portátil para o Git Bash (#47, `be30a8d`).
- Clone limpo no macOS seguindo só o README (BRA-467), com os desvios corrigidos (#36, `803e609`;
  #37, `2a9e934`).
- **Falta:**
  - a validação manual no Windows (BRA-442, em andamento): clone limpo pelo README, com API,
    dashboard, simulador e `demo.sh` no Git Bash. No Windows, a CI cobre só o backend;
  - o clone limpo no macOS (BRA-467) não exercitou o simulador nem o `demo.sh`;
  - as dependências transitivas não estão fixadas: `backend/requirements.txt` fixa só as diretas.

**Estado no início da sprint:** ❌ — toda a validação da E3 tinha sido no macOS, o `.env.example`
omitia uma variável obrigatória (`DEMO_USERS`, aposentada no #38), o `requirements.txt` fixava só a
major, o `scripts/demo.sh` só rodava em Unix e não havia CI.

**Tasks:** S4-06, S4-07, S4-08, S4-09, S4-10

---

### Engenharia de dados e modelo

#### R4-04 · Acesso ao banco e pipelines íntegros

**Origem:** *"refinamento do acesso ao banco de dados e dos pipelines, com tratamento de
inconsistências, dados faltantes e duplicidades antes do consumo pelo modelo"* · *"estrutura final
do banco, pipelines de dados tratados"* (§5.1)

**Aceite:**
- Reenviar uma leitura nunca cria segunda linha.
- Cada avaliação tem no máximo uma predição por versão de modelo.
- Ausência de dado é exibida como ausência, não como valor.
- A estrutura final do banco está documentada num lugar só, que não apaga dados.

**Estado:** ✅ atendido
- Reenvio com o mesmo `leitura_id` devolve 200 com o resultado original, e a mesma chave com outro
  payload dá 409; `UNIQUE` em `avaliacoes.leitura_id` e em `predicoes (avaliacao_id,
  modelo_versao)`, gravação atômica e `predicao_de` ordenado pela mais recente (#35, `a1dc9c9`;
  migration `20260928120000`; `tests/test_idempotencia.py`).
- Estrutura do banco só em `supabase/migrations/`, a partir de `20260527000000_base.sql`, sem
  `DROP`; o seed recusa rodar com dados e nunca apaga (#45, `470a62e`). Equipamento sem avaliação
  aparece como "sem avaliação" (#6, `10ef828`), e a decomposição SHAP por grupo é gravada (#35).
- Contra o banco real, 20 leituras, 5 delas reenviadas depois de a resposta ser descartada,
  terminam em 20 avaliações e 20 predições, sem órfã nem duplicata
  (`docs/evidencias/backend/coleta_real.txt`).
- Limite: o aceite "reenviar nunca cria segunda linha" vale para quem envia `leitura_id`, que é
  opcional no contrato por decisão; sem ele não há deduplicação (o simulador e os scripts sempre o
  enviam); as 5.000 predições do seed ficam sem a decomposição completa, por decisão medida
  (BRA-448); `populate_predictions.py` grava por upsert, mas com `--reset`, opção explícita e
  marcada como destrutiva, apaga todas as predições antes.

**Estado no início da sprint:** ❌ — `POST /avaliacoes` não era idempotente, `predicoes` não tinha
unicidade por avaliação, `predicao_de` usava `limit(1)` sem ordem, equipamento sem avaliação
aparecia como score 0 e faixa "baixo", o seed mandava executar um `schema.sql` que começava com
`DROP` e a decomposição SHAP por grupo não era persistida.

**Tasks:** S4-12, S4-13, S4-15, S4-16, S4-22

#### R4-05 · Ajuste final do modelo

**Origem:** *"ajuste final do modelo preditivo, com revisão de variáveis e avaliação de desempenho
por métricas adequadas ao problema, justificando as escolhas realizadas"*

**Aceite:** as variáveis prometidas pela solução (perfil do operador, manutenção) têm peso material
na explicação do modelo; as métricas incluem o erro que importa para a seguradora (recall da faixa
alta); treino e inferência usam a mesma função de pré-processamento; cada predição é distinguível
pela versão do modelo que a gerou.

**Estado:** 🟡 parcial
- Treino e inferência passam pelo mesmo `preprocess_features()` (`739e70f`).
- Cada predição nova é distinguível pela versão: a API grava `xgboost-v1.1`, e o seed segue
  `xgboost-v1-baseline` (#48, `d680bcd`; tabela de versões em `docs/contrato-api.md`). As
  predições das avaliações 5040–5044, feitas nos smokes antes do #48, ficaram com o rótulo antigo e
  não foram reescritas (`docs/evidencias/README.md`, Limites).
- Métricas de referência versionadas com a proveniência em `models/metrics.json` (#12, `762d901`) e
  justificadas no README §6.3.
- **Falta:** a recalibração D4 (S4-17), que saiu da entrega pela decisão abaixo (BRA-450): operador
  e manutenção seguem com peso quase nulo na explicação, registrado como dívida no README (§6.3 e
  §8). O recall da faixa alta ficou de fora junto com ela.

**Estado no início da sprint:** ❌ — `historico_sinistros` respondia por ~44% da explicação SHAP, e
operador e manutenção somavam ~6%; `train.py` reimplementava o pré-processamento em vez de chamar
`preprocess_features()`; modelos diferentes gravavam predições com o mesmo `modelo_versao`.

> **Decisão de priorização (28/09/2026):** a recalibração (S4-17) fica por último, se der tempo,
> porque dispara a cascata dataset → treino → SHAP → figuras → banco → testes. Se não entrar, o
> README final registra este requisito como dívida conhecida, com a medição de peso SHAP já feita,
> e justifica as métricas do modelo atual como estão.

**Tasks:** S4-05, S4-17

---

### Validação da integração com fontes de dados

#### R4-06 · Operação consistente com as fontes

**Origem:** *"verificação de que a solução opera de forma consistente com entradas reais ou
simuladas de telemetria, ambiente e operação, sem perda ou corrupção de dados"*

**Aceite:** o valor gravado de cada campo climático corresponde ao que a fonte informou, com a
origem registrada; o simulador produz entradas dentro da distribuição que o modelo viu no treino;
retry do cliente não duplica nem perde leitura.

**Estado:** ✅ atendido
- O clima medido em campo prevalece, a Open-Meteo só completa o que falta, e `clima_origem` registra
  `payload`, `open-meteo` ou `misto`; a chuva da Open-Meteo é a soma das últimas 24 h (#31,
  `6056c55`; `tests/test_clima.py`).
- O simulador deriva umidade do solo e condição pelas mesmas funções do serviço (Regras 3 e 5,
  #31) e repete 502 e 503 com o mesmo `leitura_id` (`252307c`), sem perder leitura
  (`TestSimuladorNaoPerdeLeitura`).
- Contra o banco real, a entrada gravada confere campo a campo com a enviada, com a procedência
  registrada (`docs/evidencias/backend/coleta_real.txt`).

**Estado no início da sprint:** 🟡 — o simulador, a Open-Meteo e o fallback funcionavam, com
`clima_origem` gravado, mas a chuva era a de ontem em UTC, o clima medido em campo era descartado
com a Open-Meteo no ar e o simulador calculava a umidade do solo por fórmula diferente da Regra 3.

**Tasks:** S4-12, S4-20

#### R4-07 · Testes de confiabilidade da coleta

**Origem:** *"testes de confiabilidade da coleta e de consistência das informações, demonstrando
que os dados que alimentam o modelo são íntegros e rastreáveis"*

**Aceite:** um teste envia N leituras com falhas injetadas e confirma exatamente N avaliações e N
predições, sem órfãs nem duplicatas; toda asserção agregada verifica que o conjunto não é vazio; a
suíte não altera arquivos versionados.

**Estado:** ✅ atendido
- `tests/test_confiabilidade_coleta.py` envia 24 leituras com 5 tipos de falha injetados (Open-Meteo
  fora, banco fora antes e depois do commit, PostgREST sem Postgres, resposta perdida no cliente) e
  confirma 24 avaliações e 24 predições, sem órfã nem duplicata (#51, `7185239`; saída em
  `docs/evidencias/backend/pytest-confiabilidade.txt`).
- As asserções agregadas exigem conjunto não vazio e calculam percentuais sobre a contagem real, e
  os testes que dependem do banco levam o marker `rede` (#43, `d38066f`; #10, `705490a`). Contra o
  banco real, `pytest -m "rede and not seed"` dá 22 passed (`docs/evidencias/backend/pytest-rede.txt`).
- A suíte não sobrescreve artefatos versionados (#8, `716861d`), e a CI falha se a árvore sujar
  depois dos testes (#15, `6bd5d5e`).

**Estado no início da sprint:** ❌ — não havia teste de confiabilidade da coleta, e a suíte tinha
testes que passavam sobre conjunto vazio, testes intermitentes, testes que dividiam por 5.000 fixo e
sobrescrevia `models/shap_values.npy` e as figuras SHAP versionadas.

**Tasks:** S4-11, S4-28

---

### Segurança e rastreabilidade

#### R4-08 · Proteção de dados e controle de acesso

**Origem:** *"boas práticas de proteção de dados, controle de acesso e integridade das informações
aplicadas ao sistema em condição de uso"*

**Aceite:**
- Cada perfil acessa só o que a matriz de permissões define, com teste por perfil × rota.
- Nenhuma credencial vive em variável de ambiente.
- A aplicação recusa subir com segredo fraco.
- Nenhuma dependência tem vulnerabilidade conhecida.

**Estado:** ✅ atendido
- Usuários na tabela `usuarios`, com senha em hash scrypt e nenhuma credencial de usuário no `.env`;
  matriz perfil × rota aplicada na API e testada por perfil (`tests/test_autorizacao.py`), com CSP
  no build do dashboard (#38, `3590986`); minimização LGPD no recorte do operador (#46, `6dbfba1`;
  `tests/test_lgpd_operador.py`).
- A API recusa subir com segredo JWT abaixo de 32 bytes, inclusive o placeholder do exemplo (#7,
  `044e9f9`); `python-jose` trocado por PyJWT e versões fixadas sem vulnerabilidade conhecida no
  `pip-audit` (#12, `762d901`), com `pip-audit` e `npm audit` na CI (#15, `6bd5d5e`).
- Limite de tentativas em `/auth/token` e coordenada truncada no log (#22, `0d44ac5`); `/health` sem
  o texto da exceção (#18, `4c0c514`). As recusas por perfil estão demonstradas em
  `docs/evidencias/backend/casos_de_uso.txt`: as de envio (POST) são auditadas, e as de leitura (GET)
  ficam no log com o `request_id`.
- Limite declarado: o token vale até expirar, e desativar um usuário só vale no próximo login
  (README §5.5 e §8).

**Estado no início da sprint:** 🟡 — JWT em todas as rotas de dado, RLS sem policy para `anon` e
`service_role` só no servidor, mas com credenciais em variável de ambiente (D1), perfil ignorado
pelas rotas (D3), token sem CSP (D9), segredo JWT utilizável no `.env.example`, duas CVEs no
`python-jose` 3.3, login sem limite de tentativas e `/health` expondo o texto da exceção.

**Tasks:** S4-07, S4-08, S4-18, S4-19

#### R4-09 · Registros de uso

**Origem:** *"registros (logs) de uso que permitam rastrear entradas, saídas e decisões do sistema,
sustentando auditoria e explicabilidade do score de risco"*

**Aceite:** toda requisição que decide ou falha, inclusive por dependência externa, deixa registro
em log e em `auditoria`, correlacionável pelo `request_id` presente no header e no corpo da
resposta.

**Estado:** 🟡 parcial
- O 502 de clima e o 503 do modelo gravam auditoria de `erro`, e o 500 leva `X-Request-ID` no
  header e no corpo (#18, `4c0c514`; `tests/test_falhas.py`), legível pelo navegador também no 500
  (#37, `2a9e934`).
- Toda gravação tem uma linha de auditoria (`sucesso` ou, quando o cliente reenvia depois de um
  503 que chegou após o commit, `reenvio`), e a trilha vai do
  `X-Request-ID` ao log, à avaliação, à predição e à auditoria (#51;
  `docs/evidencias/backend/log-correlacionado.txt` e `auditoria.txt`;
  `test_rastreabilidade_pelo_log_de_producao`).
- **Falta:** a recusa no schema (422 do Pydantic, inclusive as Regras 4 e 5 de consistência) não
  grava auditoria nem deixa linha com o `request_id` no log da aplicação; só a resposta leva o
  `X-Request-ID` (`TestConsistenciaDoPayload`). O `request_id` vem no corpo só no 500; nas demais
  respostas de erro (4xx, 502, 503), só no header. Limite declarado e aceito por projeto
  (`docs/contrato-api.md`, auditoria): com o banco fora, a auditoria não grava e nunca derruba a
  operação; a falha fica no log em `ERROR` com o `request_id`
  (`test_falhas_ficam_no_log_pelo_request_id`).

**Estado no início da sprint:** 🟡 — log estruturado com `request_id` e tabela `auditoria` existiam,
mas o 502 de clima e as falhas do banco antes do insert não geravam auditoria, o 500 saía sem
`X-Request-ID` e a falha ao gravar a auditoria só ia para o log, com a requisição seguindo em 201.

**Tasks:** S4-21

---

### Relatórios, alertas e visualização

#### R4-10 · Relatórios de tendência por perfil

**Origem:** *"relatórios e dashboards que apresentem tendências de risco por equipamento, região ou
tipo de operação, com leitura clara para cada perfil de usuário"* · *"prints ou demonstração dos
relatórios e do dashboard"* (§5.1)

**Aceite:** a tendência temporal do score é exibida pelos três eixos, com datas reais; cada perfil
atendido (operador, gestor de frota, técnico, analista da seguradora) tem uma leitura com dados
reais, recortados para ele; nenhum texto, número ou notificação fictícios aparecem na tela.

**Estado:** ✅ atendido
- Tendência do score por equipamento, região e operação, com datas reais: `GET /tendencias` com
  `janela.datas` (#17, `74caff8`; #19, `813b3e8`) e a tela Relatórios (S4-26, via #24 `87827df`).
  A janela conta dias com dados, e a tela e o contrato dizem isso.
- Leitura por perfil com o recorte feito na API: analista e gestor na Visão geral, técnico em
  Manutenção da frota, operador em Meus equipamentos (#40, `3abec59`; #38; #39, `0791c37`). O
  Corretor saiu, porque o enunciado nomeia só esses quatro perfis. Prints contra a API e o banco
  reais em `docs/evidencias/front/`, 10 a 23 (#52, `497561c`).
- Sem texto, número ou notificação fictícios: confirmações simuladas e notificações fixas removidas
  (#6, `10ef828`) e textos fictícios corrigidos (BRA-298, #33 `93d351a`). O Detalhe usa a
  decomposição SHAP gravada e rotula como aproximação a das predições do seed (#35; #43, `d38066f`).

**Estado no início da sprint:** 🟡 — Visão geral, Ranking e Detalhe consumiam a API, mas a tendência
era só global e contava dias com dado como se fossem corridos, Relatórios, Corretor e Técnico eram
mock atrás de "Em breve", não havia visão de operador nem de gestor, a tela mostrava textos e
notificações fictícios e o Detalhe recalculava a decomposição a partir de só 5 fatores.

**Tasks:** S4-15, S4-23, S4-24, S4-26, S4-27, BRA-298

#### R4-11 · Alertas e recomendações com critérios explícitos

**Origem:** *"alertas e recomendações preventivas derivados do score de risco, com critérios
explícitos e interpretáveis pelo usuário final"*

**Aceite:** toda avaliação de faixa média ou alta traz ao menos uma recomendação acompanhada do
critério que a disparou; a regra é determinística, versionada e testada; nenhuma ação é confirmada
na tela sem ter ocorrido.

**Estado:** ✅ atendido
- `recomendacoes` em `POST /avaliacoes` e `GET /equipamentos/{id}`: 12 regras determinísticas em
  `backend/services/recomendacoes.py`, cada recomendação com o público que age e o critério que a
  disparou, e fallback pelo fator SHAP dominante (#26, `93e5098`; #32, `35f8f01`).
- `tests/test_recomendacoes.py` testa o disparo de cada uma das 12 regras e o limiar de quatro
  delas; a garantia de ao menos uma recomendação na faixa média ou alta é testada por construção
  (`TestGarantiaParaMedioEAlto`) e contra o modelo real, numa amostra do dataset.
- No Detalhe, o card abre filtrado no público do perfil (#29, `f8815a1`; #40). Ações sem endpoint
  ficam atrás de `inert`, sem foco por teclado nem mensagem de sucesso (#6, `10ef828`).

**Estado no início da sprint:** 🟡 — `GET /alertas` já existia, com regra no servidor, mas a
recomendação não existia (saíra do escopo com o RAG na E3), e "Disparar alerta" era alcançável por
teclado atrás do overlay e exibia "Alerta enviado ✓" sem enviar nada.

**Tasks:** S4-22, S4-25

---

### Documentação e validação final

#### R4-12 · README final

**Origem:** *"README final com a arquitetura consolidada, o fluxo de ponta a ponta, as instruções
de execução e a justificativa das decisões técnicas tomadas ao longo das quatro Sprints"* ·
*"organização lógica do repositório, instruções de execução e descrição clara da evolução do projeto
ao longo das quatro Sprints, incluindo o link do vídeo"* (§5.1)

**Aceite:** um terceiro sobe o sistema e entende cada decisão lendo só o README; toda afirmação
factual confere com o código; a evolução cobre as quatro sprints; os documentos satélites
(contrato da API, schema de dados, README do dashboard) conferem com o código.

**Estado:** 🟡 parcial
- README final (#41, `9bec7a1`): arquitetura consolidada, caminho do dado salto a salto, "Como
  rodar" corrigido a partir de um clone limpo (#36, `803e609`), evolução das quatro sprints (§7) e
  decisões e dívidas (§8).
- Satélites sincronizados com o código: `docs/contrato-api.md` (`4b6a62f` e os PRs seguintes),
  `docs/data schema.md` (`6050a1b`) e `dashboard/README.md` no lugar do boilerplate do Vite
  (`9f0be04`, via #24).
- **Falta:** o link do vídeo (README §9, depende de R4-15).

**Estado no início da sprint:** 🟡 — o README cobria a E3, contradizia a si mesmo nas métricas,
listava como pendentes campos já implementados, descrevia a ordem persistir → prever e a evolução só
da E2 para a E3; `docs/data schema.md` divergia da fórmula, `contrato-api.md` omitia nulos e códigos
de erro reais, e o README do dashboard era o boilerplate do Vite.

**Tasks:** S4-03, S4-04, S4-05, S4-06, S4-29

#### R4-13 · Diagrama de arquitetura final

**Origem:** *"desenho consolidado do fluxo de ponta a ponta (entrada → banco → modelo → saída),
refletindo a solução efetivamente entregue"*

**Aceite:** o diagrama corresponde ao código entregue na S4, incluindo recomendações, relatórios e
controle de acesso por perfil.

**Estado:** ✅ atendido
- Diagrama Mermaid refeito no README §5.6.1 (#41, `9bec7a1`): prever antes de persistir, Open-Meteo
  consultada só "sem clima no payload", escopo por perfil, recomendações, consultas de tendência,
  tabelas `usuarios` e `auditoria` e a seta cortada do `anon`. A renderização foi conferida no
  Mermaid 11, segundo a BRA-462.

**Estado no início da sprint:** 🟡 — o diagrama Mermaid da E3 mostrava a ordem persistir → prever e
tinha o rótulo "fallback: payload", invertido, na aresta da Open-Meteo.

**Tasks:** S4-03, S4-29

#### R4-14 · Evidências de validação do MVP

**Origem:** *"evidências de validação do MVP (testes, execuções demonstrativas ou casos de uso) que
comprovem o funcionamento integrado da solução"* · *"evidências do controle de acesso, da proteção
dos dados e dos registros de uso"* (§5.1)

**Aceite:** `docs/evidencias/` reúne a saída dos testes, prints das telas, um log correlacionado
por `request_id` e uma consulta à auditoria, com um caso de uso roteirizado por persona; cada
evidência aponta para o teste que a sustenta e pode ser reproduzida pelo avaliador.

**Estado:** ✅ atendido
- `docs/evidencias/README.md` indexa 10 evidências, cada uma com o teste que a sustenta e o comando
  que a reproduz (#51, `cd0643e` a `e2edecd`; #52, `497561c`).
- `docs/evidencias/backend/`: saída dos testes, coleta contra o banco real, log correlacionado por
  `request_id`, consulta à auditoria e um caso de uso roteirizado para cada uma das 4 personas.
  `docs/evidencias/front/`: dashboard sob falhas da API (#34, `f449e93`) e telas reais por perfil
  (#52).
- Limite: a execução registrada usou token assinado localmente (`--token-local`), e reproduzir as
  evidências contra o banco exige as credenciais do Supabase, combinadas fora do repositório; a
  suíte offline roda sem elas.

**Estado no início da sprint:** ❌ — não havia evidência reunida.

**Tasks:** S4-28

#### R4-15 · Vídeo de apresentação

**Origem:** *"vídeo com narração humana demonstrando o MVP em funcionamento de ponta a ponta
(entrada dos dados, geração do score, alertas e relatórios) e explicando a arquitetura final e as
principais decisões técnicas"* · *"até 5 minutos"* · *"não listado"*

**Aceite cumulativo:**
- Até 5 minutos, com narração humana.
- Mostra entrada, score, alertas e relatórios.
- Explica a arquitetura e as decisões técnicas.
- Publicado no YouTube como não listado.
- Link no README.

**Estado:** ❌ ausente — o vídeo não foi gravado (S4-30, BRA-463 em Backlog), e o README §9 traz
"link a incluir após a gravação".

**Estado no início da sprint:** ❌

**Tasks:** S4-30

#### R4-16 · Conformidade do repositório

**Origem:** *"o GitHub deve ser privado e compartilhado apenas com o perfil: fiap-tutoria"* ·
*"Caso o grupo decida manter seu repositório público [...] não precisa convidar o seu tutor como
colaborador, e sim, apenas enviar o link"* · *"não poderá sofrer alterações após a data limite de
entrega"* · manifestação na primeira capa caso o grupo não deseje concorrer ao prêmio

**Decisão (28/09/2026):** o repositório fica **público**, e a entrega vai com o link. O enunciado
permite essa opção (§5.2), e com ela não há convite ao `fiap-tutoria`.

**Aceite:** link do repositório público enviado na entrega; `main` congelada na data limite;
decisão sobre concorrer ao prêmio registrada.

**Estado:** 🟡 parcial
- Repositório público, com a entrega pelo link, pela decisão de 28/09/2026 registrada acima
  (`bf4875d`).
- **Falta:** congelar a `main` na data limite, que o enunciado não informa (S4-31, BRA-464), enviar o
  link na entrega e registrar a decisão sobre concorrer ao prêmio.

**Estado no início da sprint:** 🟡 — o repositório era privado, o convite ao `fiap-tutoria` da E3
(BRA-297) não tinha conclusão registrada e a decisão sobre o prêmio não tinha sido tomada.

**Tasks:** S4-31

---

## 5. Requisitos não funcionais

| # | Requisito | Origem | Estado no fim da sprint · no início |
|---|---|---|---|
| RNF4-01 | Nenhuma falha silenciosa: toda exceção tratada é registrada | *"sem interrupções"*, *"rastrear decisões"* | 🟡 o erro do `/equipamentos` passou a aparecer na tela (`ece3f43`); a falha de auditoria continua indo para o log em `ERROR` sem derrubar a operação, comportamento aceito por projeto (`docs/contrato-api.md`); a recusa no schema não deixa linha no log da aplicação (R4-09) · início: 🟡 falha de auditoria seguia com 201 (igual hoje), e a do `/equipamentos` era engolida no contador |
| RNF4-02 | Toda operação que grava e pode ser reentregue é idempotente | *"sem perda ou corrupção de dados"*, *"duplicidades"* | ✅ `leitura_id`, `UNIQUE` e gravação atômica (#35); seed que nunca apaga (#45); ver R4-04 · início: ❌ |
| RNF4-03 | Toda predição é rastreável à versão do modelo que a gerou | *"integridade das informações"* | 🟡 a API grava `xgboost-v1.1` e o seed segue `xgboost-v1-baseline` (#48); 5 predições anteriores ao #48 ficaram com o rótulo antigo (R4-05) · início: 🟡 modelos diferentes compartilhavam a mesma versão |
| RNF4-04 | Segredos fora do código, do bundle e do exemplo de configuração | *"proteção de dados"* | ✅ os placeholders do `.env.example` têm menos de 32 bytes, e a API recusa subir com eles (#7) · início: 🟡 o exemplo trazia segredo JWT utilizável |
| RNF4-05 | Tela nunca afirma dado, ação ou notificação que não veio da API | *"saídas que sustentam uma decisão preventiva"* | ✅ sem confirmação simulada nem notificação fixa (#6), textos fictícios corrigidos (#33), faixa vinda da API (#23); ver R4-10 e R4-11 · início: ❌ |

---

## 6. Fora de escopo

| Item | Motivo |
|---|---|
| RAG / LLM / base de conhecimento | Restrição R4; recomendação por regra determinística atende R4-11 com critério explícito |
| App móvel | O enunciado aceita *"relatórios e dashboards"*; a interface é o dashboard web |
| Firmware ESP32 físico | O enunciado aceita *"entradas reais ou simuladas"* |
| Integração IBGE (shapefiles) | Dados geográficos já estão no dataset; não há exigência de enriquecimento geográfico em tempo real |
| Deploy em nuvem | O enunciado exige execução reproduzível, não hospedagem; R4-03 é atendido com execução local + CI |
| UBI e Simulador de cenários | Não citados no enunciado; permanecem com overlay "Em breve" |

---

## 7. Rastreabilidade

### Enunciado → requisitos

| Trecho do enunciado (§4 / §5.1) | Requisitos |
|---|---|
| Refinamento do código e da arquitetura | R4-01, R4-02, R4-03 |
| Engenharia de dados e modelo | R4-04, R4-05 |
| Validação da integração com fontes de dados | R4-06, R4-07 |
| Segurança e rastreabilidade | R4-08, R4-09 |
| Relatórios, alertas e visualização | R4-10, R4-11 |
| Documentação e validação final | R4-12, R4-13, R4-14 |
| Entregáveis: vídeo e GitHub | R4-15, R4-16 |

### Tasks → requisitos

| Task | Requisitos | Task | Requisitos |
|---|---|---|---|
| S4-01 spec | esta spec | S4-17 recalibração | R4-05 |
| S4-02 `context.md` | R4-01 | S4-18 autenticação | R4-08 |
| S4-03 README | R4-12, R4-13 | S4-19 hardening | R4-08 |
| S4-04 contrato da API | R4-12 | S4-20 clima | R4-06 |
| S4-05 `data schema.md` | R4-05, R4-12 | S4-21 falhas previsíveis | R4-01, R4-02, R4-09 |
| S4-06 README do dashboard | R4-03, R4-12 | S4-22 falsa confirmação | R4-04, R4-11 |
| S4-07 `.env.example` | R4-03, R4-08 | S4-23 robustez do dashboard | R4-02, R4-10 |
| S4-08 versões | R4-03, R4-08 | S4-24 refactor do dashboard | R4-01, R4-10 |
| S4-09 Windows | R4-03 | S4-25 recomendações | R4-11 |
| S4-10 CI | R4-03 | S4-26 relatórios | R4-10 |
| S4-11 higiene da suíte | R4-07 | S4-27 leitura por perfil | R4-10 |
| S4-12 idempotência | R4-04, R4-06 | S4-28 evidências | R4-07, R4-14 |
| S4-13 unique e compensação | R4-02, R4-04 | S4-29 README final | R4-12, R4-13 |
| S4-14 validação cruzada | R4-02 | S4-30 vídeo | R4-15 |
| S4-15 SHAP por grupo | R4-04, R4-10 | S4-31 conformidade | R4-16 |
| S4-16 faixa única | R4-01, R4-04 | S4-32 scripts one-off | R4-01 |
| BRA-298 textos fictícios | R4-10 | | |

---

## 8. Resumo do estado

| Estado | Fim da sprint (28/09/2026) | Início da sprint |
|---|---|---|
| ✅ atendido | 9: R4-02, R4-04, R4-06, R4-07, R4-08, R4-10, R4-11, R4-13, R4-14 | 0 |
| 🟡 parcial | 6: R4-01, R4-03, R4-05, R4-09, R4-12, R4-16 | 10: R4-01, R4-02, R4-06, R4-08, R4-09, R4-10, R4-11, R4-12, R4-13, R4-16 |
| ❌ ausente | 1: R4-15 | 6: R4-03, R4-04, R4-05, R4-07, R4-14, R4-15 |

**O que ficou pendente:**
- **R4-01:** `api/main.py` importa de `db` sem passar por `services`, `db/supabase_client.py` lê o
  ambiente fora de `core.config`, e o dashboard repete os limiares da faixa para colorir médias.
- **R4-03:** faltam a validação manual no Windows (BRA-442) e o simulador no clone limpo; a CI já
  prova o backend em Ubuntu, Windows e macOS a cada PR.
- **R4-05:** a recalibração D4 e o recall da faixa alta ficaram fora por decisão (BRA-450); a D4 está
  registrada como dívida no README.
- **R4-09:** a recusa no schema (422) não grava auditoria nem deixa linha com o `request_id` no log.
- **R4-12:** falta o link do vídeo no README.
- **R4-15:** o vídeo não foi gravado.
- **R4-16:** faltam congelar a `main` na data limite e registrar a decisão sobre o prêmio.

No início da sprint, a Entrega 3 deixara o fluxo integrado de pé, e o que a Sprint 4 cobrava era a
prova de que ele é confiável: reproduzível fora da máquina de quem o escreveu (R4-03), sem duplicata
nem órfão no banco (R4-04), testado quanto à integridade da coleta (R4-07) e documentado com
evidência (R4-14). No fim, três dessas provas estão entregues; de R4-03, faltam a validação manual no
Windows e o simulador no clone limpo.
