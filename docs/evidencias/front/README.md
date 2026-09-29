# Evidências do front · falhas da API e telas reais

Parte front da S4-28 e o "pronto quando" da S4-23 (BRA-456): *API derrubada com a tela aberta, API
lenta e resposta malformada produzem mensagem legível e recuperável*. Aqui estão os cenários de
falha da BRA-466. As telas com dados reais (BRA-470) estão no fim deste arquivo.

## Como foi feito

- **Front:** o dashboard real (`npm run dev`), sem nenhuma alteração para o teste.
- **Backend:** [`api-simulada.mjs`](api-simulada.mjs), um servidor Node sem dependências que segue o
  formato de `docs/contrato-api.md` com dado sintético e troca de cenário ao vivo. Nenhum destes
  cenários precisa de banco. Simular é o que torna cada falha reproduzível: derrubar a API, deixá-la
  muda ou fazê-la devolver HTML é difícil de provocar sob demanda na API de verdade.
- **Prints:** Chrome headless controlado por script (Playwright), 1440×900. Nenhum dado real:
  equipamentos, operadores e scores são sintéticos.

## Reproduzir

```bash
# terminal 1 — API simulada (porta 8010)
node docs/evidencias/front/api-simulada.mjs

# terminal 2 — dashboard apontando para ela, sem mexer no dashboard/.env.local
cd dashboard
VITE_API_BASE_URL=http://localhost:8010 npm run dev    # Windows (PowerShell): $env:VITE_API_BASE_URL="http://localhost:8010"; npm run dev
# http://localhost:5173 · entre com qualquer usuário e senha
```

Troque o cenário sem reiniciar: `curl -X POST 'http://localhost:8010/__cenario?nome=<cenario>'`,
com `<cenario>` entre `normal`, `lento`, `html`, `erro500` e `expirar`. "API fora do ar" é
encerrar o terminal 1.

## Cenários

| # | Cenário | Como provocar | Esperado | Resultado | Print |
|---|---|---|---|---|---|
| 0 | Referência | cenário `normal` | Visão geral com dados | ✅ | [00](00-referencia-visao-geral.png) |
| 1a | API cai **com dados na tela** | Visão geral carregada; encerrar a API e trocar o período (30 → 60) | dados mantidos + aviso com "Tentar de novo" | ✅ "Falha ao atualizar os indicadores; exibindo os últimos carregados." | [01a](01a-api-cai-com-dados-na-tela.png) |
| 1b | API fora **ao abrir a tela** | com a API encerrada, recarregar a página (F5) | mensagem legível + "Tentar de novo" | ✅ "Não foi possível carregar a visão geral." com o motivo (`Failed to fetch`) | [01b](01b-api-fora-ao-abrir.png) |
| 1c | Recuperação | religar a API e clicar em "Tentar de novo" | a tela inteira volta, sem recarregar a página | ✅ KPIs, Top 5 e contador do menu voltam; os alertas abrem o Detalhe (print da página inteira) | [02](02-api-religada-recupera.png) |
| 2 | API lenta | cenário `lento` (a rota nunca responde) e abrir Relatórios | timeout com mensagem, sem "Carregando…" eterno | ✅ "Carregando…" e, após **15 s**, "a API não respondeu em 15 s" + "Tentar de novo" | [03a](03a-api-lenta-carregando.png) · [03b](03b-api-lenta-timeout.png) |
| 3 | Resposta malformada | cenário `html` (status 200 com HTML) | erro legível, sem tela branca | ✅ "Resposta inesperada da API (text/html), esperado JSON." | [04](04-resposta-malformada.png) |
| 4 | 5xx | cenário `erro500` (500 com `request_id` no corpo, como no contrato) | mensagem com o `request_id` | ✅ "Erro interno… (código para suporte: `<request_id>`)" — ver limite abaixo | [05](05-erro-500-request-id.png) |
| 5 | Sessão expirada | cenário `expirar` (401 nas rotas de dado) | volta ao login dizendo "sessão expirada" | ✅ tela de login com "Sua sessão expirou. Entre novamente." | [06](06-sessao-expirada.png) |

A recuperação completa do cenário 1c depende do PR #44, que faz o "Tentar de novo" da Visão geral refazer
também a lista de equipamentos e o contador do menu. Antes dele, só os KPIs voltavam.

## Limites desta evidência

- O backend é simulado: prova o comportamento do **front** diante de cada resposta, não o
  comportamento da API real. Os formatos de erro seguem o contrato (500 com `request_id` no corpo,
  401 com `detail`).
- **A API simulada manda CORS em toda resposta, inclusive no 500.** A API real só passa a mandar
  CORS no 500 com o PR #37: antes dele, o middleware que monta o 500 ficava por fora do CORS, o
  navegador descartava a resposta e a tela dizia "Não foi possível falar com a API", sem o código.
  Por isso o ✅ do cenário 4 vale para a API real **a partir do #37**.
- O cenário "lenta" usa uma rota que nunca responde. Com resposta que chega depois de 15 s o
  resultado é o mesmo, porque o limite cobre a requisição inteira, leitura do corpo incluída.

## Telas reais contra a API com banco (BRA-470)

Capturadas em 28/09/2026. Setup:
- build de produção do dashboard (`npm run build` + `vite preview`, com a CSP ativa), na `main` em `5618c81`;
- API local ligada ao **Supabase real**, com o modelo `xgboost-v1.1`;
- uma sessão por perfil, em janela de 1440 px de largura;
- altura da página inteira (o dashboard rola o `<main>`, não a página), com o limite de 1500 px nas listas longas.

Os dados são sintéticos (dataset do projeto e avaliações de telemetria enviadas pela API).

| # | Perfil | Tela | O que mostra | Print |
|---|---|---|---|---|
| 10 | analista | Visão geral | KPIs da frota inteira (200 equipamentos, 5.000+ avaliações), mapa, tendência e risco por tipo de operação | [10](10-analista-visao-geral.png) |
| 11 | analista | Equipamentos (ranking) | frota ordenada por risco, com operador e número de avaliações | [11](11-analista-ranking.png) |
| 12 | analista | Detalhe do EQ-0042 | recomendações preventivas com o critério de cada uma (filtro por público); decomposição SHAP **completa** por grupo (`xgboost-v1.1`); top 5 fatores; histórico; manutenção; operador | [12](12-analista-detalhe-eq-0042.png) |
| 13 | analista | Relatórios · Equipamento | tendência do score por equipamento, com datas reais | [13](13-analista-relatorios-equipamento.png) |
| 14 | analista | Relatórios · Região | a mesma leitura por região | [14](14-analista-relatorios-regiao.png) |
| 15 | analista | Relatórios · Operação | a mesma leitura por tipo de operação | [15](15-analista-relatorios-operacao.png) |
| 20 | operador (`OP-0015`) | Meus equipamentos | só os 7 equipamentos que ele operou e só os alertas deles; menu reduzido | [20](20-operador-meus-equipamentos.png) |
| 21 | operador | Detalhe do EQ-0106 | última avaliação de **outro** operador: identidade como "outro operador" e nenhuma coordenada (LGPD, PR #46); sem ações de frota; decomposição rotulada como aproximação (predição do seed) | [21](21-operador-detalhe-avaliacao-de-outro-operador.png) |
| 22 | técnico | Manutenção da frota | equipamentos ordenados pelo atraso de manutenção; contagem de atrasados e em dia | [22](22-tecnico-manutencao-da-frota.png) |
| 23 | gestor | Visão geral | a leitura da frota para o gestor, sem Simulador, UBI nem Manutenção no menu | [23](23-gestor-visao-geral.png) |

**Reproduzir.** Com a API ligada ao banco e os usuários cadastrados (`scripts/criar_usuario.py`),
entre com cada perfil no build de produção e abra as telas da tabela. As negações do operador
(`/kpis`, `/tendencias` e equipamento fora do recorte → 403) estão demonstradas em
[`../backend/casos_de_uso.txt`](../backend/casos_de_uso.txt).

**Limites.**
- As sessões foram abertas com token assinado localmente pela própria API (`criar_token`), sem
  digitar senha. O login em si está coberto pelos testes do backend.
- O relatório por região ordena pelo maior score no último ponto. Com o dado de hoje, as 5
  primeiras regiões têm score 100 e 1 ou 2 avaliações. É o recorte real, e o print o mostra como está.

