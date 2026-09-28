# SafeField · Dashboard

Painel web (React 19 + TypeScript + Vite) que exibe os scores de risco da carteira. Ele não fala
com o banco: toda leitura passa pela API do backend (FastAPI), autenticada por JWT.

## Pré-requisitos

- **Node.js** `20.19+` ou `22.12+` (exigência do Vite 8)
- **API no ar.** Sem ela o dashboard abre só a tela de login e acusa que não consegue falar com a
  API. Para subir a API, veja "Como rodar o projeto" no [README da raiz](../README.md).

## Rodar

```bash
cd dashboard
cp .env.example .env.local
npm install
npm run dev
```

Abra o endereço que o Vite imprimir (por padrão **http://localhost:5173**) e entre com um usuário
de demonstração (`DEMO_USERS` do `.env` do backend, combinado fora do repositório).

Outros scripts:

| Script | O que faz |
|---|---|
| `npm run build` | checa tipos (`tsc -b`) e gera `dist/` |
| `npm run lint` | ESLint |
| `npm run preview` | serve o `dist/` localmente |

## Configuração

A **única** variável é `VITE_API_BASE_URL`, a base da API (padrão `http://localhost:8000`).

- Nenhuma credencial vai no bundle nem no `.env.local`. Usuário e senha são digitados na tela de
  login e trocados por um JWT em `POST /auth/token`.
- O Vite expõe ao browser tudo que tem prefixo `VITE_`. Nunca coloque chave de banco ou segredo
  aqui.
- Mudou o `.env.local`? Reinicie o `npm run dev`.

**CORS:** a API só aceita as origens de `API_CORS_ORIGINS` no `.env` do backend (padrão
`http://localhost:5173,http://localhost:5175`). Se o Vite subir em outra porta, porque a 5173
estava ocupada, acrescente a nova origem lá ou libere a porta.

## Telas

| Tela | Fonte dos dados | Estado |
|---|---|---|
| Visão geral | `GET /kpis`, `GET /alertas`, `GET /equipamentos` | ✅ API |
| Equipamentos (ranking) | `GET /equipamentos` | ✅ API |
| Detalhe do equipamento | `GET /equipamentos/{id}` | ✅ API |
| Sino de alertas (topo) | `GET /alertas` | ✅ API |
| Simulador | `data/mock.ts` | 🔒 "Em breve" |
| UBI · Prêmios | `data/mock.ts` | 🔒 "Em breve" |
| Relatórios | `data/mock.ts` | 🔒 "Em breve" |
| Persona Corretor | `data/mock.ts` | 🔒 "Em breve" |
| Persona Técnico | `data/mock.ts` | 🔒 "Em breve" |

As telas "Em breve" ficam atrás de um overlay com `inert`: não recebem clique nem foco por
teclado, e nenhuma delas confirma ação que não aconteceu. Os botões de ação sem endpoint
(Exportar, Relatório, Ligar operador, Disparar alerta) seguem a mesma regra.

## Sessão

- O JWT fica em **`sessionStorage`** (`safefield.sessao`): sobrevive a um refresh e morre quando a
  aba fecha. Isso é a dívida **D9**: token acessível a JavaScript e sem CSP. Está registrada em
  `docs/spec-sprint-04.md` e é tratada na S4-18.
- 401 da API ou prazo vencido derrubam a sessão, e o login mostra "Sua sessão expirou".
- Sair zera o estado da interface; o próximo login começa na Visão geral.

## Falhas da API

- Toda requisição desiste após **15 s** (`lib/apiClient.ts`).
- Resposta que não é JSON vira mensagem legível, não "Unexpected token '<'".
- Toda tela que busca dados tem "Tentar de novo". Um erro de render cai no `ErrorBoundary`, e não
  numa tela branca.

## Estrutura

```
src/
├── App.tsx              portão de sessão + shell (navegação, persona)
├── components/          TopBar, SideNav, Login, ComingSoon, ErrorBoundary, shared (Card, Chip, …)
├── data/
│   ├── api.ts           chamadas à API e adaptação das respostas
│   ├── shap.ts          rótulos e agregação dos fatores SHAP
│   └── mock.ts          dados fictícios, só das telas "Em breve"
├── lib/
│   ├── apiClient.ts     fetch com token, timeout e tratamento de erro
│   ├── auth.ts          sessão (sessionStorage)
│   ├── useCarga.ts      hook de busca com erro e "tentar de novo"
│   ├── risco.ts         faixas e tons de risco
│   └── formato.ts       formatação de datas
└── pages/               sompo/ (telas reais + mock), broker/, technician/
```

Contrato da API: [`docs/contrato-api.md`](../docs/contrato-api.md). Com a API no ar, o Swagger
fica em `${VITE_API_BASE_URL}/docs`.
