# Evidências do front · falhas da API

Parte front da S4-28 e o "pronto quando" da S4-23 (BRA-456): *API derrubada com a tela aberta, API
lenta e resposta malformada produzem mensagem legível e recuperável*. Aqui estão os cenários de
falha da BRA-466. As telas com dados reais ficam na BRA-470, que depende da API com banco.

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
