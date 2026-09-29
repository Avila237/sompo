# Evidências de validação do MVP

Reúne o que a Sprint 4 pede em R4-07 e R4-14 (`docs/spec-sprint-04.md`):

- testes de confiabilidade da coleta e de consistência das informações, que mostram que os
  dados que alimentam o modelo são íntegros e rastreáveis;
- evidências do funcionamento integrado, do controle de acesso, da proteção dos dados e dos
  registros de uso.

Cada evidência aponta para o teste que a sustenta e para o comando que a reproduz.

**Execução registrada:** 28/09/2026, contra a API local (uvicorn) ligada ao Supabase real,
com o modelo `xgboost-v1.1`. Os dados são sintéticos: nenhum dado real de segurado.

| Pasta | Conteúdo |
|---|---|
| `backend/` | saídas dos testes, execução contra o banco real, casos de uso por persona, auditoria e log |
| `front/` | dashboard sob falhas da API e telas reais por perfil (ver o `README.md` de lá) |

## Índice

| # | O que prova | Evidência | Teste que sustenta |
|---|---|---|---|
| 1 | **Coleta sem perda nem duplicata.** 24 leituras com 5 falhas injetadas (Open-Meteo fora, banco fora antes e depois do commit, PostgREST sem Postgres, resposta perdida no cliente) terminam em exatamente 24 avaliações e 24 predições, sem órfãs nem duplicatas | [`backend/pytest-confiabilidade.txt`](backend/pytest-confiabilidade.txt) | `tests/test_confiabilidade_coleta.py::TestColetaComFalhasInjetadas` |
| 2 | **O mesmo contra o banco real.** 20 leituras, 5 respostas descartadas de propósito e reenviadas com a mesma chave: 20 avaliações, 20 predições, nenhuma órfã, nenhuma duplicata, e a entrada gravada confere campo a campo com a enviada | [`backend/coleta_real.txt`](backend/coleta_real.txt) · [`.json`](backend/coleta_real.json) | checagens do próprio script; o checador é testado em `TestChecadorDoScriptReal` |
| 3 | **Rastreabilidade.** `X-Request-ID` da resposta → linha do log com o mesmo id → `avaliacao_id` → entrada e `clima_origem` (avaliação), `modelo_versao` (predição), usuário e horário (auditoria) | [`backend/log-correlacionado.txt`](backend/log-correlacionado.txt) · trilhas no fim de [`backend/coleta_real.txt`](backend/coleta_real.txt) | `TestColetaComFalhasInjetadas::test_rastreabilidade_pelo_log_de_producao` (sobre o formatter real de `backend/core/logging.py`) |
| 4 | **Registro de uso.** Toda gravação tem uma linha de auditoria (`sucesso` ou `reenvio`), e toda recusa por perfil tem um `erro` | [`backend/auditoria.txt`](backend/auditoria.txt) | `TestColetaComFalhasInjetadas::test_auditoria_sucesso_ou_reenvio_por_avaliacao` |
| 5 | **Consistência.** Payload inválido (schema ou consistência cruzada entre campos) é recusado com 422 e não grava nada; a mesma chave com outro payload dá 409 | [`backend/pytest-confiabilidade.txt`](backend/pytest-confiabilidade.txt) | `TestConsistenciaDoPayload` |
| 6 | **Controle de acesso e LGPD por perfil.** Cada persona vê só o que a matriz permite; o operador não vê identidade nem posição de outros operadores | [`backend/casos_de_uso.txt`](backend/casos_de_uso.txt) · [`.json`](backend/casos_de_uso.json) | `tests/test_autorizacao.py`, `tests/test_lgpd_operador.py`, `tests/test_casos_de_uso.py` |
| 7 | **Integridade dos dados gravados** (distribuição de faixas, SHAP completo, versão do modelo, integridade referencial), contra o banco real | [`backend/pytest-rede.txt`](backend/pytest-rede.txt) | `tests/test_predicoes.py`, `tests/test_supabase.py` (marker `rede`) |
| 8 | **O simulador não perde leitura** quando a Open-Meteo ou o banco caem: repete 502/503 com o mesmo `leitura_id` | [`backend/pytest-confiabilidade.txt`](backend/pytest-confiabilidade.txt) | `TestSimuladorNaoPerdeLeitura`, `TestEnviarComRetry` |
| 9 | **Dashboard sob falhas da API** (fora do ar, lenta, resposta malformada, 500 com código de suporte, sessão expirada) | [`front/README.md`](front/README.md) | cenários reproduzíveis com `front/api-simulada.mjs` |

## Casos de uso por persona

Roteirizados a partir das histórias de usuário do README (§3.3) e executados por
`scripts/evidencias/casos_de_uso.py`. O resultado passo a passo está em
[`backend/casos_de_uso.txt`](backend/casos_de_uso.txt).

| Persona | História | O que a execução mostrou |
|---|---|---|
| **Operador** (`OP-0015`) | alertas diretos para ajustar a condução | Vê os 7 equipamentos que operou (de 200) e só os alertas deles. Envia a própria leitura (201). Nos 3 equipamentos em que a última avaliação é de outro operador, `operador_id`, latitude e longitude vêm nulos. `/kpis`, `/tendencias` e equipamento fora do recorte → 403 |
| **Gestor de frota** | ranking de risco e comparação campo × transporte | KPIs da frota com o score médio por operação (transporte 53,1 × colheita 51,1), ranking, tendências por região e por operação. Envio de leitura → 403, auditado |
| **Técnico de manutenção** | padrões que antecedem danos, para agir antes | 89 equipamentos com manutenção atrasada, do mais atrasado ao menos; no detalhe, as recomendações para o técnico com o critério que disparou cada uma. Envio de leitura → 403, auditado |
| **Analista Sompo** | score explicável, fatores de risco e trilha de auditoria | Detalhe com SHAP completo por grupo e recomendações da avaliação que o operador acabou de enviar; o mesmo equipamento que o operador viu mascarado aparece com a identidade; auditoria com 1 `erro` por perfil recusado |

## Como reproduzir

Pré-requisitos:
- setup do README (venv, `.env` real, modelo treinado);
- migrations aplicadas;
- usuários cadastrados com `scripts/criar_usuario.py`;
- API de pé.

```bash
# 1, 5 e 8: suíte offline (não precisa de banco)
pytest tests/test_confiabilidade_coleta.py tests/test_casos_de_uso.py -v

# 7: integridade contra o banco real
pytest -m "rede and not seed" -v

# 2 e 3: coleta contra a API e o banco reais; o log da API vai para api.log
uvicorn backend.api.main:app --port 8000 > api.log 2>&1 &
SAFEFIELD_SENHA=... python scripts/evidencias/coleta_real.py --api http://127.0.0.1:8000 --log-api api.log --saida coleta.json

# 6: casos de uso por persona (senha de cada perfil em SAFEFIELD_SENHA_<PERFIL>)
python scripts/evidencias/casos_de_uso.py --api http://127.0.0.1:8000 --saida casos.json
```

Os dois scripts saem com `0` quando todas as checagens passam, com `1` quando alguma falha e
com `2` quando a API ou o banco estão fora.

## Limites (o que esta pasta não prova)

- **Autenticação da execução registrada.** A execução de 28/09 usou `--token-local`: o token é
  assinado com o `JWT_SECRET_KEY` do `.env`, sem login. O relatório registra isso. O login em si
  está coberto em `tests/test_autorizacao.py::TestLogin` e no smoke do PR #38 (usuário
  inexistente → 401). Para uma execução com login, rode os scripts sem `--token-local`.
- **Atomicidade real do Postgres.** Na suíte offline ela vem do repositório falso. No banco, a
  garantia é a função `registrar_avaliacao` (migration `20260928120000`), verificada pelo smoke
  do PR #35 e pela execução 2 acima.
- **Formato do erro do PostgREST sem Postgres.** O mapeamento para 503 segue a documentação do
  PostgREST e o comportamento do `postgrest-py` 2.31. Nenhum PostgREST real foi derrubado.
- **Rótulo de versão de 5 predições.** As avaliações 5040–5044, dos smokes de 28/09 feitos
  antes do #48, foram geradas pelo modelo atual mas gravadas como `xgboost-v1-baseline`. Elas não
  foram reescritas, para manter a trilha de auditoria intacta.
