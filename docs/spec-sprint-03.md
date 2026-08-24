# Spec — Entrega 3 (Challenge Sompo): Integração e MVP funcional

> **Fonte normativa:** enunciado "CHALLENGE SOMPO — terceira entrega", fornecido pela FIAP/Sompo.
> Este documento é a especificação derivada desse enunciado. Onde houver conflito entre esta spec
> e o roadmap de sprints descrito em `context.md` / `README.md`, **esta spec prevalece** — o roadmap
> interno é proposta do grupo, não contrato com a Sompo.
>
> **Data de entrega declarada:** 24/08/2026.
> **Escopo desta spec:** requisitos e critérios de aceite. Não contém plano de execução, ordem de
> trabalho nem estimativas.

---

## 1. Objetivo da entrega

Transformar componentes que hoje existem isolados em **um fluxo contínuo e estável de ponta a ponta**:

```
entrada de dados → banco → modelo de risco → saída para o usuário
```

O enunciado é explícito quanto ao critério de julgamento: *"a robustez e a clareza dessa integração
são mais importantes, neste momento, do que a sofisticação visual"*. Não se avalia qualidade de
modelo, refinamento de UI nem features novas — avalia-se se os módulos conversam.

**Meta declarada:** MVP com ~60% da solução em funcionamento.

**Denominador dos 60%:** a solução prometida na proposta inicial do grupo — plataforma de score de
risco preditivo para equipamentos agrícolas, com explicabilidade e alertas, alimentada por dados
ambientais, operacionais e geográficos. O cronograma interno de sprints **não** é o denominador.

---

## 2. Restrições de arquitetura (decididas)

| # | Restrição | Consequência |
|---|---|---|
| R1 | O dashboard React consome a **API do backend**, não o SDK do Supabase | `dashboard/src/data/api.ts` deixa de falar com o banco direto; a chave do Supabase sai do bundle do browser |
| R2 | Telemetria chega por **simulador Python + Open-Meteo real** | Sem dependência de firmware físico; a integração com fonte externa é demonstrável |
| R3 | Backend em **Python**, orquestrando o fluxo | Já é a stack declarada (FastAPI no `requirements.txt`) |
| R4 | Restrito às **disciplinas do primeiro ano** | Exclui LLM, RAG e embeddings — ver §7 |

---

## 3. Requisitos funcionais

Cada requisito traz sua origem no enunciado, o critério de aceite e o estado atual verificado no
repositório em 24/08/2026.

**Legenda de estado:** ✅ atendido · 🟡 parcial · ❌ ausente

---

### RF-01 · Backend integrador

**Origem:** *"desenvolver, em Python, o backend que organiza o fluxo de dados e conecta a entrada de informações ao modelo de risco"*

Serviço HTTP em Python que recebe uma leitura (telemetria + ambiente + operação), persiste,
aciona o modelo treinado e devolve o score com sua explicação.

**Aceite:** uma requisição com dados de um equipamento retorna score de risco, faixa e fatores
contribuintes, tendo persistido tanto a entrada quanto a predição.

**Estado:** ❌ — `backend/api/` e `backend/core/` contêm apenas `__init__.py`. Nenhuma linha de
FastAPI escrita; a dependência está declarada e não usada.

---

### RF-02 · Organização modular e tratamento de exceções

**Origem:** *"organização do código em funções e módulos, com tratamento básico de exceções para garantir um fluxo estável"*

O backend é dividido em camadas com responsabilidade única (rotas · serviço · acesso a dados ·
modelo). Falhas previsíveis — banco indisponível, payload inválido, artefato de modelo ausente,
API externa fora do ar — retornam erro tratado e registrado.

**Aceite:** nenhuma falha derruba o processo nem retorna stack trace ao cliente; nenhuma exceção é
engolida sem registro.

**Estado:** ❌ — não há camada de serviço. Os módulos ML existentes (`train.py`,
`shap_explainer.py`) são scripts de execução direta, não serviços.

---

### RF-03 · Persistência de dados recebidos e scores gerados

**Origem:** *"banco de dados (relacional e/ou não relacional) para persistir os dados recebidos e os scores de risco gerados"*

Toda leitura recebida vira registro em `avaliacoes`; toda predição vira registro em `predicoes`,
com score, faixa, fatores SHAP e versão do modelo.

**Aceite:** após uma requisição de scoring, existe uma linha nova em cada tabela, ligadas por
`avaliacao_id`.

**Estado:** 🟡 — o **esquema está pronto e é adequado**: `backend/db/schema.sql` define 4 tabelas
normalizadas com chaves estrangeiras e índices; `predicoes` já guarda `top_fatores_shap` (JSONB) e
`modelo_versao`. O que falta é escrita **transacional por requisição** — hoje só existe carga em
massa a partir do parquet (`seed_supabase.py`, `populate_predictions.py`).

---

### RF-04 · Pipeline de preparação e integridade histórica

**Origem:** *"pipelines de preparação que mantenham os dados prontos para o modelo e garantam a integridade histórica para auditoria"*

Uma função única converte a leitura persistida no vetor de 30 features na ordem de
`models/features.json`, aplicando o mesmo encoding do treino. Predições passadas nunca são
sobrescritas — o histórico é append-only e cada predição carrega a versão do modelo que a gerou.

**Aceite:** o mesmo pré-processamento serve treino e inferência (sem código duplicado); reprocessar
não apaga predição anterior.

**Estado:** 🟡 — `preprocess_features()` já existe em `backend/ml/train.py` e é reaproveitada por
`populate_predictions.py`, o que é a base correta. `modelo_versao` já é persistido. Falta: a
função vive dentro do script de treino (acoplamento indevido para uso em serviço) e
`populate_predictions.py` **apaga** as predições existentes antes de inserir (`clear_predicoes`),
o que viola a integridade histórica exigida.

---

### RF-05 · Recebimento e validação das fontes

**Origem:** *"recebimento de dados de telemetria, ambiente e operação, por simulação ou por dispositivos reais, com validação da consistência das entradas"*

Três origens distintas alimentam o sistema:

| Origem | Conteúdo | Como chega |
|---|---|---|
| Telemetria | vibração, temperatura do motor, velocidade, horas de operação | simulador Python emitindo contra a API |
| Ambiente | temperatura do ar, precipitação, vento, condição climática | Open-Meteo, pela coordenada da leitura |
| Operação | tipo de operação, horário, operador, dados de manutenção | payload do simulador |

Toda entrada é validada antes de tocar o banco: tipos, faixas e as regras de consistência já
especificadas em `docs/data schema.md` (ex.: `parado` implica velocidade zero; `tem_iot=false`
implica `temperatura_motor` nula).

**Aceite:** payload inválido é rejeitado com erro descritivo e **não** é persistido; payload válido
sem dados de clima é enriquecido automaticamente via Open-Meteo.

**Estado:** ❌ — não há simulador, não há chamada à Open-Meteo (`OPENMETEO_BASE_URL` está no
`.env.example` sem uso), não há validação de entrada (`pydantic` declarado e não usado). Os dados
existem apenas como parquet sintético gerado offline.

---

### RF-06 · Documentação do caminho do dado

**Origem:** *"definição clara de como os dados chegam ao sistema e como são utilizados para alimentar o modelo preditivo"*

Descrição textual e diagramática de cada salto: origem → validação → persistência → features →
modelo → SHAP → persistência da predição → interface.

**Aceite:** um leitor externo consegue seguir o caminho de um dado sem ler código.

**Estado:** 🟡 — o README tem diagrama Mermaid e descrição em camadas, mas descreve a arquitetura
**atual** (dashboard lendo o banco direto, modelo em batch). Precisa refletir o fluxo com backend.

---

### RF-07 · Controle de acesso e proteção da API

**Origem:** *"controle de acesso e proteção das APIs ou serviços criados, com cuidados de integridade e proteção dos dados sensíveis"*

Autenticação por token nos endpoints que leem ou escrevem dados, com distinção de perfil
(operador · gestor · analista Sompo). Acesso ao banco protegido por RLS. Segredos fora do
código-fonte e fora do bundle do frontend.

**Aceite:** requisição sem token válido é recusada; a chave usada pelo browser não permite escrita
direta no banco.

**Estado:** ❌ — `python-jose` e `JWT_SECRET_KEY` declarados e não usados. `schema.sql` **não**
habilita RLS nem cria policy alguma nas 4 tabelas, e `dashboard/src/lib/supabase.ts` embute
`VITE_SUPABASE_KEY` no bundle do browser. Na configuração atual, quem abre o dashboard consegue
ler e escrever as tabelas diretamente.

> **Risco nomeado:** hoje o dado é sintético, o que contém o dano. Com dado de segurado real, essa
> configuração é exposição de dado pessoal sob LGPD. RF-07 é o requisito de maior risco da entrega.

---

### RF-08 · Registros de uso rastreáveis

**Origem:** *"registros básicos de uso que permitam rastrear entradas, saídas e decisões do sistema"*

Log estruturado de cada requisição: quem chamou, quando, qual equipamento, qual score saiu, qual
versão do modelo decidiu. Erros registrados com contexto suficiente para diagnóstico, sem expor
dado sensível no log.

**Aceite:** dada uma predição no banco, é possível reconstruir quem a solicitou e quando.

**Estado:** ❌ — nenhum uso de `logging` em todo o repositório. Os scripts comunicam por `print()`.

---

### RF-09 · Interface com scores e alertas

**Origem:** *"dashboard básico ou relatório que exiba os scores de risco e os alertas por equipamento, operação ou região"*

Visualização dos scores e alertas, agregável pelos três eixos citados, consumindo a API.

**Aceite:** as três visões (equipamento, operação, região) estão disponíveis e os dados vêm do
backend, não do banco direto.

**Estado:** 🟡 — **o mais adiantado dos requisitos.** Três telas React funcionais com dados reais:
Visão Geral (KPIs, tendência, mapa de regiões, alertas), Ranking (200 equipamentos com filtro e
busca) e Detalhe (decomposição SHAP por grupo, top 5 fatores, manutenção, histórico). Lacunas:
(a) consome Supabase direto, violando R1; (b) não há agregação por **tipo de operação**;
(c) alertas são derivados em memória (`buildAlertas`), não persistidos.

> **Nota de interpretação:** o enunciado escreve *"dashboard básico ou relatório (em Python)"*.
> A entrega usa React consumindo a API Python. A leitura adotada é que o parêntese indica o teto
> mínimo esperado, não uma proibição — e que um cliente consumindo a própria API demonstra a
> integração exigida com mais força que um relatório lendo o banco. Ambiguidade registrada.

---

### RF-10 · Saídas interpretáveis

**Origem:** *"saídas interpretáveis e organizadas, priorizando a clareza para a tomada de decisão"*

O score nunca aparece sozinho: sempre acompanhado da faixa e dos fatores que o produziram.

**Aceite:** toda exibição de score traz sua decomposição.

**Estado:** ✅ — atendido pela tela de Detalhe (grupos SHAP com sinal, top 5 fatores rotulados em
português via `FEATURE_LABELS`). O mesmo contrato precisa ser preservado na resposta da API.

---

### RF-11 · README atualizado

**Origem:** *"README com a arquitetura integrada, o fluxo de dados de ponta a ponta e a justificativa das decisões técnicas"* · *"descrição clara da evolução do projeto em relação à Sprint anterior, incluindo o link do vídeo"*

**Aceite:** contém arquitetura integrada, fluxo ponta a ponta, justificativa das decisões,
instruções de execução do sistema completo, seção de evolução vs. entrega anterior e link do vídeo.

**Estado:** 🟡 — README é extenso e bem estruturado, mas descreve a arquitetura anterior. Faltam:
seção de evolução, instruções de execução do backend, link do vídeo novo. Há também referências
quebradas (`challenge_sompo.txt`, `hardware_iot.txt`, dois PDFs removidos do versionamento).

---

### RF-12 · Diagrama atualizado

**Origem:** *"diagrama atualizado do pipeline, da coleta à apresentação do score"*

**Aceite:** o diagrama mostra a API como orquestradora entre entrada, banco, modelo e interface.

**Estado:** 🟡 — existe diagrama Mermaid de 4 camadas, correto para a arquitetura atual e
desatualizado em relação à exigida.

---

### RF-13 · Vídeo de apresentação

**Origem:** *"até 5 minutos, com narração humana, demonstrando o fluxo integrado de ponta a ponta e explicando a arquitetura"* · *"configurado como 'não listado' no YouTube"*

**Aceite cumulativo:** ≤5 min · narração humana (não sintetizada) · demonstra entrada do dado,
geração do score e apresentação na interface · explica a arquitetura · publicado como **não
listado** · link no README.

**Estado:** ❌ para esta entrega — o vídeo referenciado no README é da entrega anterior. A
visibilidade "não listado" do vídeo existente não foi verificada.

---

### RF-14 · Conformidade do repositório

**Origem:** *"o GitHub deve ser privado e compartilhado com o perfil: fiap-tutoria"*

**Aceite:** repositório privado, com `fiap-tutoria` aceito como colaborador.

**Estado:** 🟡 — repositório privado em `github.com/Avila237/sompo`. O compartilhamento com
`fiap-tutoria` (destinatário novo, substitui as tutoras individuais das entregas anteriores) é ação
administrativa a executar no GitHub.

---

## 4. Requisitos não funcionais

| # | Requisito | Origem | Estado |
|---|---|---|---|
| RNF-01 | Segredos fora do código e fora do bundle do frontend | *"proteção dos dados sensíveis"* | ❌ chave do Supabase embutida no browser |
| RNF-02 | Nenhuma falha silenciosa — toda exceção tratada é registrada | *"fluxo estável"* | ❌ sem logging |
| RNF-03 | Toda predição rastreável à versão do modelo que a gerou | *"integridade histórica para auditoria"* | ✅ `modelo_versao` em `predicoes`; MLflow registra os runs |
| RNF-04 | Clareza acima de sofisticação visual | texto §1 do enunciado | ✅ |
| RNF-05 | Solução restrita às disciplinas do primeiro ano | *"usando exclusivamente as disciplinas do primeiro ano"* | ✅ por construção — ver §7 |

---

## 5. Contrato da API (proposta)

Derivado dos requisitos; sujeito a confirmação antes da implementação.

| Método | Rota | Finalidade | Requisitos |
|---|---|---|---|
| `POST` | `/auth/token` | emissão de token por perfil | RF-07 |
| `POST` | `/avaliacoes` | recebe leitura, valida, enriquece com clima, persiste, scora, persiste predição, devolve score + SHAP | RF-01, RF-03, RF-04, RF-05 |
| `GET` | `/equipamentos` | lista com score mais recente e faixa | RF-09 |
| `GET` | `/equipamentos/{id}` | detalhe: última avaliação, predição, decomposição SHAP, histórico | RF-09, RF-10 |
| `GET` | `/alertas` | alertas ativos, filtráveis por equipamento, operação ou região | RF-09 |
| `GET` | `/kpis` | agregados da visão geral | RF-09 |
| `GET` | `/health` | disponibilidade do serviço e dos artefatos do modelo | RF-02 |

**Resposta de scoring — contrato mínimo** (preserva RF-10):

```json
{
  "avaliacao_id": 5001,
  "equipamento_id": "EQ-0042",
  "risco_score": 74.3,
  "faixa_risco": "alto",
  "contribuicoes_por_grupo": { "ambiental": 12.4, "operador": 8.1, "manutencao": 3.2 },
  "top_fatores": [
    { "feature": "historico_sinistros", "valor": 7, "shap_value": 18.6, "grupo": "equipamento" }
  ],
  "modelo_versao": "xgboost-v1-baseline",
  "timestamp": "2026-08-24T14:30:00Z"
}
```

---

## 6. Impacto no que já existe

| Artefato | Situação |
|---|---|
| `backend/db/schema.sql` | reaproveitado; **acrescentar** RLS + policies (RF-07) |
| `backend/ml/train.py` | reaproveitado; `preprocess_features()` e `derive_faixa()` precisam sair do script de treino para um módulo compartilhado (RF-04) |
| `backend/ml/shap_explainer.py` | reaproveitado; `explain_record()` serve a resposta da API |
| `models/*.joblib` | reaproveitados sem retreino — a entrega não avalia o modelo |
| `scripts/populate_predictions.py` | referência do pipeline; o `clear_predicoes()` conflita com RF-04 |
| `dashboard/src/data/api.ts` | reescrito para consumir a API (R1) |
| `dashboard/src/lib/supabase.ts` | removido do caminho de dados do browser (RF-07) |

---

## 7. Fora de escopo

Excluído por decisão explícita, com justificativa:

| Item | Motivo |
|---|---|
| **RAG / LLM / base de conhecimento** | O enunciado não menciona RAG, LLM nem geração de linguagem natural, e restringe a solução às disciplinas do primeiro ano. Construir isso consome esforço em algo não avaliado. |
| **App móvel** | Não citado no enunciado; a interface exigida é dashboard ou relatório. |
| **Firmware ESP32 físico** | O enunciado aceita *"por simulação ou por dispositivos reais"* — R2 opta por simulação. |
| **Recalibração do modelo / regeneração do dataset** | A entrega não avalia qualidade preditiva. Retreinar dispararia retrabalho em cascata (dataset → treino → SHAP → banco → testes → figuras) sem ganho de conformidade. |
| **Integração IBGE (shapefiles)** | Os dados geográficos (tipo de solo, distância de água, declividade) já existem no dataset. Não é exigido enriquecimento geográfico em tempo real. |

---

## 8. Rastreabilidade

| Trecho do enunciado | Requisitos |
|---|---|
| Backend integrador | RF-01, RF-02 |
| Engenharia de dados | RF-03, RF-04 |
| Integração com fontes | RF-05, RF-06 |
| Segurança da informação | RF-07, RF-08, RNF-01, RNF-02 |
| Interface simples | RF-09, RF-10, RNF-04 |
| Documentação | RF-06, RF-11, RF-12 |
| Entregáveis (§5.1) | RF-11, RF-12, RF-13, RF-14 |

---

## 9. Resumo do estado

| Estado | Requisitos |
|---|---|
| ✅ atendido | RF-10, RNF-03, RNF-04, RNF-05 |
| 🟡 parcial | RF-03, RF-04, RF-06, RF-09, RF-11, RF-12, RF-14 |
| ❌ ausente | RF-01, RF-02, RF-05, RF-07, RF-08, RF-13, RNF-01, RNF-02 |

O eixo da entrega — backend integrador, ingestão validada e segurança (RF-01, RF-02, RF-05, RF-07,
RF-08) — está integralmente ausente. O que está pronto é a fundação sobre a qual ele se apoia:
esquema de banco adequado, modelo treinado com explicabilidade e interface funcional.
