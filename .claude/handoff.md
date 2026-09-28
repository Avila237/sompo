# Handoff — 28/09/2026

**Onde parou:** `35f8f01` na `main` · Supabase **não medido** nesta sessão (não há `.env` real na máquina Windows usada; a do Mac não foi olhada) · migrations da Sprint 4 escritas e ensaiadas em Postgres local, **nenhuma aplicada**

## O que estava em voo

Dois PRs meus em **rascunho, verdes na CI**, que só podem ser mesclados depois de aplicar a migration de cada um:

- **#35 · S4-12/13/15** (BRA-445/446/448) — idempotência por `leitura_id` (reenvio → 200, conflito → 409), avaliação+predição gravadas numa transação (função `registrar_avaliacao`), UNIQUE `(avaliacao_id, modelo_versao)`, `contribuicoes_por_grupo` gravada e usada no Detalhe. **Sem a migration `20260928120000` aplicada, todo `POST /avaliacoes` dá 500.**
- **#38 · S4-18** (BRA-451) — tabela `usuarios` (scrypt), matriz perfil × rota aprovada, CSP no build do dashboard. **Sem a migration `20260928130000` e sem cadastrar usuário por `scripts/criar_usuario.py`, ninguém faz login** — o `DEMO_USERS` deixa de ser lido.

Os dois tocam `repository.py`, `scoring.py` e `contrato-api.md`: quem mesclar o segundo resolve conflito. Ordem sugerida: #35, depois #38.

**Cinco PRs do Kainan abertos e ainda não revisados** (combinado: revisão por subagente + merge meu com CI verde): #30 (BRA-468), #33 (BRA-298), #34 (BRA-466), #36 (BRA-467, README), #37 (CORS expõe X-Request-ID).

## Esperando o Guilherme

- **`.env` real** em uma das máquinas. Bloqueia: aplicar as duas migrations, S4-09 (setup Windows + `demo.sh` multiplataforma), S4-11 parte 2, S4-28 (evidências) e o backfill abaixo.
- **Ok para aplicar as migrations** no SQL Editor — `20260928120000` primeiro. Ela aborta sem apagar nada se já houver predição duplicada; nesse caso a limpeza é decisão sua, com a lista em mãos.
- **Backfill das 5.000 predições do seed** (BRA-448): (a) recalcular só `contribuicoes_por_grupo` onde é nula — preserva histórico, recomendado; (b) regravar predições inteiras — viola append-only e o recálculo não reproduz os scores entre Windows e Mac.
- **LGPD no recorte do operador** (levantado na revisão do #38, não decidido): o operador vê equipamentos que operou, mas com a última avaliação, o histórico e os alertas **de outros operadores** nesses equipamentos — `operador_id`, latitude e longitude. Opções: aceitar (recorte é por equipamento, como na matriz), ou omitir localização/identidade alheia para o perfil operador (~1 função em `consultas.py`).
- **Apagar `DEMO_USERS` do `.env`** das duas máquinas depois do merge do #38 (senha em texto).

## O que eu faria a seguir

1. Revisar e mesclar os PRs do Kainan (#37 e #30 são pequenos; #36 muda o README e deve ser conferido contra o #38, que tira o `DEMO_USERS`).
2. Com o `.env`: aplicar `20260928120000`, smoke do reenvio (201 → 200), mesclar #35; aplicar `20260928130000`, cadastrar `analista`/`gestor`/`tecnico`/`operador`, smoke do 403, mesclar #38.
3. Só então a S4-28 (evidências), que precisa do sistema final rodando.

O roteiro do vídeo, com narração e comandos por bloco, está na **BRA-463** e já assume o #38 mesclado.

## O que NÃO foi verificado

- **As migrations contra o Supabase real.** Foram ensaiadas em Postgres 16 local, com os privilégios padrão do Supabase simulados. Os ensaios estão nos PRs em `scripts/ensaios/` — os arquivos são a consolidação dos comandos executados, mas não foram re-executados nessa forma final (o container foi parado no encerramento).
- **O simulador, o `demo.sh` e o `criar_usuario.py` contra banco real** — só sintaxe e testes com repositório mockado.
- **Ausência de violação de CSP no console** do build de produção: o login renderiza com a CSP ativa (headless), mas o log headless não mostra o console.
- **Os comandos `curl` do roteiro da BRA-463** contra a API real: os payloads foram validados contra o schema, não contra o banco (`EQ-0042`/`OP-0015` podem não existir no seed).
- **README da `main` e `docs/spec-sprint-04.md`** ainda citam `DEMO_USERS`; ficam errados quando o #38 entrar. README é da BRA-462 (Kainan).
