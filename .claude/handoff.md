# Handoff — 24/08/2026

**Onde parou:** `7047d83` na `main` · Supabase `sompo` ACTIVE_HEALTHY, migration `20260824120000` aplicada, 5.024 avaliações (5.000 seed + 24 telemetria) · API e dashboard rodam local, sem deploy

## O que estava em voo

Nada pela metade. Os cinco PRs da Entrega 3 foram mergeados e as branches removidas — só existe `main`.

A única coisa que ficou em aberto por decisão, não por falta de tempo: a **BRA-298** (textos fictícios na tela). O Guilherme optou por não corrigir antes de gravar.

## Esperando o Guilherme

**Adicionar `fiap-tutoria` como colaborador no GitHub** (BRA-297). É o item que **invalida a entrega se faltar** — sem isso o tutor não acessa o repositório. Só o dono do repo consegue fazer.

**Gravar o vídeo** (BRA-296). Critérios cumulativos: ≤5 min · narração humana · fluxo de ponta a ponta · arquitetura explicada · publicado como **não listado** · link no README, onde o Kainan já reservou o espaço.

**Decidir sobre a dívida D4** (recalibração dos pesos). Medida e provada viável nesta sessão: `historico_sinistros` responde hoje por ~44% da explicação SHAP; operador e manutenção somam ~6%. O rebalanceamento levaria operador a 18,9% e manutenção a 15,6%, usando **limiares** em vez de soma linear. O custo é cascata completa — dataset, treino, SHAP, 6 figuras, repopular o banco, ajustar `test_generate_dataset.py` e `test_dataset.py`, e a §4 do `data schema.md`. **Repopular apagaria as avaliações de telemetria e a tabela `auditoria`**, que são a evidência da integração; dá para preservar filtrando `fonte='seed'`, mas é cirurgia num banco hoje consistente.

**Divergência de numeração RF-11/RF-12.** A `spec-sprint-03.md` (normativa, derivada do enunciado) usa RF-11 = README e RF-12 = Diagrama. A `spec-implementacao` inventou um "RF-11 · Testes" — que o enunciado não pede — e empurrou os demais. O Linear seguiu a de implementação. Os dois documentos vão ser lidos pelo tutor. Não corrigido por falta de decisão.

## O que eu faria a seguir

**Gravar antes de mexer em qualquer coisa.** O sistema está verde e verificado ponta a ponta agora; qualquer alteração antes da gravação reabre a necessidade de revalidar. `./scripts/demo.sh` sobe API e dashboard juntos e pausa em cada etapa para narração.

Depois da entrega, a ordem que faz sentido: **D4** (é a que muda o produto, e a tela hoje contradiz a narrativa do README), depois **D1+D2+D3+D9** juntas (são a mesma dívida de autenticação vista de quatro ângulos), depois CI.

## O que NÃO foi verificado

**O dashboard rodando em outra máquina.** Toda a validação foi no macOS do Guilherme. O `.env` e o `dashboard/.env.local` não atravessam máquinas — na Windows, será preciso recriar ambos e rodar `brew`-equivalente para o OpenMP.

**A visibilidade do vídeo da Entrega 2**, ainda linkado no README. Só o Guilherme, logado no YouTube, consegue confirmar se está "não listado".

**Comportamento do dashboard com a API fora do ar.** O `apiClient.ts` trata (`ApiError` com status 0), mas ninguém derrubou a API com a tela aberta para ver o que aparece.

**Se o Supabase aguenta a demo.** O projeto já pausou uma vez por inatividade — foi assim que esta sessão começou. Vale conferir o status logo antes de gravar; o `demo.sh` faz isso na etapa 0 e para com mensagem clara se o banco não responder.
