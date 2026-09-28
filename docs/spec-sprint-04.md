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

Cada requisito traz a origem no enunciado, o critério de aceite, o estado verificado no repositório
em 28/09/2026 e as tasks que o atendem.

**Legenda de estado:** ✅ atendido · 🟡 parcial · ❌ ausente

---

### Refinamento do código e da arquitetura

#### R4-01 · Código modular e arquitetura documentada

**Origem:** *"código Python organizado em módulos e funções padronizadas, com a arquitetura do
sistema documentada e o fluxo de execução claro do início ao fim"*

**Aceite:** a direção de dependência declarada (api → services → ml/db; core ← todos) é respeitada
sem exceção; nenhuma regra de negócio tem duas implementações; a documentação de arquitetura
descreve o código que existe.

**Estado:** 🟡 — as camadas existem e não há ciclo. Desvios:
- `api/main.py` e `api/routers/health.py` importam `ml` direto, pulando `services`.
- A faixa de risco é derivada em quatro lugares: `ml/preprocess.py`, `services/consultas.py`,
  `ml/shap_explainer.py` e o dashboard.
- `db/supabase_client.py` lê o ambiente fora de `core.config`.
- `context.md` descreve a arquitetura da Sprint 2.

**Tasks:** S4-02, S4-16, S4-21, S4-24, S4-32

#### R4-02 · Exceções e validação de entrada

**Origem:** *"tratamento de exceções e validações que garantam um fluxo estável e reproduzível, sem
interrupções diante de entradas ausentes, inválidas ou fora do padrão esperado"*

**Aceite:**
- Payload inconsistente é recusado com erro descritivo e não persiste.
- Dependência indisponível (modelo, banco, Open-Meteo) produz resposta tratada e registrada.
- Nenhuma falha deixa registro em estado intermediário.
- A interface não trava nem quebra diante de API lenta, fora do ar ou com resposta malformada.

**Estado:** 🟡 — faixas por campo e campo desconhecido já são recusados (422). Faltam:
- A validação cruzada: `parado` com velocidade, motor sem IoT, tempestade sem chuva.
- `ModeloIndisponivel` e `BancoIndisponivel` existem mas nunca são levantados, então viram 500
  genérico.
- A compensação em `scoring.py` pode deixar uma avaliação sem predição e sem trilha.
- No dashboard, o `fetch` não tem timeout e não há ErrorBoundary.

**Tasks:** S4-13, S4-14, S4-21, S4-23

#### R4-03 · Execução reproduzível

**Origem:** *"fluxo de ponta a ponta funcionando de forma estável e reproduzível"* (§5.1) · *"um
sistema que funciona uma vez, no ambiente de quem o desenvolveu, ainda não é uma solução"* (§1)

**Aceite:** um clone limpo, seguindo só o README, sobe API, dashboard e simulador e roda a suíte
verde em Windows e macOS, com as mesmas versões de dependência nas duas máquinas; a CI confirma a
cada push.

**Estado:** ❌
- Toda a validação da E3 foi no macOS.
- `.env.example` omite `DEMO_USERS`, que é obrigatória, então a API quebra no import.
- `requirements.txt` fixa só a major, e trocar de versão já mudou o MAE.
- `scripts/demo.sh` só roda em Unix.
- Não há CI.

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

**Estado:** ❌
- `POST /avaliacoes` não é idempotente, e `predicoes.avaliacao_id` não tem restrição de unicidade.
- `predicao_de` usa `limit(1)` sem ordem.
- Equipamento sem avaliação aparece como score 0, faixa "baixo".
- `seed_supabase.py` manda executar `schema.sql`, que começa com `DROP` e ignora a migration da E3.
- A decomposição SHAP por grupo não é persistida.

**Tasks:** S4-12, S4-13, S4-15, S4-16, S4-22

#### R4-05 · Ajuste final do modelo

**Origem:** *"ajuste final do modelo preditivo, com revisão de variáveis e avaliação de desempenho
por métricas adequadas ao problema, justificando as escolhas realizadas"*

**Aceite:** as variáveis prometidas pela solução (perfil do operador, manutenção) têm peso material
na explicação do modelo; as métricas incluem o erro que importa para a seguradora (recall da faixa
alta); treino e inferência usam a mesma função de pré-processamento; cada predição é distinguível
pela versão do modelo que a gerou.

**Estado:** ❌
- `historico_sinistros` responde por ~44% da explicação SHAP; operador e manutenção somam ~6%.
- `train.py` reimplementa o pré-processamento em vez de chamar `preprocess_features()`.
- Modelos diferentes gravaram predições com o mesmo `modelo_versao`.

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

**Estado:** 🟡 — o simulador, a Open-Meteo e o fallback para o payload funcionam, com
`clima_origem` gravado. Desvios:
- `precipitacao_mm` é a chuva de ontem em UTC, não a das últimas 24 h.
- Com a Open-Meteo no ar, o clima medido em campo é descartado.
- Sem clima externo, o simulador calcula a umidade do solo por uma fórmula diferente da Regra 3.

**Tasks:** S4-12, S4-20

#### R4-07 · Testes de confiabilidade da coleta

**Origem:** *"testes de confiabilidade da coleta e de consistência das informações, demonstrando
que os dados que alimentam o modelo são íntegros e rastreáveis"*

**Aceite:** um teste envia N leituras com falhas injetadas e confirma exatamente N avaliações e N
predições, sem órfãs nem duplicatas; toda asserção agregada verifica que o conjunto não é vazio; a
suíte não altera arquivos versionados.

**Estado:** ❌ — não existe teste de confiabilidade da coleta. A suíte atual:
- tem testes que passam sobre conjunto vazio;
- tem testes intermitentes, conforme a linha que a amostra sorteia;
- tem testes que dividem por 5.000 fixo;
- sobrescreve `models/shap_values.npy` e as figuras SHAP versionadas.

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

**Estado:** 🟡 — JWT em todas as rotas de dado, RLS sem policy para `anon` e `service_role` só no
servidor. Pendências:
- Credenciais em variável de ambiente (D1).
- Perfil ignorado por todas as rotas (D3).
- Token em `sessionStorage` sem CSP (D9).
- `.env.example` traz um segredo JWT utilizável.
- `python-jose` 3.3 tem duas CVEs.
- Sem rate limit em `/auth/token`.
- `/health` expõe o texto da exceção.

**Tasks:** S4-07, S4-08, S4-18, S4-19

#### R4-09 · Registros de uso

**Origem:** *"registros (logs) de uso que permitam rastrear entradas, saídas e decisões do sistema,
sustentando auditoria e explicabilidade do score de risco"*

**Aceite:** toda requisição que decide ou falha, inclusive por dependência externa, deixa registro
em log e em `auditoria`, correlacionável pelo `request_id` presente no header e no corpo da
resposta.

**Estado:** 🟡 — log estruturado com `request_id` e tabela `auditoria` implementados. Lacunas:
- O 502 de clima e as falhas do banco antes do insert não geram auditoria.
- Respostas 500 não trazem `X-Request-ID`.
- Falha ao gravar auditoria é registrada em log e a requisição segue com 201.

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

**Estado:** 🟡 — Visão Geral, Ranking e Detalhe consomem a API, com agregação pelos três eixos no
estado atual. Faltam:
- A tendência é só global, e o eixo "N dias" conta dias com dado, não dias corridos.
- Relatórios, Corretor e Técnico são mock atrás de "Em breve".
- Não há visão de operador nem de gestor.
- A tela mostra textos e notificações fictícios (BRA-298).
- A decomposição do Detalhe é recalculada a partir de só 5 fatores.

**Tasks:** S4-15, S4-23, S4-24, S4-26, S4-27, BRA-298

#### R4-11 · Alertas e recomendações com critérios explícitos

**Origem:** *"alertas e recomendações preventivas derivados do score de risco, com critérios
explícitos e interpretáveis pelo usuário final"*

**Aceite:** toda avaliação de faixa média ou alta traz ao menos uma recomendação acompanhada do
critério que a disparou; a regra é determinística, versionada e testada; nenhuma ação é confirmada
na tela sem ter ocorrido.

**Estado:** 🟡
- Alertas existem: `GET /alertas`, com regra no servidor.
- Recomendação **não existe**: saiu do escopo junto com o RAG na E3.
- No Detalhe, "Disparar alerta" é alcançável por teclado atrás do overlay e exibe "Alerta enviado ✓"
  sem enviar nada.

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

**Estado:** 🟡
- O README é extenso e cobre a E3.
- Contradiz a si mesmo nas métricas (§6.3 × §8).
- Lista como pendentes campos já implementados.
- Descreve a ordem persistir → prever, invertida em relação ao código.
- Cobre a evolução só da E2 para a E3.
- `docs/data schema.md` diverge da fórmula do código.
- `contrato-api.md` omite nulos e códigos de erro reais.
- O README do dashboard é o boilerplate do Vite.

**Tasks:** S4-03, S4-04, S4-05, S4-06, S4-29

#### R4-13 · Diagrama de arquitetura final

**Origem:** *"desenho consolidado do fluxo de ponta a ponta (entrada → banco → modelo → saída),
refletindo a solução efetivamente entregue"*

**Aceite:** o diagrama corresponde ao código entregue na S4, incluindo recomendações, relatórios e
controle de acesso por perfil.

**Estado:** 🟡 — o diagrama Mermaid da E3 está no README, mas mostra a ordem persistir → prever e
tem o rótulo "fallback: payload" na aresta da Open-Meteo, que está invertida.

**Tasks:** S4-03, S4-29

#### R4-14 · Evidências de validação do MVP

**Origem:** *"evidências de validação do MVP (testes, execuções demonstrativas ou casos de uso) que
comprovem o funcionamento integrado da solução"* · *"evidências do controle de acesso, da proteção
dos dados e dos registros de uso"* (§5.1)

**Aceite:** `docs/evidencias/` reúne a saída dos testes, prints das telas, um log correlacionado
por `request_id` e uma consulta à auditoria, com um caso de uso roteirizado por persona; cada
evidência aponta para o teste que a sustenta e pode ser reproduzida pelo avaliador.

**Estado:** ❌

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

**Estado:** ❌

**Tasks:** S4-30

#### R4-16 · Conformidade do repositório

**Origem:** *"o GitHub deve ser privado e compartilhado apenas com o perfil: fiap-tutoria"* ·
*"não poderá sofrer alterações após a data limite de entrega"* · manifestação na primeira capa caso
o grupo não deseje concorrer ao prêmio

**Aceite:** repositório privado, com `fiap-tutoria` aceito como colaborador; `main` congelada na
data limite; decisão sobre concorrer ao prêmio registrada.

**Estado:** 🟡 — o repositório é privado. O convite a `fiap-tutoria` da E3 (BRA-297) não tem
conclusão registrada, e a decisão sobre o prêmio não foi tomada.

**Tasks:** S4-31

---

## 5. Requisitos não funcionais

| # | Requisito | Origem | Estado |
|---|---|---|---|
| RNF4-01 | Nenhuma falha silenciosa: toda exceção tratada é registrada | *"sem interrupções"*, *"rastrear decisões"* | 🟡 falha de auditoria segue com 201; falha do `/equipamentos` no dashboard é engolida no contador |
| RNF4-02 | Toda operação que grava e pode ser reentregue é idempotente | *"sem perda ou corrupção de dados"*, *"duplicidades"* | ❌ |
| RNF4-03 | Toda predição é rastreável à versão do modelo que a gerou | *"integridade das informações"* | 🟡 coluna existe; modelos diferentes compartilham a mesma versão |
| RNF4-04 | Segredos fora do código, do bundle e do exemplo de configuração | *"proteção de dados"* | 🟡 fora do código e do bundle; o exemplo traz segredo JWT utilizável |
| RNF4-05 | Tela nunca afirma dado, ação ou notificação que não veio da API | *"saídas que sustentam uma decisão preventiva"* | ❌ |

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

| Estado | Requisitos |
|---|---|
| ✅ atendido | — |
| 🟡 parcial | R4-01, R4-02, R4-06, R4-08, R4-09, R4-10, R4-11, R4-12, R4-13, R4-16 |
| ❌ ausente | R4-03, R4-04, R4-05, R4-07, R4-14, R4-15 |

A Entrega 3 deixou o fluxo integrado de pé. O que a Sprint 4 cobra, e ainda falta, é a prova de que
ele é confiável: reproduzível fora da máquina de quem o escreveu (R4-03), sem duplicata nem órfão no
banco (R4-04), testado quanto à integridade da coleta (R4-07) e documentado com evidência (R4-14).
